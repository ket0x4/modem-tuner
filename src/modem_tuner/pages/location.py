"""Location: GPS, AGPS sources and one-shot position fix."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from ..client import MODEM_LOCATION  # noqa: E402
from ..widgets import (button_row, monospace, panel, run_in_background,  # noqa: E402
                       spin_row, toast, value_row)
from ._base import Page  # noqa: E402

SOURCE_LABELS = [
    (1, "3GPP cell info", "network-cellular-symbolic"),
    (4, "GPS NMEA", "find-location-symbolic"),
    (2, "GPS raw", "find-location-symbolic"),
    (32, "AGPS MSA", "find-location-symbolic"),
    (64, "AGPS MSB", "find-location-symbolic"),
    (8, "CDMA base station", "network-cellular-symbolic"),
]

CAPABILITY_LABELS = [
    (1, "3GPP"),
    (2, "GPS raw"),
    (4, "GPS NMEA"),
    (8, "CDMA BS"),
    (16, "GPS unmanaged"),
    (32, "AGPS MSA"),
    (64, "AGPS MSB"),
]


class LocationPage(Page):
    interfaces = (MODEM_LOCATION,)

    def __init__(self, window) -> None:
        super().__init__(window, title="Location",
                         icon_name="find-location-symbolic", name="location")
        self._checks: dict[int, Gtk.CheckButton] = {}

        self._caps_group = Adw.PreferencesGroup(title="Capabilities")
        self.add(self._caps_group)
        self._caps_row = value_row("Supported", "—")
        self._caps_group.add(self._caps_row)

        self._source_group = Adw.PreferencesGroup(
            title="Enabled sources",
            description="Enabling a source powers the GPS receiver and increases "
                        "battery use. Turn everything off when not in use.",
        )
        self.add(self._source_group)

        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(2)
        flow.set_row_spacing(4)
        flow.set_column_spacing(4)
        flow.set_margin_top(8)
        flow.set_margin_bottom(8)
        flow.set_margin_start(12)
        flow.set_margin_end(12)
        for value, label, _icon in SOURCE_LABELS:
            check = Gtk.CheckButton(label=label)
            check.add_css_class("card")
            self._checks[value] = check
            flow.append(check)
        self._source_group.add(flow)

        self._signals_row = Adw.SwitchRow(
            title="Expose location via D-Bus signals",
            subtitle="Needed by some applications, drains more power.")
        self._source_group.add(self._signals_row)

        self._source_group.add(button_row(
            "Apply sources", "Start or stop the selected sources.", "Apply",
            self._apply_sources))

        self._fix_group = Adw.PreferencesGroup(title="Position")
        self.add(self._fix_group)
        self._fix_group.add(button_row(
            "Get a position fix", "Reads the last known position. Enable GPS NMEA "
            "first for a fresh fix.", "Fetch", self._fetch))
        self._position = monospace("No fix yet")
        self._fix_group.add(panel(self._position))

        self._agps_group = Adw.PreferencesGroup(title="Assisted GPS")
        self.add(self._agps_group)
        self._supl_row = Adw.EntryRow(title="SUPL server")
        self._supl_row.set_text("")
        self._supl_row.set_show_apply_button(True)
        self._supl_row.connect("apply", lambda _r: self._apply_supl())
        self._agps_group.add(self._supl_row)
        self._refresh_row = spin_row(
            "GPS refresh rate (seconds)", "0 uses the modem default.",
            value=0, lower=0, upper=3600, step=30,
            on_change=self._apply_refresh)
        self._agps_group.add(self._refresh_row)

        self._servers_group = Adw.PreferencesGroup(title="Assistance data servers")
        self.add(self._servers_group)
        self._servers = monospace("—")
        self._servers_group.add(panel(self._servers))

    def refresh(self) -> None:
        modem = self.modem
        if modem is None or not modem.has(MODEM_LOCATION):
            return
        self._updating = True
        try:
            capabilities = modem.location_capabilities
            self._caps_row.value_label.set_text(
                ", ".join(label for value, label in CAPABILITY_LABELS
                          if capabilities & value) or "none")
            enabled = modem.location_enabled
            for value, check in self._checks.items():
                check.set_active(bool(enabled & value))
            self._signals_row.set_active(modem.location_signals)
            self._supl_row.set_text(modem.supl_server)
            self._refresh_row.set_value(modem.gps_refresh_rate)
            servers = modem.assistance_data_servers
            self._servers.set_text(
                "\n".join(servers) if servers else "None configured")
        finally:
            self._updating = False

    def _apply_sources(self) -> None:
        if self.modem is None:
            return
        sources = 0
        for value, check in self._checks.items():
            if check.get_active():
                sources |= value
        signals = self._signals_row.get_active()

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Location setup failed: {error}")
            else:
                toast(self.window, "Location sources updated" if sources
                      else "Location disabled")
                self.refresh()

        run_in_background(self.window,
                          lambda: self.modem.location_setup(sources, signals), done)

    def _fetch(self) -> None:
        if self.modem is None:
            return
        self._position.set_text("Reading…")

        def done(result, error) -> None:
            if error is not None:
                self._position.set_text(f"Failed: {error}")
                return
            self._position.set_text(_format_location(result or {}))

        run_in_background(self.window, self.modem.get_location, done)

    def _apply_supl(self) -> None:
        if self.modem is None:
            return
        server = self._supl_row.get_text().strip()

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"SUPL server failed: {error}")
            else:
                toast(self.window, "SUPL server updated")

        run_in_background(self.window, lambda: self.modem.set_supl_server(server), done)

    def _apply_refresh(self, value: float) -> None:
        if self._updating or self.modem is None:
            return
        rate = int(value)

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Refresh rate failed: {error}")

        run_in_background(self.window, lambda: self.modem.set_gps_refresh_rate(rate), done)


def _format_location(values: dict) -> str:
    if not values:
        return "No data reported"
    lines = []
    for source, value in sorted(values.items()):
        label = next((name for bit, name, _i in SOURCE_LABELS if bit == source),
                     f"source {source}")
        if isinstance(value, (list, tuple)):
            value = " ".join(str(v) for v in value)
        lines.append(f"{label}: {value}")
    return "\n".join(lines)
