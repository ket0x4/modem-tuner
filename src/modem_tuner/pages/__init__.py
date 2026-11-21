"""Pages, one per ModemManager area."""

from .advanced import AdvancedPage
from .location import LocationPage
from .network import NetworkPage
from .profiles import ProfilesPage
from .radio import RadioPage
from .signal import SignalPage
from .sim import SimPage
from .status import StatusPage

__all__ = [
    "AdvancedPage", "LocationPage", "NetworkPage", "ProfilesPage",
    "RadioPage", "SignalPage", "SimPage", "StatusPage",
]
