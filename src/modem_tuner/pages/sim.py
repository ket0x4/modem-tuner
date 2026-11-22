"""SIM: identity, PIN/PUK handling and preferred network list."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import constants as C  # noqa: E402
from ..client import MODEM_IFACE, Sim  # noqa: E402
from ..widgets import (RowList, banner, button_row, dialog_size, prompt,  # noqa: E402
                       run_in_background, toast, value_row)
from ._base import Page  # noqa: E402


class SimPage(Page):
    interfaces = (MODEM_IFACE,)

    def __init__(self, window) -> None:
        super().__init__(window, title="SIM",
                         icon_name="smartphone-symbolic", name="sim")
        self.sim: Sim | None = None
        self._rows: dict[str, Adw.ActionRow] = {}

        self._info = Adw.PreferencesGroup(title="SIM")
        self.add(self._info)

        for key, title in [
            ("active", "Active"), ("imsi", "IMSI"), ("icc", "ICCID"),
            ("operator", "Operator"), ("mccmnc", "MCC/MNC"),
            ("type", "Type"), ("esim", "eSIM status"), ("eid", "eID"),
            ("removability", "Removability"), ("gid1", "GID1"), ("gid2", "GID2"),
        ]:
            row = value_row(title, "—")
            self._info.add(row)
            self._rows[key] = row

        self._lock = Adw.PreferencesGroup(
            title="SIM lock",
            description="The modem asks for this code before it can register.",
        )
        self.add(self._lock)

        self._lock_row = value_row("Lock state", "—")
        self._lock.add(self._lock_row)
        self._retries_row = value_row("Unlock retries", "—")
        self._lock.add(self._retries_row)

        self._unlock_row = button_row(
            "Unlock SIM", "Enter the PIN to unlock the modem now.",
            "Unlock", self._on_unlock)
        self._lock.add(self._unlock_row)

        self._pin_group = Adw.PreferencesGroup(title="PIN management")
        self.add(self._pin_group)
        self._pin_group.add(button_row(
            "Enable or disable PIN", "PIN protection asks for the code on every boot.",
            "Configure", self._on_enable_pin))
        self._pin_group.add(button_row(
            "Change PIN", "Replace the current SIM PIN.", "Change", self._on_change_pin))

        self._pref_group = Adw.PreferencesGroup(
            title="Preferred networks",
            description="Operator MCC/MNC list written to the SIM.",
        )
        self.add(self._pref_group)
        self._pref_list = RowList()
        self._pref_group.add(self._pref_list)
        self._pref_group.add(button_row(
            "Edit preferred networks", "One MCCMNC per line.", "Edit",
            self._on_edit_preferred))

        self._emergency_group = Adw.PreferencesGroup(title="Emergency numbers")
        self.add(self._emergency_group)
        self._emergency_list = RowList()
        self._emergency_group.add(self._emergency_list)

    # -- binding ----------------------------------------------------------

    def changed(self, *_args) -> None:
        self.reload()

    def reload(self) -> None:
        modem = self.modem
        if modem is None:
            return
        path = modem.sim_path
        self.sim = Sim(path, on_change=self.refresh) if path else None
        self.refresh()

    def refresh(self) -> None:
        sim = self.sim

        def set_row(key: str, text: str) -> None:
            row = self._rows.get(key)
            if row is not None:
                row.value_label.set_text(text or "—")

        if sim is None:
            for key in self._rows:
                set_row(key, "No SIM")
            self._lock_row.value_label.set_text("—")
            return

        set_row("active", "Yes" if sim.active else "No")
        set_row("imsi", sim.imsi)
        set_row("icc", sim.sim_identifier)
        set_row("operator", sim.operator_name)
        set_row("mccmnc", sim.operator_identifier)
        set_row("type", C.SIM_TYPE.get(sim.sim_type, "Unknown"))
        set_row("esim", C.ESIM_STATUS_LABELS.get(sim.esim_status, str(sim.esim_status)))
        set_row("eid", sim.eid or "—")
        set_row("removability", C.REMOVABILITY_LABELS.get(sim.remoability, "Unknown"))
        set_row("gid1", sim.gid1)
        set_row("gid2", sim.gid2)

        unlock = self.modem.unlock_required if self.modem else 0
        self._lock_row.value_label.set_text(C.LOCK_LABELS.get(unlock, str(unlock)))
        retries = self.modem.unlock_retries if self.modem else {}
        self._retries_row.value_label.set_text(
            ", ".join(f"{C.LOCK_LABELS.get(lock, lock)}: {count}"
                      for lock, count in sorted(retries.items())) or "—")
        self._unlock_row.set_visible(unlock not in (0, 1))

        self._refresh_preferred(sim)
        self._refresh_emergency(sim)

    def _refresh_preferred(self, sim: Sim) -> None:
        self._pref_list.clear()
        networks = sim.preferred_networks
        if not networks:
            self._pref_list.add(banner("No preferred networks are stored.", "info"))
            return
        for code, techs in networks[:8]:
            row = Adw.ActionRow(title=code, subtitle=C.mode_bits_label(techs))
            self._pref_list.add(row)
        if len(networks) > 8:
            self._pref_list.add(banner(f"{len(networks) - 8} more entries", "info"))

    def _refresh_emergency(self, sim: Sim) -> None:
        self._emergency_list.clear()
        numbers = sim.emergency_numbers
        if not numbers:
            self._emergency_list.add(banner("The SIM does not report emergency numbers.", "info"))
            return
        for number in numbers:
            self._emergency_list.add(Adw.ActionRow(title=number))

    # -- actions ----------------------------------------------------------

    def _on_unlock(self) -> None:
        if self.sim is None:
            return

        def unlocked(pin: str) -> None:
            def task():
                self.sim.send_pin(pin)

            run_in_background(self.window, task, self._done("Unlock"))

        prompt(self.window, "Unlock SIM", "Enter the SIM PIN.", "Unlock",
               unlocked, password=True)

    def _on_enable_pin(self) -> None:
        if self.sim is None:
            return
        locks = self.modem.enabled_facility_locks if self.modem else 0
        enabled_now = bool(locks & 1)

        dialog = Adw.AlertDialog(
            heading="PIN protection",
            body="Ask for the SIM PIN when the modem boots.",
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)

        switch_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        label = Gtk.Label(label="Require PIN at boot", xalign=0, hexpand=True)
        switch = Gtk.Switch(active=enabled_now, valign=Gtk.Align.CENTER)
        switch_box.append(label)
        switch_box.append(switch)

        entry = Gtk.PasswordEntry()
        entry.set_show_peek_icon(True)
        entry.set_placeholder_text("SIM PIN")

        box.append(switch_box)
        box.append(entry)
        dialog.set_extra_child(box)
        dialog.add_cancel("Cancel")
        dialog.add_response("ok", "Apply")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")

        def answered(_dialog, response: str) -> None:
            if response != "ok":
                return
            pin = entry.get_text()
            if not pin:
                toast(self.window, "Enter the SIM PIN")
                return
            target = switch.get_active()
            self._run(lambda: self.sim.enable_pin(pin, target), "PIN setting")

        dialog.connect("response", answered)
        dialog.present(self.get_root() or self.window)

    def _on_change_pin(self) -> None:
        if self.sim is None:
            return

        def old_entered(old: str) -> None:
            prompt(self.window, "New PIN", "Enter the new SIM PIN.", "Change",
                   lambda new: self._run(
                       lambda: self.sim.change_pin(old, new), "PIN change"),
                   password=True)

        prompt(self.window, "Current PIN", "Enter the current SIM PIN.", "Next",
               old_entered, password=True)

    def _on_edit_preferred(self) -> None:
        if self.sim is None:
            return
        current = "\n".join(code for code, _techs in self.sim.preferred_networks)

        dialog = Adw.AlertDialog(
            heading="Preferred networks",
            body="One MCCMNC per line, for example 28603.",
        )
        view = Gtk.TextView()
        view.set_monospace(True)
        view.get_buffer().set_text(current)
        width, height = dialog_size(280, 220)
        box = Gtk.ScrolledWindow()
        box.set_child(view)
        box.set_size_request(width, height)
        dialog.set_extra_child(box)
        dialog.add_cancel("Cancel")
        dialog.add_response("ok", "Save")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)

        def answered(_dialog, response: str) -> None:
            if response != "ok":
                return
            buffer = view.get_buffer()
            text = buffer.get_text(buffer.get_start_iter(), buffer.get_end_iter(), False)
            entries = []
            for line in text.splitlines():
                code = line.strip()
                if code:
                    entries.append((code, 0x3FFF))
            self._run(lambda: self.sim.set_preferred_networks(entries),
                      "Preferred networks", reload=True)

        dialog.connect("response", answered)
        dialog.present(self.get_root() or self.window)

    def _run(self, task, label: str, reload: bool = False) -> None:
        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"{label} failed: {error}")
            else:
                toast(self.window, f"{label} updated")
                if reload:
                    self.reload()

        run_in_background(self.window, task, done)

    def _done(self, label: str):
        def callback(_result, error) -> None:
            if error is not None:
                toast(self.window, f"{label} failed: {error}")
            else:
                toast(self.window, f"{label} succeeded")
                self.reload()

        return callback
