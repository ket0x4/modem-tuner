"""Shared widgets and helpers for the pages."""

from __future__ import annotations

import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402


def toast(window, message: str) -> None:
    """Show a transient message at the bottom of the window."""
    overlay = getattr(window, "toast_overlay", None)
    if overlay is not None:
        overlay.add_toast(Adw.Toast.new(message))


def run_in_background(window, task, on_done, busy_widget=None) -> None:
    """Run a blocking call off the main loop.

    Scan, Register and PIN operations talk to the modem over AT and can take
    tens of seconds; doing them inline freezes the whole window.
    """
    if busy_widget is not None:
        busy_widget.set_sensitive(False)

    def worker() -> None:
        try:
            result = task()
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            error = exc
        else:
            error = None
        GLib.idle_add(finish, result if error is None else None, error)

    def finish(result, error) -> bool:
        if busy_widget is not None:
            busy_widget.set_sensitive(True)
        on_done(result, error)
        return GLib.SOURCE_REMOVE

    threading.Thread(target=worker, daemon=True).start()


def value_row(title: str, value: str = "", subtitle: str = "") -> Adw.ActionRow:
    row = Adw.ActionRow(title=title, subtitle=subtitle or None)
    label = Gtk.Label(label=value)
    label.add_css_class("dim-label")
    label.set_selectable(True)
    label.set_valign(Gtk.Align.CENTER)
    row.add_suffix(label)
    row.value_label = label
    return row


def switch_row(title: str, subtitle: str = "", active: bool = False,
               on_toggle=None) -> Adw.SwitchRow:
    row = Adw.SwitchRow(title=title, subtitle=subtitle or None, active=active)
    if on_toggle is not None:
        row.connect("notify::active", lambda r, _p: on_toggle(r.get_active()))
    return row


def combo_row(title: str, subtitle: str = "", options: list[str] | None = None,
              selected: int = -1, on_select=None) -> Adw.ComboRow:
    row = Adw.ComboRow(title=title, subtitle=subtitle or None)
    row.set_model(Gtk.StringList.new(options or []))
    if selected >= 0:
        row.set_selected(selected)
    if on_select is not None:
        row.connect("notify::selected", lambda r, _p: on_select(r.get_selected()))
    return row


def spin_row(title: str, subtitle: str = "", value: float = 0.0,
             lower: float = 0.0, upper: float = 100.0, step: float = 1.0,
             digits: int = 0, on_change=None) -> Adw.SpinRow:
    adjustment = Gtk.Adjustment(value=value, lower=lower, upper=upper,
                                step_increment=step, page_increment=step * 10)
    row = Adw.SpinRow(title=title, subtitle=subtitle or None,
                      adjustment=adjustment, digits=digits)
    if on_change is not None:
        row.connect("notify::value", lambda r, _p: on_change(r.get_value()))
    return row


def entry_row(title: str, subtitle: str = "", text: str = "", placeholder: str = "",
              on_apply=None, apply_label: str = "Apply") -> Adw.EntryRow:
    row = Adw.EntryRow(title=title)
    if subtitle:
        row.set_tooltip_text(subtitle)
    if placeholder:
        row.set_show_apply_button(True)
    row.set_text(text)

    def apply(_row) -> None:
        if on_apply is not None:
            on_apply(row.get_text())

    row.connect("apply", apply)
    if on_apply is not None:
        row.set_show_apply_button(True)
        row.set_apply_label(apply_label) if hasattr(row, "set_apply_label") else None
    return row


def button_row(title: str, subtitle: str = "", button_label: str = "Apply",
               on_click=None, destructive: bool = False) -> Adw.ActionRow:
    row = Adw.ActionRow(title=title, subtitle=subtitle or None)
    button = Gtk.Button(label=button_label, valign=Gtk.Align.CENTER)
    if destructive:
        button.add_css_class("destructive-action")
    if on_click is not None:
        button.connect("clicked", lambda _b: on_click())
    row.add_suffix(button)
    row.button = button
    return row


def confirm(window, heading: str, body: str, label: str, on_confirm,
            destructive: bool = False) -> None:
    dialog = Adw.AlertDialog(heading=heading, body=body)
    dialog.add_cancel("Cancel")
    dialog.add_response("ok", label)
    if destructive:
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
    else:
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")

    def answered(_dialog, response: str) -> None:
        if response == "ok":
            on_confirm()

    dialog.connect("response", answered)
    dialog.present(window)


def prompt(window, heading: str, body: str, label: str, on_accept,
           password: bool = False, placeholder: str = "") -> None:
    dialog = Adw.AlertDialog(heading=heading, body=body)
    entry = Gtk.Entry()
    entry.set_visibility(not password)
    entry.set_input_purpose(Gtk.InputPurpose.PASSWORD if password else Gtk.InputPurpose.FREE_FORM)
    if placeholder:
        entry.set_placeholder_text(placeholder)
    dialog.set_extra_child(entry)
    dialog.add_cancel("Cancel")
    dialog.add_response("ok", label)
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("ok")
    dialog.set_close_response("cancel")

    def answered(_dialog, response: str) -> None:
        if response == "ok":
            on_accept(entry.get_text())

    dialog.connect("response", answered)
    dialog.present(window)


def banner(text: str, css: str = "warning") -> Gtk.Box:
    """An inline note used when a feature is blocked by the bus policy."""
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
    box.add_css_class("card")
    box.set_margin_top(6)
    box.set_margin_bottom(6)
    icon = Gtk.Image.new_from_icon_name("dialog-information-symbolic")
    icon.set_valign(Gtk.Align.START)
    label = Gtk.Label(label=text, wrap=True, xalign=0)
    label.add_css_class("caption")
    label.set_hexpand(True)
    box.append(icon)
    box.append(label)
    return box


def monospace(text: str = "", wrap: bool = True) -> Gtk.Label:
    label = Gtk.Label(label=text, xalign=0, wrap=wrap)
    label.add_css_class("monospace")
    label.add_css_class("caption")
    label.set_selectable(True)
    return label


def panel(widget: Gtk.Widget) -> Gtk.ListBoxRow:
    """Wrap a free-form widget so it lines up with the rows in a group.

    Adw.PreferencesGroup places children in a list box, so a bare label or
    button ends up flush against the edges while the Adw rows around it keep
    their padding. Wrapping keeps the whole group on the same grid.
    """
    row = Gtk.ListBoxRow()
    row.set_activatable(False)
    row.set_selectable(False)
    row.set_child(widget)
    widget.set_margin_top(10)
    widget.set_margin_bottom(10)
    widget.set_margin_start(12)
    widget.set_margin_end(12)
    return row


class RowList(Gtk.ListBox):
    """A list box that accepts Adw rows and plain widgets alike.

    AdwActionRow refuses to live in a GtkBox, and the rows built dynamically on
    the pages (bearers, scan results, firmware images) need a list box. Plain
    widgets such as the inline banners are wrapped in a row so both can share
    one container.
    """

    def __init__(self) -> None:
        super().__init__()
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.add_css_class("boxed-list")
        self.set_valign(Gtk.Align.START)

    def add(self, widget: Gtk.Widget) -> None:
        if isinstance(widget, (Adw.ActionRow, Adw.SwitchRow, Adw.EntryRow,
                               Adw.ComboRow, Adw.SpinRow, Adw.ExpanderRow)):
            self.append(widget)
            return
        row = Gtk.ListBoxRow()
        row.set_activatable(False)
        row.set_selectable(False)
        row.set_child(widget)
        row.add_css_class("boxed-list-row")
        self.append(row)

    def clear(self) -> None:
        while (child := self.get_first_child()) is not None:
            self.remove(child)
