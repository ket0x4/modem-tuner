"""Main window: modem chooser and the settings pages."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from .client import (Modem, ModemError, list_modems, manager_version,  # noqa: E402
                     watch_modems)
from .pages import (AdvancedPage, LocationPage, NetworkPage, ProfilesPage,  # noqa: E402
                    RadioPage, SignalPage, SimPage, StatusPage)
from .widgets import button_row, display_size  # noqa: E402


class ModemTunerWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("Modem Tuner")
        self._size_to_display()

        self.modem: Modem | None = None
        self._paths: list[str] = []
        self._pending_reload = False
        self._select_action: Gio.SimpleAction | None = None
        self._error_page: Adw.PreferencesPage | None = None
        self._error_group: Adw.PreferencesGroup | None = None
        self._error_row: Adw.ActionRow | None = None
        self._tasks: set = set()

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

        self.busy_spinner = Gtk.Spinner()
        self.busy_spinner.set_visible(False)
        self.header.pack_end(self.busy_spinner)

        self.cancel_button = Gtk.Button(icon_name="process-stop-symbolic")
        self.cancel_button.set_tooltip_text("Cancel the running operation")
        self.cancel_button.set_visible(False)
        self.cancel_button.connect("clicked", lambda _b: self.cancel_tasks())
        self.header.pack_end(self.cancel_button)

        reload_button = Gtk.Button(icon_name="view-refresh-symbolic")
        reload_button.set_tooltip_text("Re-read every value")
        reload_button.connect("clicked", lambda _b: self.reload())
        self.header.pack_end(reload_button)

        self.stack = Adw.ViewStack()
        self.stack.set_vexpand(True)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(self._build_error_banner())
        content.append(self.stack)
        toolbar.set_content(content)

        # Eight sections in a bottom switcher get truncated on a phone-width
        # window, so the sections live in a menu in the header instead.
        self.section_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.section_button.set_tooltip_text("Sections")
        self.header.pack_start(self.section_button)
        self.section_menu = Gio.Menu()
        self.section_button.set_menu_model(self.section_menu)

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
        self._watcher = watch_modems(self._schedule_modem_reload)

    def _build_error_banner(self) -> Gtk.Revealer:
        self._error_revealer = Gtk.Revealer()
        self._error_revealer.set_transition_type(
            Gtk.RevealerTransitionType.SLIDE_DOWN)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.add_css_class("card")
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(12)
        box.set_margin_end(12)

        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        icon.set_valign(Gtk.Align.START)
        self._error_label = Gtk.Label(xalign=0, wrap=True, selectable=True,
                                      hexpand=True)
        self._error_label.add_css_class("caption")
        close = Gtk.Button(icon_name="window-close-symbolic",
                           valign=Gtk.Align.CENTER)
        close.add_css_class("flat")
        close.set_tooltip_text("Dismiss")
        close.connect("clicked", lambda _b: self.clear_error())

        box.append(icon)
        box.append(self._error_label)
        box.append(close)
        self._error_revealer.set_child(box)
        return self._error_revealer

    def report_error(self, message: str) -> None:
        """Keep a failure visible instead of letting it fall out of a toast."""
        self._error_label.set_text(message)
        self._error_revealer.set_reveal_child(True)

    def clear_error(self) -> None:
        self._error_revealer.set_reveal_child(False)

    # -- background activity ----------------------------------------------

    def register_task(self, task) -> None:
        self._tasks.add(task)
        self._update_busy()

    def unregister_task(self, task) -> None:
        self._tasks.discard(task)
        self._update_busy()

    def _update_busy(self) -> None:
        busy = bool(self._tasks)
        self.busy_spinner.set_visible(busy)
        if busy:
            self.busy_spinner.start()
        else:
            self.busy_spinner.stop()
        self.cancel_button.set_visible(busy)

    def cancel_tasks(self) -> None:
        for task in list(self._tasks):
            task.cancel()

    def _size_to_display(self) -> None:
        """Open at the size of the screen rather than a desktop-sized window.

        Phones running Plasma Mobile report 360x800 logical pixels; a fixed
        440-wide default opened wider than the display, so the right edge of
        every page was cut off.
        """
        width, height = display_size()
        self.set_default_size(min(width, 440), min(height, 820))

    # -- modem handling ---------------------------------------------------

    def _load_modems(self) -> None:
        try:
            paths = list_modems()
        except ModemError as exc:
            self._show_error("Cannot talk to ModemManager", str(exc))
            return
        self._paths = paths
        if not paths:
            version = manager_version() or "unknown version"
            self._show_error(
                "No modem found",
                f"ModemManager {version} is running but reports no modem. "
                "Check that the modem is powered on and detected.")
            return

        self._update_modem_menu()
        if self.modem is None or self.modem.path not in paths:
            self._attach(paths[0])
        else:
            self.reload()
        if (self.stack.get_visible_child() is self._error_page
                and self.modem is not None):
            self.stack.set_visible_child(self.pages["status"])
            self.window_title.set_title("Status")

    def _update_modem_menu(self) -> None:
        multiple = len(self._paths) > 1
        self.modem_button.set_visible(multiple)
        if not multiple:
            return
        menu = Gio.Menu()
        for path in self._paths:
            menu.append(path.rsplit("/", 1)[-1], f"win.select::{path}")
        self.modem_button.set_menu_model(menu)
        if self._select_action is None:
            self._select_action = Gio.SimpleAction.new(
                "select", GLib.VariantType.new("s"))
            self._select_action.connect("activate", self._on_select_action)
            self.add_action(self._select_action)

    def _schedule_modem_reload(self) -> None:
        if self._pending_reload:
            return
        self._pending_reload = True
        GLib.timeout_add(300, self._reload_after_change)

    def _reload_after_change(self) -> bool:
        self._pending_reload = False
        self._load_modems()
        return GLib.SOURCE_REMOVE

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
            self._show_error("Cannot open the modem", str(exc))
            return
        self.modem = modem
        self.clear_error()
        title = " ".join(part for part in (modem.manufacturer, modem.model)
                         if part and part != "0")
        self.window_title.set_subtitle(title)
        for page in self.pages.values():
            try:
                page.bind(modem)
            except Exception as exc:  # noqa: BLE001 - one broken page must not hide the rest
                print(f"modem-tuner: page {page.get_name()} failed to bind: {exc}")
        if self.stack.get_visible_child() is self._error_page:
            self.stack.set_visible_child(self.pages["status"])
            self.window_title.set_title("Status")

    def reload(self) -> None:
        if self.modem is None:
            self._load_modems()
            return
        self.clear_error()
        for page in self.pages.values():
            try:
                page.reload()
            except Exception as exc:  # noqa: BLE001
                print(f"modem-tuner: reload {page.get_name()} failed: {exc}")

    def _show_error(self, title: str, message: str) -> None:
        if self._error_page is None:
            self._error_page = Adw.PreferencesPage()
            self._error_group = Adw.PreferencesGroup(title="Modem unavailable")
            self._error_row = Adw.ActionRow(title="What happened")
            self._error_group.add(self._error_row)
            self._error_group.add(button_row(
                "Retry", "Look for the modem again.", "Retry", self._load_modems))
            self._error_page.add(self._error_group)
            self.stack.add_titled(self._error_page, "error", "Error")
        self._error_group.set_title(title)
        self._error_row.set_subtitle(message)
        self.stack.set_visible_child(self._error_page)
        self.window_title.set_title("Error")
