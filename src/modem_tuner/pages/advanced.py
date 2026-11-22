"""Advanced: SAR, EPS settings, AT passthrough, firmware and cell broadcast."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import constants as C  # noqa: E402
from ..client import (MODEM_3GPP, MODEM_CELL_BROADCAST, MODEM_MESSAGING,
                      MODEM_SAR, Modem)  # noqa: E402
from ..widgets import (RowList, banner, button_row, combo_row, monospace,  # noqa: E402
                       panel, prompt, run_in_background, toast, value_row)
from ._base import Page  # noqa: E402

EPS_UE_MODE_LABELS = C.EPS_UE_MODE_LABELS
SAR_LEVELS = [str(level) for level in range(0, 11)]


class AdvancedPage(Page):
    interfaces = (MODEM_3GPP, MODEM_SAR, MODEM_MESSAGING, MODEM_CELL_BROADCAST)

    def __init__(self, window) -> None:
        super().__init__(window, title="Advanced",
                         icon_name="applications-engineering-symbolic",
                         name="advanced")

        self._eps_group = Adw.PreferencesGroup(
            title="EPS settings",
            description="Controls how the modem attaches to LTE and 5G.",
        )
        self.add(self._eps_group)

        self._eps_row = Adw.ComboRow(title="EPS UE mode of operation")
        self._eps_row.set_model(Gtk.StringList.new(list(EPS_UE_MODE_LABELS.values())))
        self._eps_values = list(EPS_UE_MODE_LABELS.keys())
        self._eps_row.connect("notify::selected", self._on_eps)
        self._eps_group.add(self._eps_row)

        self._eps_group.add(button_row(
            "Re-attach packet service", "Detach and attach the data connection.",
            "Re-attach", self._on_reattach))

        self._eps_group.add(button_row(
            "Show initial bearer settings", "The APN the modem uses on attach.",
            "Show", self._show_initial_bearer))
        self._bearer_view = monospace("—")
        self._eps_group.add(panel(self._bearer_view))

        # -- NR5G ----------------------------------------------------------
        self._nr_group = Adw.PreferencesGroup(
            title="5G NR",
            description="Registration settings reported by the modem.",
        )
        self.add(self._nr_group)
        self._nr_view = monospace("Not reported by this modem")
        self._nr_group.add(panel(self._nr_view))

        # -- SAR -----------------------------------------------------------
        self._sar_group = Adw.PreferencesGroup(
            title="SAR (specific absorption rate)",
            description="Caps transmit power to meet exposure limits.",
        )
        self.add(self._sar_group)
        self._sar_state = value_row("SAR control", "—")
        self._sar_group.add(self._sar_state)
        self._sar_level = value_row("Power level", "—")
        self._sar_group.add(self._sar_level)
        self._sar_group.add(banner(
            "These two calls are blocked by the system bus policy on this device "
            "(org.freedesktop.ModemManager1.Modem.Sar.*). They are shown so the "
            "capability is visible; enabling them needs a D-Bus policy change.",
            "info"))
        self._sar_enable = Adw.SwitchRow(title="Enable SAR control")
        self._sar_enable.connect("notify::active", self._on_sar_enable)
        self._sar_group.add(self._sar_enable)
        self._sar_level_row = combo_row(
            "Power level", "Lower values reduce transmit power.",
            SAR_LEVELS, 9, self._on_sar_level)
        self._sar_group.add(self._sar_level_row)

        # -- Cell broadcast ------------------------------------------------
        self._cb_group = Adw.PreferencesGroup(
            title="Cell broadcast channels",
            description="Used for public warning systems.",
        )
        self.add(self._cb_group)
        self._cb_view = monospace("—")
        self._cb_group.add(panel(self._cb_view))
        self._cb_entry = Adw.EntryRow(title="Channels")
        self._cb_entry.set_show_apply_button(True)
        self._cb_entry.set_tooltip_text("Ranges or IDs, e.g. 4370-4380 or 4370")
        self._cb_entry.connect("apply", lambda _r: self._apply_channels())
        self._cb_group.add(self._cb_entry)
        self._cb_group.add(button_row(
            "Clear channels", "Unsubscribe from every channel.", "Clear",
            self._on_clear_channels, destructive=True))

        # -- Messaging -----------------------------------------------------
        self._msg_group = Adw.PreferencesGroup(
            title="Messaging",
            description="Messages stored on the SIM or modem.")
        self.add(self._msg_group)
        self._storage_row = value_row("Default storage", "—")
        self._msg_group.add(self._storage_row)
        self._supported_row = value_row("Supported storages", "—")
        self._msg_group.add(self._supported_row)
        self._msg_group.add(button_row(
            "List messages", "Read the messages stored on the modem.", "List",
            self._list_messages))
        self._msg_list = RowList()
        self._msg_group.add(self._msg_list)
        self._msg_group.add(button_row(
            "Send message", "Create an SMS.", "Send…", self._on_send_message))

        # -- Firmware ------------------------------------------------------
        self._fw_group = Adw.PreferencesGroup(title="Firmware")
        self.add(self._fw_group)
        self._fw_group.add(button_row(
            "List firmware images", "Images installed on the modem.", "List",
            self._list_firmware))
        self._fw_list = RowList()
        self._fw_group.add(self._fw_list)

        # -- AT passthrough ------------------------------------------------
        self._at_group = Adw.PreferencesGroup(
            title="AT command passthrough",
            description="Sends a raw AT command to the modem. Most builds require "
                        "ModemManager debug mode (--debug) for this to be allowed.",
        )
        self.add(self._at_group)
        self._at_row = Adw.EntryRow(title="AT command")
        self._at_row.set_text("ATI")
        self._at_row.set_show_apply_button(True)
        self._at_row.connect("apply", lambda _r: self._send_at())
        self._at_group.add(self._at_row)
        self._at_output = monospace("No output yet")
        self._at_group.add(panel(self._at_output))

        # -- Device info ---------------------------------------------------
        self._device_group = Adw.PreferencesGroup(title="Device")
        self.add(self._device_group)
        self._device_group.add(button_row(
            "Show simple status", "ModemManager's aggregated connection state.",
            "Show", self._show_simple_status))
        self._simple_view = monospace("—")
        self._device_group.add(panel(self._simple_view))
        self._device_group.add(button_row(
            "Factory reset", "Wipes modem configuration. Requires the factory code.",
            "Reset…", self._on_factory_reset, destructive=True))

    # -- binding ----------------------------------------------------------

    def refresh(self) -> None:
        modem = self.modem
        if modem is None:
            return
        self._updating = True
        try:
            self._refresh_eps(modem)
            self._refresh_nr(modem)
            self._refresh_sar(modem)
            self._refresh_channels(modem)
            self._refresh_messaging(modem)
        finally:
            self._updating = False

    def _refresh_eps(self, modem: Modem) -> None:
        mode = modem.eps_ue_mode_operation
        self._eps_row.set_selected(
            self._eps_values.index(mode) if mode in self._eps_values else -1)

    def _refresh_nr(self, modem: Modem) -> None:
        settings = modem.nr5g_registration_settings
        if not settings:
            self._nr_view.set_text("Not reported by this modem")
        else:
            self._nr_view.set_text("\n".join(
                f"{key}: {value}" for key, value in sorted(settings.items())))

    def _refresh_sar(self, modem: Modem) -> None:
        self._sar_state.value_label.set_text("Enabled" if modem.sar_state else "Disabled")
        self._sar_level.value_label.set_text(str(modem.sar_power_level))
        self._sar_enable.set_active(modem.sar_state)
        self._sar_level_row.set_selected(min(10, max(0, modem.sar_power_level)))

    def _refresh_channels(self, modem: Modem) -> None:
        channels = modem.cell_broadcast_channels
        if not channels:
            self._cb_view.set_text("No channels subscribed")
            self._cb_entry.set_text("")
        else:
            text = ", ".join(f"{a}-{b}" if a != b else str(a) for a, b in channels)
            self._cb_view.set_text(text)
            self._cb_entry.set_text(text)

    def _refresh_messaging(self, modem: Modem) -> None:
        storage = modem.default_storage
        self._storage_row.value_label.set_text(
            C.STORAGE_LABELS.get(storage, str(storage)))
        supported = modem.supported_storages
        self._supported_row.value_label.set_text(
            ", ".join(C.STORAGE_LABELS.get(s, str(s)) for s in supported) or "—")

    # -- actions ----------------------------------------------------------

    def _on_eps(self, row, _param) -> None:
        if self._updating or self.modem is None:
            return
        index = row.get_selected()
        if index < 0 or index >= len(self._eps_values):
            return
        mode = self._eps_values[index]

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"EPS mode failed: {error}")
            else:
                toast(self.window, f"EPS mode set to {EPS_UE_MODE_LABELS.get(mode, mode)}")
                self.refresh()

        run_in_background(self.window,
                          lambda: self.modem.set_eps_ue_mode_operation(mode), done)

    def _on_reattach(self) -> None:
        if self.modem is None:
            return

        def task():
            detached = C.PACKET_SERVICE_STATE.get(1, 1)
            attached = C.PACKET_SERVICE_STATE.get(2, 2)
            self.modem.set_packet_service_state(detached)
            self.modem.set_packet_service_state(attached)

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Re-attach failed: {error}")
            else:
                toast(self.window, "Packet service re-attached")

        run_in_background(self.window, task, done)

    def _show_initial_bearer(self) -> None:
        if self.modem is None:
            return
        settings = self.modem.initial_eps_bearer_settings
        if not settings:
            self._bearer_view.set_text("No initial bearer settings")
            return
        self._bearer_view.set_text("\n".join(
            f"{key}: {value}" for key, value in sorted(settings.items())))

    def _on_sar_enable(self, row, _param) -> None:
        if self._updating or self.modem is None:
            return

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"SAR enable failed: {error}")
            else:
                toast(self.window, "SAR state changed")

        run_in_background(self.window, lambda: self.modem.sar_enable(row.get_active()), done)

    def _on_sar_level(self, index: int) -> None:
        if self._updating or self.modem is None:
            return

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"SAR level failed: {error}")
            else:
                toast(self.window, f"SAR level set to {index}")

        run_in_background(self.window, lambda: self.modem.sar_set_power_level(index), done)

    def _apply_channels(self) -> None:
        if self.modem is None:
            return
        channels = []
        try:
            for part in self._cb_entry.get_text().split(","):
                part = part.strip()
                if not part:
                    continue
                if "-" in part:
                    start, end = part.split("-", 1)
                    channels.append((int(start), int(end)))
                else:
                    value = int(part)
                    channels.append((value, value))
        except ValueError:
            toast(self.window,
                  "Use ranges like 4370-4380 or single channel IDs")
            return

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Channels failed: {error}")
            else:
                toast(self.window, f"{len(channels)} channel ranges set")
                self.refresh()

        run_in_background(
            self.window,
            lambda: self.modem.set_cell_broadcast_channels(channels), done)

    def _on_clear_channels(self) -> None:
        if self.modem is None:
            return

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Clear channels failed: {error}")
            else:
                toast(self.window, "Channels cleared")
                self.refresh()

        run_in_background(self.window,
                          lambda: self.modem.set_cell_broadcast_channels([]), done)

    def _list_firmware(self) -> None:
        self._fw_list.clear()
        if self.modem is None:
            return

        def done(result, error) -> None:
            if error is not None:
                self._fw_list.add(banner(f"Cannot list firmware: {error}"))
                return
            images = result or []
            if not images:
                self._fw_list.add(banner("No firmware images reported.", "info"))
                return
            for image in images:
                row = Adw.ActionRow(
                    title=str(image.get("name") or "image"),
                    subtitle=str(image.get("version") or ""))
                if image.get("current"):
                    row.add_suffix(Gtk.Label(label="current"))
                else:
                    unique_id = image.get("unique-id")
                    if unique_id:
                        use = Gtk.Button(label="Use", valign=Gtk.Align.CENTER)
                        use.connect(
                            "clicked",
                            lambda _b, uid=unique_id: self._select_firmware(uid))
                        row.add_suffix(use)
                self._fw_list.add(row)

        run_in_background(self.window, self.modem.list_firmware, done)

    def _select_firmware(self, unique_id: str) -> None:
        if self.modem is None:
            return

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Firmware select failed: {error}")
            else:
                toast(self.window, "Firmware image selected")
                self._list_firmware()

        run_in_background(
            self.window, lambda: self.modem.select_firmware(unique_id), done)

    def _list_messages(self) -> None:
        self._msg_list.clear()
        if self.modem is None:
            return

        def done(result, error) -> None:
            if error is not None:
                self._msg_list.add(banner(f"Cannot list messages: {error}"))
                return
            messages = result or []
            if not messages:
                self._msg_list.add(banner("No messages stored.", "info"))
                return
            for message in messages:
                row = Adw.ActionRow(
                    title=message.number or "(unknown number)",
                    subtitle=message.text or "")
                state = C.SMS_STATE_LABELS.get(message.state, str(message.state))
                row.add_suffix(Gtk.Label(label=state))
                self._msg_list.add(row)

        run_in_background(self.window, self.modem.messages, done)

    def _on_send_message(self) -> None:
        if self.modem is None:
            return
        dialog = Adw.AlertDialog(
            heading="Send message",
            body="Create an SMS on the modem.")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        number = Gtk.Entry()
        number.set_placeholder_text("Phone number")
        text = Gtk.Entry()
        text.set_placeholder_text("Message text")
        box.append(number)
        box.append(text)
        dialog.set_extra_child(box)
        dialog.add_cancel("Cancel")
        dialog.add_response("ok", "Send")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")

        def answered(_dialog, response: str) -> None:
            if response != "ok":
                return
            target = number.get_text().strip()
            body = text.get_text().strip()
            if not target or not body:
                toast(self.window, "Number and message text are required")
                return

            def done(_result, error) -> None:
                if error is not None:
                    toast(self.window, f"Send failed: {error}")
                else:
                    toast(self.window, "Message queued")
                    self._list_messages()

            run_in_background(
                self.window, lambda: self.modem.create_message(target, body), done)

        dialog.connect("response", answered)
        dialog.present(self.get_root() or self.window)

    def _send_at(self) -> None:
        if self.modem is None:
            return
        command = self._at_row.get_text().strip()
        if not command:
            return
        self._at_output.set_text("Sending…")

        def done(result, error) -> None:
            if error is not None:
                self._at_output.set_text(f"Failed: {error}")
            else:
                self._at_output.set_text(result or "(empty reply)")

        run_in_background(self.window, lambda: self.modem.command(command), done)

    def _show_simple_status(self) -> None:
        if self.modem is None:
            return
        self._simple_view.set_text("Reading…")

        def done(result, error) -> None:
            if error is not None:
                self._simple_view.set_text(f"Failed: {error}")
            else:
                self._simple_view.set_text("\n".join(
                    f"{key}: {value}" for key, value in sorted((result or {}).items())))

        run_in_background(self.window, self.modem.simple_status, done)

    def _on_factory_reset(self) -> None:
        if self.modem is None:
            return

        def do_reset(code: str) -> None:
            def done(_result, error) -> None:
                if error is not None:
                    toast(self.window, f"Factory reset failed: {error}")
                else:
                    toast(self.window, "Factory reset requested")

            run_in_background(self.window, lambda: self.modem.factory_reset(code), done)

        prompt(self.window, "Factory reset",
               "This erases the modem's stored configuration. Enter the factory "
               "code, or leave it empty if the modem does not require one.",
               "Reset", do_reset, password=True)
