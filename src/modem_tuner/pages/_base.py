"""Shared plumbing for the preference pages."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from ..client import Modem  # noqa: E402


class Page(Adw.PreferencesPage):
    """A page that binds to a modem and refreshes on property changes.

    Subclasses declare the interfaces they care about and implement refresh();
    bind() wires every present interface to changed(), which refreshes by
    default. Pages that need coalescing or a different reload path override
    changed() or bind().
    """

    interfaces: tuple[str, ...] = ()

    def __init__(self, window, **kwargs) -> None:
        super().__init__(**kwargs)
        self.window = window
        self.modem: Modem | None = None
        self._updating = False

    def bind(self, modem: Modem) -> None:
        self.modem = modem
        for interface in self.interfaces:
            if modem.has(interface):
                modem.signal(interface, "g-properties-changed", self.changed)
        self.on_bound(modem)
        self.reload()

    def on_bound(self, modem: Modem) -> None:
        """Hook for extra setup after the signals are connected."""

    def changed(self, *_args) -> None:
        self.refresh()

    def refresh(self) -> None:
        raise NotImplementedError

    def reload(self) -> None:
        self.refresh()
