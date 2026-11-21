"""Live checks against the modem on this machine.

Skips when ModemManager is absent or exposes no modem, so it is safe to run
anywhere. Nothing here writes to the modem.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from modem_tuner.client import (MODEM_3GPP, MODEM_IFACE, MODEM_SIGNAL, Modem,
                                    ModemError, Sim, list_modems, manager_version)
except Exception as exc:  # noqa: BLE001 - no GI or typelib on this machine
    raise unittest.SkipTest(f"ModemManager bindings unavailable: {exc}") from exc


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

    def test_interfaces_present(self):
        for interface in (MODEM_IFACE, MODEM_3GPP, MODEM_SIGNAL):
            self.assertTrue(self.modem.has(interface), interface)


if __name__ == "__main__":
    unittest.main()
