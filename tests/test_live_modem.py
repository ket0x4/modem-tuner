"""Live checks against the modem on this machine.

Skips when ModemManager is absent or exposes no modem, so it is safe to run
anywhere. Nothing here writes to the modem.
"""

import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from gi.repository import Gio, GLib
    from modem_tuner.client import (BUS_NAME, MODEM_3GPP, MODEM_IFACE,
                                    MODEM_SIGNAL, SIM_IFACE, Modem, ModemError,
                                    Sim, list_modems, manager_version)
except Exception as exc:  # noqa: BLE001 - no GI or typelib on this machine
    raise unittest.SkipTest(f"ModemManager bindings unavailable: {exc}") from exc


def _method_signatures(path: str) -> dict[str, dict[str, str]]:
    """Map interface -> method -> "(in,arg,types)" from introspection."""
    proxy = Gio.DBusProxy.new_for_bus_sync(
        Gio.BusType.SYSTEM, Gio.DBusProxyFlags.DO_NOT_AUTO_START, None,
        BUS_NAME, path, "org.freedesktop.DBus.Introspectable", None)
    xml = proxy.call_sync(
        "Introspect", None, Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    result = {}
    for interface in ET.fromstring(xml).findall("interface"):
        methods = {}
        for method in interface.findall("method"):
            args = "".join(
                arg.get("type") for arg in method.findall("arg")
                if arg.get("direction") == "in")
            methods[method.get("name")] = f"({args})"
        result[interface.get("name")] = methods
    return result


class TestLiveModem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            paths = list_modems()
        except ModemError as exc:
            raise unittest.SkipTest(f"ModemManager not reachable: {exc}") from exc
        if not paths:
            raise unittest.SkipTest("no modem present")
        cls.modem = Modem(paths[0])

    def test_manager_version(self):
        self.assertRegex(manager_version(), r"^\d+\.\d+")

    def test_identity(self):
        self.assertTrue(self.modem.manufacturer or self.modem.model)
        self.assertTrue(self.modem.primary_port)

    def test_capabilities_are_sane(self):
        supported = self.modem.supported_capabilities
        self.assertTrue(supported)
        self.assertIn(self.modem.current_capabilities, supported)

    def test_current_mode_is_supported(self):
        self.assertIn(self.modem.current_modes, self.modem.supported_modes)

    def test_bands_are_known(self):
        supported = set(self.modem.supported_bands)
        current = set(self.modem.current_bands)
        # ANY is a valid "no restriction" value and is not part of the list.
        self.assertTrue(current <= supported or 256 in current)

    def test_signal_quality_range(self):
        quality, _recent = self.modem.signal_quality
        self.assertGreaterEqual(quality, 0)
        self.assertLessEqual(quality, 100)

    def test_profiles_readable(self):
        if not self.modem.has("org.freedesktop.ModemManager1.Modem.Modem3gpp.ProfileManager"):
            self.skipTest("no profile manager")
        profiles = self.modem.list_profiles()
        for profile in profiles:
            self.assertIn("profile-id", profile)

    def test_sim_readable(self):
        path = self.modem.sim_path
        if not path:
            self.skipTest("no SIM")
        sim = Sim(path)
        self.assertTrue(sim.imsi or sim.sim_identifier)

    def test_set_current_modes_uses_combination_struct(self):
        # SetCurrentModes takes one (uu) struct, not two u arguments.
        calls = []

        def capture(_interface, method, params=None, timeout=20000):
            calls.append((method, params.get_type_string() if params else None))
            return GLib.Variant("()", ())

        original = self.modem._call
        self.modem._call = capture
        try:
            self.modem.set_current_modes(24, 0)
        finally:
            self.modem._call = original
        self.assertIn(("SetCurrentModes", "((uu))"), calls)

    def test_setter_signatures_match_introspection(self):
        expected = {}
        for path in (self.modem.path, self.modem.sim_path):
            if path:
                for interface, methods in _method_signatures(path).items():
                    for name, signature in methods.items():
                        expected[(interface, name)] = signature

        calls = []

        def capture(interface, method, params=None, timeout=20000):
            calls.append((interface, method, params))
            if method == "ListBearers":
                return GLib.Variant("(ao)", ([],))
            if method == "Set":
                return GLib.Variant("(a{sv})", ({},))
            if method in ("Initiate", "Respond", "Command"):
                return GLib.Variant("(s)", ("",))
            if method in ("Create", "Connect"):
                return GLib.Variant("(o)", ("/",))
            return GLib.Variant("()", ())

        original = self.modem._call
        self.modem._call = capture
        try:
            self.modem.set_current_capabilities(1)
            self.modem.set_current_modes(24, 0)
            self.modem.set_current_bands([31])
            self.modem.set_power_state(3)
            self.modem.enable(True)
            self.modem.reset()
            self.modem.factory_reset("0000")
            self.modem.set_primary_sim_slot(1)
            self.modem.set_eps_ue_mode_operation(1)
            self.modem.set_packet_service_state(2)
            self.modem.set_initial_eps_bearer_settings({"apn": "ims"})
            self.modem.set_nr5g_registration_settings({"mico-mode": 0})
            self.modem.disable_facility_lock(1, "1234")
            self.modem.register("")
            self.modem.set_carrier_lock(b"\x00")
            self.modem.set_profile({"apn": "internet"})
            self.modem.delete_profile({"profile-id": 1})
            self.modem.ussd_initiate("*100#")
            self.modem.ussd_respond("1")
            self.modem.ussd_cancel()
            self.modem.set_signal_rate(0)
            self.modem.set_signal_thresholds({"rssi-threshold": 10})
            self.modem.sar_enable(True)
            self.modem.sar_set_power_level(1)
            self.modem.location_setup(1, False)
            self.modem.set_supl_server("supl.example")
            self.modem.set_gps_refresh_rate(30)
            self.modem.set_default_storage(1)
            self.modem.select_firmware("x")
            self.modem.set_cell_broadcast_channels([])
            self.modem.disconnect_bearers()
            self.modem.simple_disconnect("/org/freedesktop/ModemManager1/Bearer/1")
            self.modem.simple_connect({"apn": "internet"})
            self.modem.command("AT", 1)
            self.modem.create_message("123", "hi")
        finally:
            self.modem._call = original

        problems = []
        for interface, method, params in calls:
            actual = params.get_type_string() if params is not None else "()"
            want = expected.get((interface, method))
            if want != actual:
                problems.append(f"{method}: sent {actual}, expected {want}")
        self.assertEqual(problems, [], "; ".join(problems))

    def test_sim_setter_signatures_match_introspection(self):
        if not self.modem.sim_path:
            self.skipTest("no SIM")
        sim = Sim(self.modem.sim_path)
        expected = _method_signatures(self.modem.sim_path).get(SIM_IFACE, {})
        calls = []

        def capture(method, params=None):
            calls.append((method, params))
            return GLib.Variant("()", ())

        original = sim._call
        sim._call = capture
        try:
            sim.send_pin("1234")
            sim.send_puk("00000000", "1234")
            sim.enable_pin("1234", True)
            sim.change_pin("1234", "4321")
            sim.set_preferred_networks([("28603", 0x3FFF)])
        finally:
            sim._call = original

        problems = []
        for method, params in calls:
            actual = params.get_type_string() if params is not None else "()"
            if expected.get(method) != actual:
                problems.append(
                    f"{method}: sent {actual}, expected {expected.get(method)}")
        self.assertEqual(problems, [], "; ".join(problems))

    def test_interfaces_present(self):
        for interface in (MODEM_IFACE, MODEM_3GPP, MODEM_SIGNAL):
            self.assertTrue(self.modem.has(interface), interface)


if __name__ == "__main__":
    unittest.main()
