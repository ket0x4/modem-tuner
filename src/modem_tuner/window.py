"""Main window: modem chooser and the settings pages."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .client import Modem, ModemError, list_modems, manager_version  # noqa: E402
from .pages.advanced import AdvancedPage  # noqa: E402
from .pages.location import LocationPage  # noqa: E402
from .pages.network import NetworkPage  # noqa: E402
from .pages.profiles import ProfilesPage  # noqa: E402
from .pages.radio import RadioPage  # noqa: E402
from .pages.signal import SignalPage  # noqa: E402
from .pages.sim import SimPage  # noqa: E402
from .pages.status import StatusPage  # noqa: E402


class ModemTunerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Modem Tuner")
        self._size_to_display()

        self.modem: Modem | None = None
        self._paths: list[str] = []

        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        self.header = Adw.HeaderBar()
        toolbar.add_top_bar(self.header)

        # A single long title ("Modem Tuner · QUALCOMM INCORPORATED") gets
        # ellipsised on a 360 px screen, so the modem name lives in the
        # subtitle where it has room to wrap.
        self.window_title = Adw.WindowTitle(title="Modem Tuner")
        self.header.set_title_widget(self.window_title)

        self.modem_button = Gtk.MenuButton(icon_name="emblem-system-symbolic")
        self.modem_button.set_tooltip_text("Select modem")
        self.modem_button.set_visible(False)
        self.header.pack_end(self.modem_button)

        reload_button = Gtk.Button(icon_name="view-refresh-symbolic")
        reload_button.set_tooltip_text("Re-read every value")
        reload_button.connect("clicked", lambda _b: self.reload())
        self.header.pack_end(reload_button)

        self.stack = Adw.ViewStack()

        # Eight sections in a bottom switcher get truncated on a phone-width
        # window, so the sections live in a menu in the header instead.
        self.section_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.section_button.set_tooltip_text("Sections")
        self.header.pack_start(self.section_button)
        self.section_menu = Gio.Menu()
        self.section_button.set_menu_model(self.section_menu)

        toolbar.set_content(self.stack)

        self.pages: dict[str, Adw.PreferencesPage] = {
            "status": StatusPage(self),
            "radio": RadioPage(self),
            "network": NetworkPage(self),
            "profiles": ProfilesPage(self),
            "sim": SimPage(self),
            "signal": SignalPage(self),
            "location": LocationPage(self),
            "advanced": AdvancedPage(self),
        }
        for page in self.pages.values():
            self.stack.add_titled(page, page.get_name(), page.get_title())
            icon = page.get_icon_name()
            if icon:
                self.stack.get_page(page).set_icon_name(icon)
            self.section_menu.append(page.get_title(), f"win.section::{page.get_name()}")

        section_action = Gio.SimpleAction.new("section", GLib.VariantType.new("s"))
        section_action.connect("activate", self._on_section_action)
        self.add_action(section_action)

        self._load_modems()

    def _size_to_display(self) -> None:
        """Open at the size of the screen rather than a desktop-sized window.

        Phones running Plasma Mobile report 360x800 logical pixels; a fixed
        440-wide default opened wider than the display, so the right edge of
        every page was cut off.
        """
        monitor = Gdk.Display.get_default().get_monitors().get_item(0)
        if monitor is None:
            self.set_default_size(360, 700)
            return
        geometry = monitor.get_geometry()
        self.set_default_size(min(geometry.width, 440), min(geometry.height, 820))

    # -- modem handling ---------------------------------------------------

    def _load_modems(self) -> None:
        try:
            self._paths = list_modems()
        except ModemError as exc:
            self._show_fatal(f"Cannot talk to ModemManager: {exc}")
            return
        if not self._paths:
            version = manager_version() or "unknown version"
            self._show_fatal(
                f"No modem found (ModemManager {version}). Check that the modem is "
                "powered on and that ModemManager detected it.")
            return

        if len(self._paths) > 1:
            menu = Gio.Menu()
            for path in self._paths:
                menu.append(path.rsplit("/", 1)[-1], f"win.select::{path}")
            self.modem_button.set_menu_model(menu)
            action = Gio.SimpleAction.new("select", GLib.VariantType.new("s"))
            action.connect("activate", self._on_select_action)
            self.get_application().add_action(action)

        self._attach(self._paths[0])

    def _on_select_action(self, _action, parameter) -> None:
        self._attach(parameter.get_string())

    def _on_section_action(self, _action, parameter) -> None:
        name = parameter.get_string()
        page = self.pages.get(name)
        if page is not None:
            self.stack.set_visible_child(page)
            self.window_title.set_title(page.get_title())

    def _attach(self, path: str) -> None:
        try:
            modem = Modem(path)
        except ModemError as exc:
            self._show_fatal(f"Cannot open {path}: {exc}")
            return
        self.modem = modem
        title = " ".join(part for part in (modem.manufacturer, modem.model) if part and part != "0")
        self.window_title.set_subtitle(title)
        for page in self.pages.values():
            try:
                page.bind(modem)
            except Exception as exc:  # noqa: BLE001 - one broken page must not hide the rest
                print(f"modem-tuner: page {page.get_name()} failed to bind: {exc}")

    def reload(self) -> None:
        if self.modem is None:
            self._load_modems()
            return
        for page in self.pages.values():
            try:
                if hasattr(page, "reload"):
                    page.reload()
                elif hasattr(page, "refresh"):
                    page.refresh()
            except Exception as exc:  # noqa: BLE001
                print(f"modem-tuner: reload {page.get_name()} failed: {exc}")

    def _show_fatal(self, message: str) -> None:
        page = Adw.PreferencesPage()
        group = Adw.PreferencesGroup(title="No modem available")
        group.add(Adw.ActionRow(title="What happened", subtitle=message))
        page.add(group)
        self.stack.add_titled(page, "error", "Error")
        self.stack.set_visible_child(page)
