"""Live modem status: identity, registration, signal and bearers."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from .. import constants as C  # noqa: E402
from ..client import MODEM_3GPP, MODEM_IFACE, MODEM_SIGNAL, Modem  # noqa: E402
from ..widgets import RowList, value_row  # noqa: E402


class StatusPage(Adw.PreferencesPage):
    def __init__(self, window) -> None:
        super().__init__(
            title="Status", icon_name="network-modem-symbolic",
            name="status",
        )
        self.window = window
        self.modem: Modem | None = None

        self._conn_group = Adw.PreferencesGroup(title="Connection")
        self.add(self._conn_group)

        self._signal_group = Adw.PreferencesGroup(title="Signal")
        self.add(self._signal_group)

        self._device_group = Adw.PreferencesGroup(title="Device")
        self.add(self._device_group)

        self._bearer_group = Adw.PreferencesGroup(title="Bearers")
        self.add(self._bearer_group)

        self._rows: dict[str, Adw.ActionRow] = {}

        for key, title in [
            ("state", "Modem state"),
            ("operator", "Operator"),
            ("registration", "Registration"),
            ("packet", "Packet service"),
            ("technologies", "Access technology"),
            ("quality", "Signal quality"),
            ("unlock", "SIM lock"),
            ("power", "Power state"),
        ]:
            group = self._conn_group if key in ("state", "operator", "registration", "packet") else self._signal_group
            row = value_row(title, "—")
            group.add(row)
            self._rows[key] = row

        for key, title in [
            ("manufacturer", "Manufacturer"),
            ("model", "Model"),
            ("revision", "Firmware"),
            ("plugin", "Plugin"),
            ("imei", "IMEI"),
            ("equipment", "Equipment ID"),
            ("device_id", "Device ID"),
            ("ports", "Ports"),
            ("drivers", "Drivers"),
        ]:
            row = value_row(title, "—")
            self._device_group.add(row)
            self._rows[key] = row

        self._bearer_list = RowList()
        self._bearer_group.add(self._bearer_list)

        for interface in (MODEM_IFACE, MODEM_3GPP, MODEM_SIGNAL):
            self._pending_interfaces = getattr(self, "_pending_interfaces", [])
            self._pending_interfaces.append(interface)

    def bind(self, modem: Modem) -> None:
        self.modem = modem
        for interface in self._pending_interfaces:
            if modem.has(interface):
                modem.signal(interface, "g-properties-changed", self._on_change)
        self.refresh()

    def _on_change(self, _proxy=None, _changed=None, _invalidated=None) -> None:
        # Signals arrive for every property; coalescing keeps a burst of
        # signal-strength updates from redrawing the page each time.
        if getattr(self, "_scheduled", False):
            return
        self._scheduled = True
        GLib.timeout_add(250, self._deferred_refresh)

    def _deferred_refresh(self) -> bool:
        self._scheduled = False
        self.refresh()
        return GLib.SOURCE_REMOVE

    def refresh(self) -> None:
        modem = self.modem
        if modem is None:
            return

        def set_row(key: str, text: str) -> None:
            row = self._rows.get(key)
            if row is not None:
                row.value_label.set_text(text or "—")

        state = modem.state
        set_row("state", C.STATE_LABELS.get(state, str(state)))
        set_row("operator", f"{modem.operator_name} ({modem.operator_code})"
                if modem.operator_code else modem.operator_name)
        set_row("registration", C.REGISTRATION_LABELS.get(modem.registration_state, "—"))
        set_row("packet", C.PACKET_SERVICE_LABELS.get(modem.packet_service_state, "—"))

        technologies = C.access_technology_names(modem.access_technologies)
        set_row("technologies", ", ".join(technologies))

        quality, recent = modem.signal_quality
        set_row("quality", f"{quality}%{' (live)' if recent else ' (cached)'}")

        unlock = modem.unlock_required
        lock_label = C.LOCK_LABELS.get(unlock, str(unlock))
        if unlock not in (0, 1) and modem.state in C.NETWORK_STATES:
            # ModemManager keeps the last lock capability in UnlockRequired even
            # while the modem is registered and connected, so showing "SIM PIN2"
            # on a working connection is misleading. Say it is locked only while
            # the modem actually is.
            lock_label = f"{lock_label} (not blocking)"
        set_row("unlock", lock_label)
        set_row("power", C.POWER_STATE_LABELS.get(modem.power_state, "—"))

        set_row("manufacturer", modem.manufacturer)
        set_row("model", modem.model)
        set_row("revision", modem.revision)
        set_row("plugin", modem.plugin)
        set_row("imei", modem.imei or modem.equipment_identifier)
        set_row("equipment", modem.equipment_identifier)
        set_row("device_id", modem.device_identifier)
        set_row("ports", ", ".join(name for name, _kind in modem.ports))
        set_row("drivers", ", ".join(modem.drivers))

        self._refresh_bearers()

    def _refresh_bearers(self) -> None:
        self._bearer_list.clear()
        modem = self.modem
        if modem is None or not modem.has(MODEM_IFACE):
            return
        for path in modem.list_bearers():
            from ..client import BUS_NAME

            import gi as _gi
            _gi.require_version("Gio", "2.0")
            from gi.repository import Gio

            proxy = Gio.DBusProxy.new_for_bus_sync(
                Gio.BusType.SYSTEM, Gio.DBusProxyFlags.DO_NOT_AUTO_START, None,
                BUS_NAME, path, "org.freedesktop.ModemManager1.Bearer", None,
            )
            interface = proxy.get_cached_property("Interface")
            connected = proxy.get_cached_property("Connected")
            apn = ""
            try:
                settings = proxy.get_cached_property("Properties")
                if settings is not None:
                    apn = dict(settings.unpack()).get("apn", "")
            except Exception:  # noqa: BLE001
                pass
            row = Adw.ActionRow(
                title=path.rsplit("/", 1)[-1],
                subtitle=f"APN {apn} · {interface.unpack() if interface else '—'}",
            )
            status = Gtk.Label(label="connected" if connected and connected.unpack() else "disconnected")
            status.add_css_class("dim-label")
            row.add_suffix(status)
            self._bearer_list.add(row)
