"""Thin ModemManager client over the system bus.

Everything goes through Gio.DBusProxy so property changes arrive as signals and
no polling is needed. The interface names and signatures match ModemManager
1.25 as introspected on the device.
"""

from __future__ import annotations

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gio, GLib  # noqa: E402

BUS_NAME = "org.freedesktop.ModemManager1"
ROOT_PATH = "/org/freedesktop/ModemManager1"

MODEM_IFACE = "org.freedesktop.ModemManager1.Modem"
MODEM_3GPP = "org.freedesktop.ModemManager1.Modem.Modem3gpp"
MODEM_3GPP_PROFILE = "org.freedesktop.ModemManager1.Modem.Modem3gpp.ProfileManager"
MODEM_3GPP_USSD = "org.freedesktop.ModemManager1.Modem.Modem3gpp.Ussd"
MODEM_SIGNAL = "org.freedesktop.ModemManager1.Modem.Signal"
MODEM_SAR = "org.freedesktop.ModemManager1.Modem.Sar"
MODEM_LOCATION = "org.freedesktop.ModemManager1.Modem.Location"
MODEM_MESSAGING = "org.freedesktop.ModemManager1.Modem.Messaging"
MODEM_SIMPLE = "org.freedesktop.ModemManager1.Modem.Simple"
MODEM_FIRMWARE = "org.freedesktop.ModemManager1.Modem.Firmware"
MODEM_CELL_BROADCAST = "org.freedesktop.ModemManager1.Modem.CellBroadcast"
SIM_IFACE = "org.freedesktop.ModemManager1.Sim"
BEARER_IFACE = "org.freedesktop.ModemManager1.Bearer"
MESSAGE_IFACE = "org.freedesktop.ModemManager1.Sms"


class ModemError(Exception):
    """A ModemManager call failed."""


def _system_proxy(path: str, interface: str) -> Gio.DBusProxy:
    """Proxy an interface on the system bus without starting the daemon."""
    return Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SYSTEM, Gio.DBusProxyFlags.DO_NOT_AUTO_START,
        None, BUS_NAME, path, interface, None,
    )


class Modem:
    """One modem, addressed by its object path."""

    def __init__(self, path: str, on_change=None) -> None:
        self.path = path
        self._on_change = on_change
        self._proxies: dict[str, Gio.DBusProxy] = {}
        self._interfaces: list[str] = []
        self._load_interfaces()

    # -- proxies ----------------------------------------------------------

    def _load_interfaces(self) -> None:
        io = self._get("org.freedesktop.DBus.Introspectable", self.path)
        xml = io.call_sync("Introspect", None, Gio.DBusCallFlags.NONE, 5000, None)
        names = xml.unpack()[0]
        self._interfaces = [
            line.split('interface name="')[1].split('"')[0]
            for line in names.splitlines()
            if 'interface name="' in line
        ]

    def has(self, interface: str) -> bool:
        return interface in self._interfaces

    def _get(self, interface: str, path: str, timeout: int = 5000) -> Gio.DBusProxy:
        key = f"{path}|{interface}"
        proxy = self._proxies.get(key)
        if proxy is not None:
            return proxy
        proxy = _system_proxy(path, interface)
        proxy.connect("g-properties-changed", self._properties_changed)
        self._proxies[key] = proxy
        return proxy

    def _properties_changed(self, _proxy, _changed, _invalidated) -> None:
        if self._on_change is not None:
            self._on_change()

    def _call(self, interface: str, method: str, params: GLib.Variant | None,
              timeout: int = 20000):
        proxy = self._get(interface, self.path)
        try:
            return proxy.call_sync(method, params, Gio.DBusCallFlags.NONE, timeout, None)
        except GLib.Error as exc:
            raise ModemError(_short_error(exc)) from exc

    def prop(self, interface: str, name: str, default=None):
        value = self._get(interface, self.path).get_cached_property(name)
        return default if value is None else value.unpack()

    def signal(self, interface: str, name: str, callback) -> None:
        self._get(interface, self.path).connect(name, callback)

    # -- identity ---------------------------------------------------------

    @property
    def manufacturer(self) -> str:
        return self.prop(MODEM_IFACE, "Manufacturer", "")

    @property
    def model(self) -> str:
        return self.prop(MODEM_IFACE, "Model", "")

    @property
    def revision(self) -> str:
        return self.prop(MODEM_IFACE, "Revision", "")

    @property
    def plugin(self) -> str:
        return self.prop(MODEM_IFACE, "Plugin", "")

    @property
    def primary_port(self) -> str:
        return self.prop(MODEM_IFACE, "PrimaryPort", "")

    @property
    def state(self) -> int:
        return int(self.prop(MODEM_IFACE, "State", 0))

    @property
    def state_failed_reason(self) -> int:
        return int(self.prop(MODEM_IFACE, "StateFailedReason", 0))

    @property
    def power_state(self) -> int:
        return int(self.prop(MODEM_IFACE, "PowerState", 0))

    @property
    def unlock_required(self) -> int:
        return int(self.prop(MODEM_IFACE, "UnlockRequired", 0))

    @property
    def unlock_retries(self) -> dict[int, int]:
        raw = self.prop(MODEM_IFACE, "UnlockRetries", {})
        return {int(k): int(v) for k, v in raw.items()}

    @property
    def signal_quality(self) -> tuple[int, bool]:
        percent, recent = self.prop(MODEM_IFACE, "SignalQuality", (0, False))
        return int(percent), bool(recent)

    @property
    def access_technologies(self) -> int:
        return int(self.prop(MODEM_IFACE, "AccessTechnologies", 0))

    @property
    def equipment_identifier(self) -> str:
        return self.prop(MODEM_IFACE, "EquipmentIdentifier", "")

    @property
    def device_identifier(self) -> str:
        return self.prop(MODEM_IFACE, "DeviceIdentifier", "")

    @property
    def drivers(self) -> list[str]:
        return list(self.prop(MODEM_IFACE, "Drivers", []))

    @property
    def ports(self) -> list[tuple[str, int]]:
        return [(str(name), int(kind)) for name, kind in self.prop(MODEM_IFACE, "Ports", [])]

    @property
    def sim_paths(self) -> list[str]:
        return list(self.prop(MODEM_IFACE, "SimSlots", []))

    @property
    def primary_sim_slot(self) -> int:
        return int(self.prop(MODEM_IFACE, "PrimarySimSlot", 0))

    @property
    def sim_path(self) -> str:
        return self.prop(MODEM_IFACE, "Sim", "")

    # -- capability / mode / band ----------------------------------------

    @property
    def supported_capabilities(self) -> list[int]:
        return [int(v) for v in self.prop(MODEM_IFACE, "SupportedCapabilities", [])]

    @property
    def current_capabilities(self) -> int:
        return int(self.prop(MODEM_IFACE, "CurrentCapabilities", 0))

    @property
    def supported_modes(self) -> list[tuple[int, int]]:
        return [(int(a), int(p)) for a, p in self.prop(MODEM_IFACE, "SupportedModes", [])]

    @property
    def current_modes(self) -> tuple[int, int]:
        allowed, preferred = self.prop(MODEM_IFACE, "CurrentModes", (0, 0))
        return int(allowed), int(preferred)

    @property
    def supported_bands(self) -> list[int]:
        return [int(v) for v in self.prop(MODEM_IFACE, "SupportedBands", [])]

    @property
    def current_bands(self) -> list[int]:
        return [int(v) for v in self.prop(MODEM_IFACE, "CurrentBands", [])]

    def set_current_capabilities(self, capabilities: int) -> None:
        self._call(MODEM_IFACE, "SetCurrentCapabilities", GLib.Variant("(u)", (capabilities,)))

    def set_current_modes(self, allowed: int, preferred: int) -> None:
        # SetCurrentModes takes one MMModemModeCombination struct, so the
        # signature is ((uu)) — two plain u arguments would be rejected.
        self._call(MODEM_IFACE, "SetCurrentModes",
                   GLib.Variant("((uu))", ((allowed, preferred),)))

    def set_current_bands(self, bands: list[int]) -> None:
        self._call(MODEM_IFACE, "SetCurrentBands", GLib.Variant("(au)", (bands,)))

    def set_power_state(self, state: int) -> None:
        self._call(MODEM_IFACE, "SetPowerState", GLib.Variant("(u)", (state,)))

    def enable(self, enable: bool) -> None:
        self._call(MODEM_IFACE, "Enable", GLib.Variant("(b)", (enable,)))

    def reset(self) -> None:
        self._call(MODEM_IFACE, "Reset", None)

    def factory_reset(self, code: str) -> None:
        self._call(MODEM_IFACE, "FactoryReset", GLib.Variant("(s)", (code,)))

    def set_primary_sim_slot(self, slot: int) -> None:
        self._call(MODEM_IFACE, "SetPrimarySimSlot", GLib.Variant("(u)", (slot,)))

    # -- 3GPP -------------------------------------------------------------

    @property
    def operator_name(self) -> str:
        return self.prop(MODEM_3GPP, "OperatorName", "")

    @property
    def operator_code(self) -> str:
        return self.prop(MODEM_3GPP, "OperatorCode", "")

    @property
    def registration_state(self) -> int:
        return int(self.prop(MODEM_3GPP, "RegistrationState", 0))

    @property
    def packet_service_state(self) -> int:
        return int(self.prop(MODEM_3GPP, "PacketServiceState", 0))

    @property
    def eps_ue_mode_operation(self) -> int:
        return int(self.prop(MODEM_3GPP, "EpsUeModeOperation", 0))

    @property
    def imei(self) -> str:
        return self.prop(MODEM_3GPP, "Imei", "")

    @property
    def enabled_facility_locks(self) -> int:
        return int(self.prop(MODEM_3GPP, "EnabledFacilityLocks", 0))

    @property
    def nr5g_registration_settings(self) -> dict:
        return dict(self.prop(MODEM_3GPP, "Nr5gRegistrationSettings", {}))

    @property
    def initial_eps_bearer_settings(self) -> dict:
        return dict(self.prop(MODEM_3GPP, "InitialEpsBearerSettings", {}))

    def set_eps_ue_mode_operation(self, mode: int) -> None:
        self._call(MODEM_3GPP, "SetEpsUeModeOperation", GLib.Variant("(u)", (mode,)))

    def set_packet_service_state(self, state: int) -> None:
        self._call(MODEM_3GPP, "SetPacketServiceState", GLib.Variant("(u)", (state,)))

    def set_initial_eps_bearer_settings(self, settings: dict) -> None:
        self._call(MODEM_3GPP, "SetInitialEpsBearerSettings",
                   GLib.Variant("(a{sv})", (_sv_dict(settings),)))

    def set_nr5g_registration_settings(self, settings: dict) -> None:
        self._call(MODEM_3GPP, "SetNr5gRegistrationSettings",
                   GLib.Variant("(a{sv})", (_sv_dict(settings),)))

    def disable_facility_lock(self, locks: int, pin: str) -> None:
        self._call(MODEM_3GPP, "DisableFacilityLock",
                   GLib.Variant("((us))", ((locks, pin),)))

    def scan_networks(self) -> list[dict]:
        reply = self._call(MODEM_3GPP, "Scan", None, timeout=180000)
        return [dict(item) for item in reply.unpack()[0]]

    def register(self, operator_id: str) -> None:
        self._call(MODEM_3GPP, "Register", GLib.Variant("(s)", (operator_id,)), timeout=180000)

    def set_carrier_lock(self, data: bytes) -> None:
        self._call(MODEM_3GPP, "SetCarrierLock", GLib.Variant("(ay)", (data,)), timeout=60000)

    # -- profiles ---------------------------------------------------------

    def list_profiles(self) -> list[dict]:
        reply = self._call(MODEM_3GPP_PROFILE, "List", None)
        return [dict(item) for item in reply.unpack()[0]]

    def set_profile(self, profile: dict) -> dict:
        reply = self._call(MODEM_3GPP_PROFILE, "Set",
                           GLib.Variant("(a{sv})", (_sv_dict(profile),)))
        return dict(reply.unpack()[0])

    def delete_profile(self, profile: dict) -> None:
        self._call(MODEM_3GPP_PROFILE, "Delete",
                   GLib.Variant("(a{sv})", (_sv_dict(profile),)))

    # -- USSD -------------------------------------------------------------

    def ussd_initiate(self, command: str) -> str:
        reply = self._call(MODEM_3GPP_USSD, "Initiate", GLib.Variant("(s)", (command,)),
                           timeout=120000)
        return reply.unpack()[0]

    def ussd_respond(self, response: str) -> str:
        reply = self._call(MODEM_3GPP_USSD, "Respond", GLib.Variant("(s)", (response,)),
                           timeout=120000)
        return reply.unpack()[0]

    def ussd_cancel(self) -> None:
        self._call(MODEM_3GPP_USSD, "Cancel", None)

    @property
    def ussd_state(self) -> int:
        return int(self.prop(MODEM_3GPP_USSD, "State", 0))

    @property
    def ussd_network_request(self) -> str:
        return self.prop(MODEM_3GPP_USSD, "NetworkRequest", "")

    @property
    def ussd_network_notification(self) -> str:
        return self.prop(MODEM_3GPP_USSD, "NetworkNotification", "")

    # -- signal -----------------------------------------------------------

    @property
    def signal_rate(self) -> int:
        return int(self.prop(MODEM_SIGNAL, "Rate", 0))

    @property
    def signal_thresholds(self) -> dict:
        return {
            "rssi": int(self.prop(MODEM_SIGNAL, "RssiThreshold", 0)),
            "error_rate": bool(self.prop(MODEM_SIGNAL, "ErrorRateThreshold", False)),
        }

    @property
    def signal_details(self) -> dict[str, dict]:
        result = {}
        for kind in ("Lte", "Nr5g", "Umts", "Gsm", "Cdma", "Evdo"):
            values = self.prop(MODEM_SIGNAL, kind, {})
            if values:
                result[kind.lower()] = {str(k): _plain(v) for k, v in values.items()}
        return result

    def set_signal_rate(self, rate: int) -> None:
        self._call(MODEM_SIGNAL, "Setup", GLib.Variant("(u)", (rate,)))

    def set_signal_thresholds(self, thresholds: dict) -> None:
        self._call(MODEM_SIGNAL, "SetupThresholds",
                   GLib.Variant("(a{sv})", (_sv_dict(thresholds),)))

    # -- SAR --------------------------------------------------------------

    @property
    def sar_state(self) -> bool:
        return bool(self.prop(MODEM_SAR, "State", False))

    @property
    def sar_power_level(self) -> int:
        return int(self.prop(MODEM_SAR, "PowerLevel", 0))

    def sar_enable(self, enable: bool) -> None:
        self._call(MODEM_SAR, "Enable", GLib.Variant("(b)", (enable,)))

    def sar_set_power_level(self, level: int) -> None:
        self._call(MODEM_SAR, "SetPowerLevel", GLib.Variant("(u)", (level,)))

    # -- location ---------------------------------------------------------

    @property
    def location_capabilities(self) -> int:
        return int(self.prop(MODEM_LOCATION, "Capabilities", 0))

    @property
    def location_enabled(self) -> int:
        return int(self.prop(MODEM_LOCATION, "Enabled", 0))

    @property
    def location_signals(self) -> bool:
        return bool(self.prop(MODEM_LOCATION, "SignalsLocation", False))

    @property
    def gps_refresh_rate(self) -> int:
        return int(self.prop(MODEM_LOCATION, "GpsRefreshRate", 0))

    @property
    def supl_server(self) -> str:
        return self.prop(MODEM_LOCATION, "SuplServer", "")

    @property
    def assistance_data_servers(self) -> list[str]:
        return list(self.prop(MODEM_LOCATION, "AssistanceDataServers", []))

    def get_location(self) -> dict:
        reply = self._call(MODEM_LOCATION, "GetLocation", None, timeout=10000)
        return {int(k): _plain(v) for k, v in reply.unpack()[0].items()}

    def location_setup(self, sources: int, signals: bool) -> None:
        self._call(MODEM_LOCATION, "Setup", GLib.Variant("(ub)", (sources, signals)))

    def set_supl_server(self, server: str) -> None:
        self._call(MODEM_LOCATION, "SetSuplServer", GLib.Variant("(s)", (server,)))

    def set_gps_refresh_rate(self, rate: int) -> None:
        self._call(MODEM_LOCATION, "SetGpsRefreshRate", GLib.Variant("(u)", (rate,)))

    # -- messaging --------------------------------------------------------

    @property
    def default_storage(self) -> int:
        return int(self.prop(MODEM_MESSAGING, "DefaultStorage", 0))

    @property
    def supported_storages(self) -> list[int]:
        return [int(v) for v in self.prop(MODEM_MESSAGING, "SupportedStorages", [])]

    @property
    def message_paths(self) -> list[str]:
        return list(self.prop(MODEM_MESSAGING, "Messages", []))

    def list_messages(self) -> list[str]:
        reply = self._call(MODEM_MESSAGING, "List", None)
        return list(reply.unpack()[0])

    def messages(self) -> list["Message"]:
        return [Message(path) for path in self.list_messages()]

    def create_message(self, number: str, text: str) -> str:
        reply = self._call(
            MODEM_MESSAGING, "Create",
            GLib.Variant("(a{sv})", (_sv_dict({"number": number, "text": text}),)))
        return reply.unpack()[0]

    def set_default_storage(self, storage: int) -> None:
        self._call(MODEM_MESSAGING, "SetDefaultStorage", GLib.Variant("(u)", (storage,)))

    # -- firmware ---------------------------------------------------------

    def list_firmware(self) -> list[dict]:
        # List returns (method, images): the method name comes first.
        reply = self._call(MODEM_FIRMWARE, "List", None)
        return [dict(item) for item in reply.unpack()[1]]

    def select_firmware(self, unique_id: str) -> None:
        self._call(MODEM_FIRMWARE, "Select", GLib.Variant("(s)", (unique_id,)),
                   timeout=60000)

    # -- cell broadcast ---------------------------------------------------

    @property
    def cell_broadcast_channels(self) -> list[tuple[int, int]]:
        return [(int(a), int(b)) for a, b in self.prop(MODEM_CELL_BROADCAST, "Channels", [])]

    def set_cell_broadcast_channels(self, channels: list[tuple[int, int]]) -> None:
        self._call(MODEM_CELL_BROADCAST, "SetChannels", GLib.Variant("(a(uu))", (channels,)))

    # -- simple -----------------------------------------------------------

    def simple_status(self) -> dict:
        reply = self._call(MODEM_SIMPLE, "GetStatus", None)
        return {str(k): _plain(v) for k, v in reply.unpack()[0].items()}

    def simple_connect(self, settings: dict) -> str:
        reply = self._call(MODEM_SIMPLE, "Connect",
                           GLib.Variant("(a{sv})", (_sv_dict(settings),)),
                           timeout=120000)
        return reply.unpack()[0]

    def simple_disconnect(self, bearer: str) -> None:
        self._call(MODEM_SIMPLE, "Disconnect", GLib.Variant("(o)", (bearer,)), timeout=60000)

    def list_bearers(self) -> list[str]:
        reply = self._call(MODEM_IFACE, "ListBearers", None)
        return list(reply.unpack()[0])

    def bearers(self, on_change=None) -> list["Bearer"]:
        return [Bearer(path, on_change=on_change) for path in self.list_bearers()]

    def disconnect_bearers(self) -> list[str]:
        """Disconnect every active bearer and return the paths that were up.

        Register() is refused while a bearer is connected, so network selection
        has to drop the data session first.
        """
        disconnected = []
        for bearer in self.bearers():
            if bearer.connected:
                self.simple_disconnect(bearer.path)
                disconnected.append(bearer.path)
        return disconnected

    def command(self, command: str, timeout: int = 10) -> str:
        reply = self._call(MODEM_IFACE, "Command", GLib.Variant("(su)", (command, timeout)),
                           timeout=(timeout + 5) * 1000)
        return reply.unpack()[0]


class Bearer:
    """One bearer object: the APN, its interface and whether it is up."""

    def __init__(self, path: str, on_change=None) -> None:
        self.path = path
        self._proxy_obj: Gio.DBusProxy | None = None
        self._on_change = on_change

    def _proxy(self) -> Gio.DBusProxy:
        if self._proxy_obj is None:
            self._proxy_obj = _system_proxy(self.path, BEARER_IFACE)
            if self._on_change is not None:
                self._proxy_obj.connect(
                    "g-properties-changed", lambda *_a: self._on_change())
        return self._proxy_obj

    @property
    def apn(self) -> str:
        settings = self._proxy().get_cached_property("Properties")
        if settings is None:
            return ""
        try:
            return str(dict(settings.unpack()).get("apn", ""))
        except (TypeError, ValueError):
            return ""

    @property
    def interface(self) -> str:
        value = self._proxy().get_cached_property("Interface")
        return value.unpack() if value is not None else ""

    @property
    def connected(self) -> bool:
        value = self._proxy().get_cached_property("Connected")
        return bool(value.unpack()) if value is not None else False


class Sim:
    def __init__(self, path: str, on_change=None) -> None:
        self.path = path
        self._proxy_obj: Gio.DBusProxy | None = None
        self._on_change = on_change

    def _proxy(self) -> Gio.DBusProxy:
        if self._proxy_obj is None:
            self._proxy_obj = _system_proxy(self.path, SIM_IFACE)
            if self._on_change is not None:
                self._proxy_obj.connect(
                    "g-properties-changed", lambda *_a: self._on_change())
        return self._proxy_obj

    def prop(self, name: str, default=None):
        value = self._proxy().get_cached_property(name)
        return default if value is None else value.unpack()

    def _call(self, method: str, params: GLib.Variant | None):
        try:
            return self._proxy().call_sync(method, params, Gio.DBusCallFlags.NONE, 60000, None)
        except GLib.Error as exc:
            raise ModemError(_short_error(exc)) from exc

    @property
    def active(self) -> bool:
        return bool(self.prop("Active", False))

    @property
    def imsi(self) -> str:
        return self.prop("Imsi", "")

    @property
    def sim_identifier(self) -> str:
        return self.prop("SimIdentifier", "")

    @property
    def operator_name(self) -> str:
        return self.prop("OperatorName", "")

    @property
    def operator_identifier(self) -> str:
        return self.prop("OperatorIdentifier", "")

    @property
    def sim_type(self) -> int:
        return int(self.prop("SimType", 0))

    @property
    def remoability(self) -> int:
        return int(self.prop("Removability", 0))

    @property
    def esim_status(self) -> int:
        return int(self.prop("EsimStatus", 0))

    @property
    def eid(self) -> str:
        return self.prop("Eid", "")

    @property
    def gid1(self) -> str:
        return _hex(self.prop("Gid1", []))

    @property
    def gid2(self) -> str:
        return _hex(self.prop("Gid2", []))

    @property
    def emergency_numbers(self) -> list[str]:
        return list(self.prop("EmergencyNumbers", []))

    @property
    def preferred_networks(self) -> list[tuple[str, int]]:
        return [(str(code), int(techs)) for code, techs in self.prop("PreferredNetworks", [])]

    def send_pin(self, pin: str) -> None:
        self._call("SendPin", GLib.Variant("(s)", (pin,)))

    def send_puk(self, puk: str, pin: str) -> None:
        self._call("SendPuk", GLib.Variant("(ss)", (puk, pin)))

    def enable_pin(self, pin: str, enabled: bool) -> None:
        self._call("EnablePin", GLib.Variant("(sb)", (pin, enabled)))

    def change_pin(self, old: str, new: str) -> None:
        self._call("ChangePin", GLib.Variant("(ss)", (old, new)))

    def set_preferred_networks(self, networks: list[tuple[str, int]]) -> None:
        self._call("SetPreferredNetworks", GLib.Variant("(a(su))", (networks,)))


class Message:
    """One SMS object, addressed by its object path."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._proxy_obj: Gio.DBusProxy | None = None

    def _proxy(self) -> Gio.DBusProxy:
        if self._proxy_obj is None:
            self._proxy_obj = _system_proxy(self.path, MESSAGE_IFACE)
        return self._proxy_obj

    def prop(self, name: str, default=None):
        value = self._proxy().get_cached_property(name)
        return default if value is None else value.unpack()

    @property
    def number(self) -> str:
        return self.prop("Number", "")

    @property
    def text(self) -> str:
        return self.prop("Text", "")

    @property
    def timestamp(self) -> str:
        return self.prop("Timestamp", "")

    @property
    def state(self) -> int:
        return int(self.prop("State", 0))


_manager_proxy: Gio.DBusProxy | None = None


def manager_proxy() -> Gio.DBusProxy:
    """The shared ObjectManager proxy used to list and watch modems."""
    global _manager_proxy
    if _manager_proxy is None:
        _manager_proxy = _system_proxy(
            ROOT_PATH, "org.freedesktop.DBus.ObjectManager")
    return _manager_proxy


def watch_modems(callback) -> Gio.DBusProxy:
    """Call ``callback`` when a modem interface is added or removed."""
    proxy = manager_proxy()

    def on_signal(_proxy, _sender, signal_name, parameters) -> None:
        if signal_name not in ("InterfacesAdded", "InterfacesRemoved"):
            return
        _path, interfaces = parameters.unpack()
        if MODEM_IFACE in interfaces:
            callback()

    proxy.connect("g-signal", on_signal)
    return proxy


def list_modems() -> list[str]:
    """Object paths of every modem ModemManager currently knows."""
    try:
        manager = manager_proxy()
        reply = manager.call_sync(
            "GetManagedObjects", None, Gio.DBusCallFlags.NONE, 5000, None,
        )
    except GLib.Error as exc:
        raise ModemError(_short_error(exc)) from exc
    objects = reply.unpack()[0]
    return sorted(
        path for path, interfaces in objects.items()
        if MODEM_IFACE in interfaces
    )


def manager_version() -> str:
    try:
        proxy = _system_proxy(ROOT_PATH, "org.freedesktop.ModemManager1")
        value = proxy.get_cached_property("Version")
        return value.unpack() if value is not None else ""
    except GLib.Error:
        return ""


def _sv_dict(values: dict, int_type: str = "u") -> dict:
    """Wrap plain Python values as the GVariant members of an ``a{sv}``.

    GLib requires each value of a variant dictionary to already be a
    GLib.Variant; a plain str/int/bool raises "Expected GLib.Variant".
    Profile and simple-connect dictionaries use uint32 numbers, while signal
    thresholds use int32, so the integer type is selectable.
    """
    result = {}
    for key, value in values.items():
        if isinstance(value, GLib.Variant):
            variant = value
        elif isinstance(value, bool):
            variant = GLib.Variant("b", value)
        elif isinstance(value, int):
            variant = GLib.Variant(int_type, value)
        elif isinstance(value, float):
            variant = GLib.Variant("d", value)
        elif isinstance(value, str):
            variant = GLib.Variant("s", value)
        elif isinstance(value, (bytes, bytearray)):
            variant = GLib.Variant("ay", value)
        else:
            raise TypeError(
                f"cannot send {type(value).__name__} for {key!r}")
        result[str(key)] = variant
    return result


def _plain(value):
    """Convert a GLib variant into plain Python, recursively."""
    if isinstance(value, GLib.Variant):
        return _plain(value.unpack())
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, bytes):
        return value.hex()
    return value


def _hex(raw) -> str:
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw).hex()
    return "".join(f"{int(v):02x}" for v in _plain(raw))


def _short_error(exc: GLib.Error) -> str:
    """Turn a GLib error into something readable in a toast.

    The message looks like
    ``GDBus.Error:org.freedesktop.DBus.Error.AccessDenied: Access denied``,
    so strip the domain and the D-Bus error nick, then translate the two
    messages that ModemManager and dbus-broker reuse for policy denials.
    """
    message = exc.message or str(exc)
    for prefix in ("GDBus.Error:", "org.freedesktop.DBus.Error."):
        if prefix in message:
            message = message.split(prefix, 1)[1]
    if ": " in message:
        nick, _, detail = message.partition(": ")
        if nick and " " not in nick and not nick.endswith("."):
            message = detail
    message = message.strip(": ")
    if message in ("Access denied", "AccessDenied"):
        return "permission denied by the system bus policy"
    return message
