"""Tests for the pure helpers: enum labels, band naming, error formatting.

These run without a modem, so they are safe in CI. The D-Bus client is covered
by the smoke test in tests/smoke_dbus.py, which skips when no modem is present.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from modem_tuner import constants as C  # noqa: E402


class TestModeLabels(unittest.TestCase):
    def test_single_bits(self):
        self.assertEqual(C.mode_bits_label(8), "4G")
        self.assertEqual(C.mode_bits_label(16), "5G")
        self.assertEqual(C.mode_bits_label(2), "2G")
        self.assertEqual(C.mode_bits_label(4), "3G")

    def test_combined(self):
        self.assertEqual(C.mode_bits_label(24), "4G+5G")

    def test_zero(self):
        self.assertEqual(C.mode_bits_label(0), "none")


class TestCapabilityLabels(unittest.TestCase):
    def test_lte_only(self):
        self.assertEqual(C.capability_label(8), "LTE")

    def test_lte_and_5g(self):
        # 72 is what the OnePlus 9 in this repo reports.
        self.assertEqual(C.capability_label(72), "LTE + 5G NR")

    def test_zero(self):
        self.assertEqual(C.capability_label(0), "none")


class TestBands(unittest.TestCase):
    def test_lte_band(self):
        self.assertEqual(C.band_label(31), "LTE B1")

    def test_nr_band(self):
        self.assertEqual(C.band_label(377), "NR n77")

    def test_umts_band(self):
        # UMTS B3 is 6; the value 3 is PCS in the GSM family.
        self.assertEqual(C.band_label(6), "UMTS B3")

    def test_cdma_band(self):
        self.assertEqual(C.band_label(128), "CDMA BC0")

    def test_gsm_band(self):
        self.assertEqual(C.band_label(1), "EGSM")

    def test_families(self):
        self.assertEqual(C.band_family(31), "LTE")
        self.assertEqual(C.band_family(377), "5G NR")
        self.assertEqual(C.band_family(6), "UMTS")
        self.assertEqual(C.band_family(128), "CDMA")
        self.assertEqual(C.band_family(1), "GSM")

    def test_any_band_present(self):
        # ANY is a flag, not a band, so it must not get a band label.
        self.assertEqual(C.ANY_BAND, 256)
        self.assertNotIn(C.ANY_BAND, C.BAND_LABELS)


class TestAccessTechnology(unittest.TestCase):
    def test_lte_and_5g(self):
        # 49152 = LTE | 5GNR, the mask the modem reports.
        self.assertEqual(C.access_technology_names(49152), ["5G NR", "LTE"])
        self.assertEqual(C.access_technology_short(49152), "5G NR")

    def test_empty(self):
        self.assertEqual(C.access_technology_names(0), [])
        self.assertEqual(C.access_technology_short(0), "")

    def test_unknown_bit_is_ignored(self):
        self.assertEqual(C.access_technology_names(1 << 30), [])


class TestLabelsPresent(unittest.TestCase):
    def test_every_enum_value_has_a_label(self):
        self.assertEqual(set(C.STATE_LABELS), set(C.MODEM_STATE))
        self.assertEqual(set(C.POWER_STATE_LABELS), set(C.MODEM_POWER_STATE))

    def test_network_states(self):
        # Registered and Connected are the only states where a leftover
        # UnlockRequired must not be presented as blocking.
        self.assertEqual(C.NETWORK_STATES, {8, 11})


class TestSharedLabels(unittest.TestCase):
    def test_scan_status(self):
        self.assertEqual(C.NETWORK_SCAN_STATUS_LABELS[1], "Registered")
        self.assertEqual(C.NETWORK_SCAN_STATUS_LABELS[5], "Registered (roaming)")

    def test_storage(self):
        self.assertEqual(C.STORAGE_LABELS, {0: "Unknown", 1: "SIM", 2: "Modem"})

    def test_ip_type(self):
        self.assertEqual(C.IP_TYPE_VALUES, [3, 4, 6])
        self.assertEqual(C.IP_TYPE_DIALOG_LABELS, ["IPv4", "IPv6", "IPv4v6"])
        self.assertEqual(C.IP_TYPE_LABELS[0], "IPv4")

    def test_apn_type_label(self):
        # Default + IMS is the usual profile on the modem in this repo.
        self.assertEqual(C.apn_type_label(2 | 4), "Default+IMS")
        self.assertEqual(C.apn_type_label(0), "")


class TestVariantDict(unittest.TestCase):
    def test_plain_values_become_variants(self):
        from modem_tuner.client import _sv_dict

        mapping = _sv_dict({"apn": "internet", "count": 2, "on": True})
        self.assertEqual(mapping["apn"].get_type_string(), "s")
        self.assertEqual(mapping["count"].get_type_string(), "u")
        self.assertEqual(mapping["on"].get_type_string(), "b")

    def test_thresholds_use_unsigned_ints(self):
        from modem_tuner.client import _sv_dict

        mapping = _sv_dict({"rssi-threshold": 10})
        self.assertEqual(mapping["rssi-threshold"].get_type_string(), "u")


class TestShortError(unittest.TestCase):
    def test_strips_dbus_prefix(self):
        from modem_tuner.client import _short_error

        class FakeError(Exception):
            message = "GDBus.Error:org.freedesktop.DBus.Error.AccessDenied: Access denied"

        self.assertEqual(_short_error(FakeError()),
                         "permission denied by the system bus policy")


if __name__ == "__main__":
    unittest.main()
