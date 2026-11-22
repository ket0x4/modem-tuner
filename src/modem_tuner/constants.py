"""ModemManager self-description: enums, band names and value mappings.

Enums are imported from the libmm-glib typelib when available, so the numbers
always match the ModemManager installed on the device. The band name table is
kept here because ModemManager only exposes band enums as integers over D-Bus
and mmcli renders the names itself.
"""

from __future__ import annotations

import gi

gi.require_version("ModemManager", "1.0")

from gi.repository import ModemManager as MM  # noqa: E402


def _enum_members(enum_type) -> dict[int, str]:
    return {
        getattr(enum_type, name): name
        for name in dir(enum_type)
        if not name.startswith("_") and isinstance(getattr(enum_type, name), int)
    }


MODEM_MODE = _enum_members(MM.ModemMode)
MODEM_STATE = _enum_members(MM.ModemState)
MODEM_POWER_STATE = _enum_members(MM.ModemPowerState)
MODEM_ACCESS_TECHNOLOGY = _enum_members(MM.ModemAccessTechnology)
MODEM_CAPABILITY = _enum_members(MM.ModemCapability)
MODEM_BAND = _enum_members(MM.ModemBand)
MODEM_LOCK = _enum_members(MM.ModemLock)
SIM_TYPE = _enum_members(MM.SimType)
REGISTRATION_STATE = _enum_members(MM.Modem3gppRegistrationState)
EPS_UE_MODE = _enum_members(MM.Modem3gppEpsUeModeOperation)
PACKET_SERVICE_STATE = _enum_members(MM.Modem3gppPacketServiceState)
LOCATION_SOURCE = _enum_members(MM.ModemLocationSource)
SMS_STATE = _enum_members(MM.SmsState)

# Readable labels. The enum nicks are fine for code, but 5GNR / LTE_CAT_M are
# not what a user wants to see.
MODE_LABELS = {1: "CS", 2: "2G", 4: "3G", 8: "4G", 16: "5G"}
STATE_LABELS = {
    0: "Unknown", 1: "Initializing", 2: "Locked", 3: "Disabled",
    4: "Disabling", 5: "Enabling", 6: "Enabled", 7: "Searching",
    8: "Registered", 9: "Disconnecting", 10: "Connecting", 11: "Connected",
    -1: "Failed",
}
POWER_STATE_LABELS = {0: "Unknown", 1: "Off", 2: "Low", 3: "On"}

# Modem states in which the modem has passed registration, so a lock reported in
# UnlockRequired is only a leftover capability rather than a blocker. ModemState
# values are not ordered in a way that allows a threshold (CONNECTING is 10,
# which sorts after CONNECTED at 11 would appear "further along").
NETWORK_STATES = frozenset({8, 11})
REGISTRATION_LABELS = {
    0: "Idle", 1: "Home", 2: "Searching", 3: "Denied", 4: "Unknown",
    5: "Roaming", 6: "Home (SMS only)", 7: "Roaming (SMS only)",
    8: "Emergency only", 9: "Home (CSFB not preferred)",
    10: "Roaming (CSFB not preferred)", 11: "Attached (RLOS)",
}
EPS_UE_MODE_LABELS = {
    0: "Unknown", 1: "PS mode 1", 2: "PS mode 2",
    3: "CS/PS mode 1", 4: "CS/PS mode 2",
}
PACKET_SERVICE_LABELS = {0: "Unknown", 1: "Detached", 2: "Attached"}
LOCK_LABELS = {
    0: "Unknown", 1: "Unlocked", 2: "SIM PIN", 3: "SIM PIN2", 4: "SIM PUK",
    5: "SIM PUK2", 6: "PH-SP PIN", 7: "PH-SP PUK", 8: "PH-NET PIN",
    9: "PH-NET PUK", 10: "PH-SIM PIN", 11: "PH-CORP PIN", 12: "PH-CORP PUK",
    13: "PH-FSIM PIN", 14: "PH-FSIM PUK", 15: "PH-NETSUB PIN",
    16: "PH-NETSUB PUK",
}
APN_TYPE_LABELS = {
    1: "Initial", 2: "Default", 4: "IMS", 8: "MMS", 16: "Management",
    32: "Voice", 64: "Emergency", 128: "Private", 256: "Purchase",
    512: "Video share", 1024: "Local", 2048: "APP", 4096: "XCAP",
    8192: "Tethering",
}
AUTH_LABELS = {
    1: "None", 2: "PAP", 4: "CHAP", 8: "MSCHAP", 16: "MSCHAPV2", 32: "EAP",
}
PROFILE_SOURCE_LABELS = {
    0: "Unknown", 1: "Admin", 2: "User", 3: "Operator", 4: "Modem",
    5: "Device",
}
STORAGE_LABELS = {0: "Unknown", 1: "SIM", 2: "Modem"}
ESIM_STATUS_LABELS = {
    0: "Unknown", 1: "No profile", 2: "With profiles", 3: "Provisioning",
}
REMOVABILITY_LABELS = {0: "Unknown", 1: "Removable", 2: "Not removable"}
IP_TYPE_LABELS = {
    0: "IPv4", 1: "IPv6", 2: "IPv4v6", 3: "IPv4", 4: "IPv6",
    5: "IPv4v6", 6: "IPv4v6",
}
IP_TYPE_VALUES = [3, 4, 6]
IP_TYPE_DIALOG_LABELS = [IP_TYPE_LABELS[value] for value in IP_TYPE_VALUES]
# Registration state as reported in scan results; the wording is the one the
# scan list has always used, which reads better there than REGISTRATION_LABELS.
NETWORK_SCAN_STATUS_LABELS = {
    0: "Not registered", 1: "Registered", 2: "Searching",
    3: "Registration denied", 4: "Unknown", 5: "Registered (roaming)",
}
SMS_STATE_LABELS = {
    0: "Unknown", 1: "Stored", 2: "Receiving", 3: "Received",
    4: "Sending", 5: "Sent", 6: "Error",
}
USSD_STATE_LABELS = {
    0: "Idle", 1: "Active", 2: "User response required",
}

# Access technology bits, ordered strongest first. Values are looked up by enum
# nick because several nicks ("5GNR", "1XRTT") are not valid Python attribute
# names and cannot be reached through getattr.
_ACCESS_TECH_LABELS = [
    ("LTE_CAT_M", "LTE Cat-M"),
    ("LTE_NB_IOT", "LTE NB-IoT"),
    ("5GNR", "5G NR"),
    ("LTE", "LTE"),
    ("HSPA_PLUS", "HSPA+"),
    ("HSPA", "HSPA"),
    ("HSUPA", "HSUPA"),
    ("HSDPA", "HSDPA"),
    ("UMTS", "UMTS"),
    ("EVDOB", "EVDO Rev B"),
    ("EVDOA", "EVDO Rev A"),
    ("EVDO0", "EVDO Rev 0"),
    ("EDGE", "EDGE"),
    ("GPRS", "GPRS"),
    ("GSM_COMPACT", "GSM Compact"),
    ("GSM", "GSM"),
    ("1XRTT", "1xRTT"),
]

_ACCESS_TECH_BY_NICK = {nick: value for value, nick in MODEM_ACCESS_TECHNOLOGY.items()}
ACCESS_TECH_ORDER = [
    (_ACCESS_TECH_BY_NICK[nick], label)
    for nick, label in _ACCESS_TECH_LABELS
    if nick in _ACCESS_TECH_BY_NICK
]


def access_technology_names(mask: int) -> list[str]:
    """Every access technology set in a ModemManager bitmask."""
    return [label for bit, label in ACCESS_TECH_ORDER if mask & bit]


def access_technology_short(mask: int) -> str:
    names = access_technology_names(mask)
    return names[0] if names else ""


# Band enums are 16-bit families: 1-127 GSM/UMTS, 128+ CDMA, 31+ E-UTRAN is
# derived from the enum value, so build the names from the enum itself.
BAND_LABELS: dict[int, str] = {}
for _value, _nick in MODEM_BAND.items():
    if _nick == "ANY":
        continue
    if _nick.startswith("EUTRAN_"):
        BAND_LABELS[_value] = "LTE B" + _nick[len("EUTRAN_"):]
    elif _nick.startswith("NGRAN_"):
        BAND_LABELS[_value] = "NR n" + _nick[len("NGRAN_"):]
    elif _nick.startswith("UTRAN_"):
        BAND_LABELS[_value] = "UMTS B" + _nick[len("UTRAN_"):]
    elif _nick.startswith("CDMA_BC"):
        BAND_LABELS[_value] = "CDMA BC" + _nick[len("CDMA_BC"):]
    else:
        BAND_LABELS[_value] = _nick

ANY_BAND = MM.ModemBand.ANY


def band_family(band: int) -> str:
    nick = MODEM_BAND.get(band, "")
    if nick.startswith("EUTRAN_"):
        return "LTE"
    if nick.startswith("NGRAN_"):
        return "5G NR"
    if nick.startswith("UTRAN_"):
        return "UMTS"
    if nick.startswith("CDMA_"):
        return "CDMA"
    return "GSM"


def band_label(band: int) -> str:
    return BAND_LABELS.get(band, str(band))


def supported_mode_pairs(pairs) -> list[tuple[int, int]]:
    return [(int(allowed), int(preferred)) for allowed, preferred in pairs]


def mode_bits_label(bits: int) -> str:
    parts = [label for bit, label in MODE_LABELS.items() if bits & bit]
    return "+".join(parts) if parts else "none"


def apn_type_label(mask: int) -> str:
    names = [label for value, label in sorted(APN_TYPE_LABELS.items()) if mask & value]
    return "+".join(names)


def capability_label(capability: int) -> str:
    """Human name for a ModemCapability bitmask, e.g. 72 -> "LTE + 5G NR"."""
    parts = []
    for bit, nick in sorted(MODEM_CAPABILITY.items()):
        if not capability & bit:
            continue
        parts.append({
            "POTS": "POTS",
            "GSM_UMTS": "GSM/UMTS",
            "LTE": "LTE",
            "5GNR": "5G NR",
            "CDMA_EVDO": "CDMA/EVDO",
            "TDS": "TD-SCDMA",
            "IRIDIUM": "Iridium",
        }.get(nick, nick))
    label = " + ".join(parts) if parts else "none"
    return label
