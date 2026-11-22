"""Signal: poll rate, per-technology measurements and thresholds."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import constants as C  # noqa: E402
from ..client import MODEM_SIGNAL, Modem  # noqa: E402
from ..widgets import (banner, monospace, panel, run_in_background, spin_row,  # noqa: E402
                       toast, value_row)
from ._base import Page  # noqa: E402

# ModemManager documents these keys per technology.
SIGNAL_FIELDS = {
    "lte": [("rssi", "RSSI (dBm)"), ("rsrp", "RSRP (dBm)"), ("rsrq", "RSRQ (dB)"),
            ("snr", "SNR (dB)"), ("timing-advance", "Timing advance")],
    "nr5g": [("rsrp", "RSRP (dBm)"), ("rsrq", "RSRQ (dB)"), ("snr", "SNR (dB)")],
    "umts": [("rscp", "RSCP (dBm)"), ("ecio", "Ec/Io (dB)")],
    "gsm": [("rssi", "RSSI (dBm)")],
    "cdma": [("ecio", "Ec/Io (dB)")],
    "evdo": [("ecio", "Ec/Io (dB)"), ("sinr", "SINR (dB)"),
             ("io", "Io (dBm)"), ("rssi", "RSSI (dBm)")],
}


class SignalPage(Page):
    interfaces = (MODEM_SIGNAL,)

    def __init__(self, window) -> None:
        super().__init__(window, title="Signal",
                         icon_name="network-wireless-symbolic", name="signal")
        self._rows: dict[str, Adw.ActionRow] = {}

        self._summary = Adw.PreferencesGroup(title="Overview")
        self.add(self._summary)
        self._quality = value_row("Signal quality", "—")
        self._summary.add(self._quality)
        self._tech = value_row("Access technology", "—")
        self._summary.add(self._tech)

        self._details = Adw.PreferencesGroup(
            title="Measurements",
            description="Values depend on the technology in use.",
        )
        self.add(self._details)

        self._rate_group = Adw.PreferencesGroup(
            title="Polling",
            description="0 disables periodic signal updates.",
        )
        self.add(self._rate_group)
        self._rate_row = spin_row(
            "Update rate (seconds)", "How often the modem refreshes signal values.",
            value=0, lower=0, upper=3600, step=5,
            on_change=self._on_rate_changed)
        self._rate_group.add(self._rate_row)

        self._threshold_group = Adw.PreferencesGroup(
            title="Thresholds",
            description="The modem reports updates when a measurement changes "
                        "by more than the threshold.",
        )
        self.add(self._threshold_group)
        self._rssi_row = spin_row(
            "RSSI change (dBm)",
            "Report when RSSI changes by this much. 0 disables the threshold.",
            value=0, lower=0, upper=50, step=1)
        self._threshold_group.add(self._rssi_row)
        self._error_row = Adw.SwitchRow(
            title="Error rate threshold",
            subtitle="Emit a signal when the error rate rises.")
        self._threshold_group.add(self._error_row)
        self._apply_thresholds = Gtk.Button(label="Apply thresholds")
        self._apply_thresholds.connect("clicked", lambda _b: self._on_thresholds_apply())
        self._threshold_group.add(panel(self._apply_thresholds))

        self._raw_group = Adw.PreferencesGroup(title="Raw values")
        self.add(self._raw_group)
        self._raw = monospace("—")
        self._raw_group.add(panel(self._raw))

    def on_bound(self, modem: Modem) -> None:
        if modem.has(MODEM_SIGNAL):
            self._revert_signal_rate(modem)

    def _revert_signal_rate(self, modem: Modem) -> None:
        """Stop ModemManager from polling signal on our behalf at 5 s.

        Every ModemManager restart leaves the rate at whatever was last set, and
        a non-zero rate keeps the modem awake. The user opts in from this page.
        """
        if modem.signal_rate != 0:
            try:
                modem.set_signal_rate(0)
            except Exception:  # noqa: BLE001
                pass

    def refresh(self) -> None:
        modem = self.modem
        if modem is None:
            return
        self._updating = True
        try:
            quality, recent = modem.signal_quality
            self._quality.value_label.set_text(
                f"{quality}%{' (live)' if recent else ' (cached)'}")
            self._tech.value_label.set_text(
                ", ".join(C.access_technology_names(modem.access_technologies)) or "—")
            self._rate_row.set_value(modem.signal_rate)
            thresholds = modem.signal_thresholds
            self._rssi_row.set_value(thresholds["rssi"])
            self._error_row.set_active(thresholds["error_rate"])
            self._refresh_details(modem)
        finally:
            self._updating = False

    def _refresh_details(self, modem: Modem) -> None:
        details = modem.signal_details
        if not details:
            if getattr(self, "_empty_row", None) is None:
                self._empty_row = banner(
                    "No measurements yet. Enable polling above to collect them.", "info")
                self._details.add(self._empty_row)
            self._raw.set_text("—")
            return

        if getattr(self, "_empty_row", None) is not None:
            self._details.remove(self._empty_row)
            self._empty_row = None

        for technology, values in details.items():
            fields = SIGNAL_FIELDS.get(technology)
            if fields is None:
                continue
            for key, label in fields:
                if key not in values:
                    continue
                row_key = f"{technology}.{key}"
                row = self._rows.get(row_key)
                if row is None:
                    row = value_row(label, "—", subtitle=technology.upper())
                    self._details.add(row)
                    self._rows[row_key] = row
                row.value_label.set_text(str(values[key]))

        lines = []
        for technology, values in details.items():
            lines.append(f"{technology.upper()}: " + " ".join(
                f"{key}={value}" for key, value in sorted(values.items())))
        self._raw.set_text("\n".join(lines) or "—")

    def _on_rate_changed(self, value: float) -> None:
        if self._updating or self.modem is None:
            return
        rate = int(value)

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Update rate failed: {error}")
            else:
                toast(self.window, "Update rate disabled" if rate == 0
                      else f"Signal polls every {rate} s")

        run_in_background(self.window, lambda: self.modem.set_signal_rate(rate), done)

    def _on_thresholds_apply(self) -> None:
        if self.modem is None:
            return
        thresholds = {
            "rssi-threshold": int(self._rssi_row.get_value()),
            "error-rate-threshold": self._error_row.get_active(),
        }

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Thresholds failed: {error}")
            else:
                toast(self.window, "Thresholds updated")

        run_in_background(self.window,
                          lambda: self.modem.set_signal_thresholds(thresholds), done)
