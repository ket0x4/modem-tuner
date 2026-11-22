"""Network: manual operator selection, scan results and USSD."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import constants as C  # noqa: E402
from ..client import MODEM_3GPP, MODEM_3GPP_USSD, ModemError  # noqa: E402
from ..widgets import (RowList, banner, button_row, confirm, monospace,  # noqa: E402
                       panel, prompt, run_in_background, toast, value_row)
from ._base import Page  # noqa: E402


class NetworkPage(Page):
    interfaces = (MODEM_3GPP, MODEM_3GPP_USSD)

    def __init__(self, window) -> None:
        super().__init__(window, title="Network",
                         icon_name="network-wireless-symbolic", name="network")

        self._reg_group = Adw.PreferencesGroup(title="Registration")
        self.add(self._reg_group)
        self._operator_row = value_row("Operator", "—")
        self._reg_group.add(self._operator_row)
        self._reg_state_row = value_row("State", "—")
        self._reg_group.add(self._reg_state_row)
        self._reg_tech_row = value_row("Technology", "—")
        self._reg_group.add(self._reg_tech_row)

        self._auto_row = button_row(
            "Automatic selection", "Let the modem pick the best network.",
            "Enable", self._on_auto)
        self._reg_group.add(self._auto_row)

        self._scan_group = Adw.PreferencesGroup(
            title="Available networks",
            description="A scan takes 30 seconds or more and briefly interrupts data.",
        )
        self.add(self._scan_group)
        self._scan_button = Gtk.Button(label="Scan now")
        self._scan_button.add_css_class("suggested-action")
        self._scan_button.connect("clicked", lambda _b: self._on_scan())
        self._scan_group.add(panel(self._scan_button))
        self._scan_list = RowList()
        self._scan_group.add(self._scan_list)

        self._ussd_group = Adw.PreferencesGroup(
            title="USSD", description="Operator codes such as *100# for balance.")
        self.add(self._ussd_group)
        self._ussd_state_row = value_row("Session state", "—")
        self._ussd_group.add(self._ussd_state_row)
        self._ussd_request = monospace("—")
        self._ussd_group.add(panel(self._ussd_request))
        self._ussd_row = Adw.EntryRow(title="USSD code")
        self._ussd_row.set_text("*100#")
        self._ussd_row.set_show_apply_button(True)
        self._ussd_row.connect("apply", lambda _r: self._send_ussd())
        self._ussd_group.add(self._ussd_row)
        self._ussd_reply = monospace("No session")
        self._ussd_group.add(panel(self._ussd_reply))
        self._ussd_group.add(button_row(
            "Reply to USSD session", "Only used when the operator asks a question.",
            "Reply", self._on_ussd_reply))
        self._ussd_group.add(button_row(
            "Cancel USSD session", "", "Cancel", self._on_ussd_cancel,
            destructive=True))

    def refresh(self) -> None:
        modem = self.modem
        if modem is None:
            return
        self._operator_row.value_label.set_text(
            f"{modem.operator_name} ({modem.operator_code})" if modem.operator_code
            else "—")
        self._reg_state_row.value_label.set_text(
            C.REGISTRATION_LABELS.get(modem.registration_state, "—"))
        self._reg_tech_row.value_label.set_text(
            C.access_technology_short(modem.access_technologies) or "—")
        self._ussd_state_row.value_label.set_text(
            C.USSD_STATE_LABELS.get(modem.ussd_state, "—"))
        request = modem.ussd_network_request or modem.ussd_network_notification
        self._ussd_request.set_text(request or "—")

    # -- actions ----------------------------------------------------------

    def _on_auto(self) -> None:
        self._register("", "Automatic network selection enabled")

    def _register(self, operator_id: str, success_message: str) -> None:
        if self.modem is None:
            return
        try:
            connected = any(b.connected for b in self.modem.bearers())
        except ModemError:
            connected = False
        if connected:
            confirm(
                self.window, "Disconnect mobile data?",
                "Changing the network selection needs the data connection to "
                "drop first. Reconnect mobile data afterwards if it does not "
                "come back on its own.",
                "Disconnect and continue",
                lambda: self._do_register(operator_id, success_message),
                destructive=True)
            return
        self._do_register(operator_id, success_message)

    def _do_register(self, operator_id: str, success_message: str) -> None:
        if self.modem is None:
            return

        def task() -> None:
            self.modem.disconnect_bearers()
            self.modem.register(operator_id)

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Registration failed: {error}")
            else:
                toast(self.window, success_message)
                self.refresh()

        run_in_background(self.window, task, done, self._auto_row.button)

    def _on_scan(self) -> None:
        if self.modem is None:
            return
        self._scan_button.set_sensitive(False)
        toast(self.window, "Scanning networks, this can take a minute…")

        def done(result, error) -> None:
            self._scan_button.set_sensitive(True)
            if error is not None:
                toast(self.window, f"Scan failed: {error}")
                return
            self._show_scan_results(result or [])

        run_in_background(self.window, self.modem.scan_networks, done)

    def _show_scan_results(self, networks: list[dict]) -> None:
        self._scan_list.clear()
        if not networks:
            self._scan_list.add(banner("No networks found.", "info"))
            return
        for network in networks:
            name = str(network.get("operator-long") or network.get("operator-short") or "Unknown")
            code = str(network.get("operator-code") or "")
            status = C.NETWORK_SCAN_STATUS_LABELS.get(int(network.get("status", 0)), "")
            tech = C.access_technology_short(int(network.get("access-technologies", 0)))
            subtitle = " · ".join(part for part in (code, status, tech) if part)
            row = Adw.ActionRow(title=name, subtitle=subtitle or None)
            button = Gtk.Button(label="Register", valign=Gtk.Align.CENTER)
            button.connect("clicked", lambda _b, n=code: self._register_manual(n))
            row.add_suffix(button)
            self._scan_list.add(row)

    def _register_manual(self, operator_code: str) -> None:
        if not operator_code:
            return
        self._register(operator_code, f"Registering on {operator_code}…")

    def _send_ussd(self) -> None:
        if self.modem is None:
            return
        code = self._ussd_row.get_text().strip()
        if not code:
            return
        self._ussd_reply.set_text("Sending…")

        def done(result, error) -> None:
            if error is not None:
                self._ussd_reply.set_text(f"Failed: {error}")
            else:
                self._ussd_reply.set_text(result or "(empty reply)")

        run_in_background(self.window, lambda: self.modem.ussd_initiate(code), done)

    def _on_ussd_reply(self) -> None:
        if self.modem is None:
            return

        def accepted(text: str) -> None:
            def done(result, error) -> None:
                if error is not None:
                    self._ussd_reply.set_text(f"Failed: {error}")
                else:
                    self._ussd_reply.set_text(result or "(empty reply)")

            run_in_background(self.window, lambda: self.modem.ussd_respond(text), done)

        prompt(self.window, "USSD reply", "Answer the operator question.", "Send",
               accepted)

    def _on_ussd_cancel(self) -> None:
        if self.modem is None:
            return

        def done(_result, error) -> None:
            self._ussd_reply.set_text("Cancelled" if error is None else f"Failed: {error}")

        run_in_background(self.window, self.modem.ussd_cancel, done)
