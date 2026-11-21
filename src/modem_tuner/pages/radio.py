"""Radio configuration: preferred mode, capabilities and band selection."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("GLib", "2.0")

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from .. import constants as C  # noqa: E402
from ..client import MODEM_IFACE, Modem  # noqa: E402
from ..widgets import banner, panel, run_in_background  # noqa: E402

CAPABILITY_LABELS = [
    (C.MODEM_CAPABILITY.get(1, 1), "POTS"),
    (C.MODEM_CAPABILITY.get(4, 4), "GSM/UMTS"),
    (C.MODEM_CAPABILITY.get(8, 8), "LTE"),
    (C.MODEM_CAPABILITY.get(64, 64), "5G NR"),
]


class RadioPage(Adw.PreferencesPage):
    def __init__(self, window) -> None:
        super().__init__(title="Radio", icon_name="network-modem-symbolic",
                         name="radio")
        self.window = window
        self.modem: Modem | None = None
        self._updating = False

        self._mode_group = Adw.PreferencesGroup(
            title="Preferred network mode",
            description="The modem registers using this combination. "
                        "5G preferred keeps LTE as a fallback.",
        )
        self.add(self._mode_group)

        self._mode_row = Adw.ComboRow(title="Mode")
        self._mode_row.connect("notify::selected", self._on_mode_chosen)
        self._mode_group.add(self._mode_row)
        self._mode_values: list[tuple[int, int]] = []

        self._caps_group = Adw.PreferencesGroup(
            title="Radio capabilities",
            description="Which radio access technologies the modem exposes.",
        )
        self.add(self._caps_group)

        self._caps_row = Adw.ComboRow(title="Capabilities")
        self._caps_row.connect("notify::selected", self._on_caps_chosen)
        self._caps_group.add(self._caps_row)
        self._caps_values: list[int] = []

        self._band_group = Adw.PreferencesGroup(
            title="Bands",
            description="Locking bands can improve stability but may drop coverage. "
                        "Select the bands the modem should use.",
        )
        self.add(self._band_group)

        self._band_actions = Adw.ActionRow(
            title="Band selection",
            subtitle="Choose individual bands per technology",
        )
        open_button = Gtk.Button(label="Choose", valign=Gtk.Align.CENTER)
        open_button.connect("clicked", self._open_band_dialog)
        self._band_actions.add_suffix(open_button)
        self._band_group.add(self._band_actions)

        self._band_summary = Adw.ActionRow(
            title="Current bands", subtitle="—")
        self._band_group.add(self._band_summary)

        self._reset_all = Adw.ActionRow(
            title="Use all supported bands",
            subtitle="Remove any band restriction")
        reset_button = Gtk.Button(label="Unlock", valign=Gtk.Align.CENTER)
        reset_button.connect("clicked", self._reset_bands)
        self._reset_all.add_suffix(reset_button)
        self._reset_all.button = reset_button
        self._band_group.add(self._reset_all)

        self._power_group = Adw.PreferencesGroup(title="Power")
        self.add(self._power_group)

        self._power_row = Adw.ComboRow(title="Power state")
        self._power_row.set_model(Gtk.StringList.new(["Off", "Low", "On"]))
        self._power_row.connect("notify::selected", self._on_power_chosen)
        self._power_group.add(self._power_row)

        self._reset_button = Gtk.Button(label="Reset modem")
        self._reset_button.add_css_class("destructive-action")
        self._reset_button.connect("clicked", self._on_reset)
        self._power_group.add(panel(self._reset_button))

    # -- binding ----------------------------------------------------------

    def bind(self, modem: Modem) -> None:
        self.modem = modem
        if modem.has(MODEM_IFACE):
            modem.signal(MODEM_IFACE, "g-properties-changed", self._on_change)
        self.refresh()

    def _on_change(self, *_args) -> None:
        self.refresh()

    def refresh(self) -> None:
        modem = self.modem
        if modem is None:
            return
        self._updating = True
        try:
            self._refresh_modes(modem)
            self._refresh_capabilities(modem)
            self._refresh_bands(modem)
            self._refresh_power(modem)
        finally:
            self._updating = False

    def _refresh_modes(self, modem: Modem) -> None:
        supported = modem.supported_modes
        current = modem.current_modes
        self._mode_values = supported
        labels = []
        for allowed, preferred in supported:
            text = C.mode_bits_label(allowed)
            if preferred:
                text += f" (preferred {C.mode_bits_label(preferred)})"
            labels.append(text)
        self._mode_row.set_model(Gtk.StringList.new(labels))
        index = supported.index(current) if current in supported else -1
        self._mode_row.set_selected(index)
        self._mode_row.set_sensitive(bool(supported))

    def _refresh_capabilities(self, modem: Modem) -> None:
        supported = [cap for cap in modem.supported_capabilities]
        current = modem.current_capabilities
        self._caps_values = supported
        labels = [C.capability_label(cap) for cap in supported]
        self._caps_row.set_model(Gtk.StringList.new(labels))
        self._caps_row.set_selected(supported.index(current) if current in supported else -1)
        self._caps_row.set_sensitive(bool(supported))

    def _refresh_bands(self, modem: Modem) -> None:
        current = modem.current_bands
        supported = modem.supported_bands
        if set(current) >= {C.ANY_BAND}:
            text = "All supported bands"
        elif not current:
            text = "None reported"
        else:
            text = ", ".join(C.band_label(band) for band in current[:12])
            if len(current) > 12:
                text += f" … (+{len(current) - 12})"
        self._band_summary.set_subtitle(text)
        self._band_summary.set_tooltip_text(
            f"{len(current)} of {len(supported)} supported bands active")

    def _refresh_power(self, modem: Modem) -> None:
        state = modem.power_state
        index = {1: 0, 2: 1, 3: 2}.get(state, -1)
        self._power_row.set_selected(index)

    # -- actions ----------------------------------------------------------

    def _apply(self, label: str, task, on_done=None) -> None:
        def finished(result, error) -> None:
            if error is not None:
                from ..widgets import toast
                toast(self.window, f"{label} failed: {error}")
            else:
                if on_done is not None:
                    on_done(result)
                self.refresh()

        run_in_background(self.window, task, finished, self._mode_row)

    def _on_mode_chosen(self, row, _param) -> None:
        if self._updating or self.modem is None:
            return
        index = row.get_selected()
        if index < 0 or index >= len(self._mode_values):
            return
        allowed, preferred = self._mode_values[index]
        self._apply(f"Mode {C.mode_bits_label(allowed)}",
                    lambda: self.modem.set_current_modes(allowed, preferred))

    def _on_caps_chosen(self, row, _param) -> None:
        if self._updating or self.modem is None:
            return
        index = row.get_selected()
        if index < 0 or index >= len(self._caps_values):
            return
        capabilities = self._caps_values[index]
        self._apply(f"Capabilities {C.MODEM_CAPABILITY.get(capabilities, capabilities)}",
                    lambda: self.modem.set_current_capabilities(capabilities))

    def _on_power_chosen(self, row, _param) -> None:
        if self._updating or self.modem is None:
            return
        state = {0: C.MODEM_POWER_STATE.get(1, 1),
                 1: C.MODEM_POWER_STATE.get(2, 2),
                 2: C.MODEM_POWER_STATE.get(3, 3)}.get(row.get_selected())
        if state is None:
            return
        self._apply(f"Power state {C.POWER_STATE_LABELS.get(state, state)}",
                    lambda: self.modem.set_power_state(state))

    def _on_reset(self) -> None:
        from ..widgets import confirm, toast

        def do_reset() -> None:
            try:
                self.modem.reset()
                toast(self.window, "Modem reset requested")
            except Exception as exc:  # noqa: BLE001
                toast(self.window, f"Reset failed: {exc}")

        confirm(self.window, "Reset the modem?",
                "The modem restarts and the connection drops briefly.",
                "Reset", do_reset, destructive=True)

    def _open_band_dialog(self) -> None:
        if self.modem is None:
            return
        BandDialog(self.window, self.modem, on_saved=self.refresh).present(
            self.get_root() or self.window)

    def _reset_bands(self) -> None:
        if self.modem is None:
            return
        self._apply("Unlock all bands",
                    lambda: self.modem.set_current_bands([C.ANY_BAND]))


class BandDialog(Adw.Dialog):
    """Per-technology band picker."""

    def __init__(self, window, modem: Modem, on_saved=None) -> None:
        super().__init__()
        self.window = window
        self.modem = modem
        self.on_saved = on_saved
        self._checks: dict[int, Gtk.CheckButton] = {}

        self.set_title("Band selection")
        self.set_content_width(420)
        self.set_content_height(620)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        save = Gtk.Button(label="Apply")
        save.add_css_class("suggested-action")
        save.connect("clicked", self._save)
        header.pack_end(save)

        page = Adw.PreferencesPage()
        toolbar.set_content(page)
        self.set_child(toolbar)

        supported = modem.supported_bands
        current = set(modem.current_bands)
        everything = C.ANY_BAND in current or not current

        families: dict[str, list[int]] = {}
        for band in supported:
            families.setdefault(C.band_family(band), []).append(band)

        for family in ("LTE", "5G NR", "UMTS", "GSM", "CDMA"):
            bands = sorted(families.get(family, []))
            if not bands:
                continue
            group = Adw.PreferencesGroup(title=family)
            page.add(group)

            all_button = Gtk.Button(label="All")
            all_button.add_css_class("flat")
            all_button.set_valign(Gtk.Align.CENTER)
            all_button.connect("clicked", lambda _b, b=bands: self._set_all(b, True))
            none_button = Gtk.Button(label="None")
            none_button.add_css_class("flat")
            none_button.set_valign(Gtk.Align.CENTER)
            none_button.connect("clicked", lambda _b, b=bands: self._set_all(b, False))
            group.set_header_suffix(_box(all_button, none_button))

            flow = Gtk.FlowBox()
            flow.set_selection_mode(Gtk.SelectionMode.NONE)
            flow.set_max_children_per_line(4)
            flow.set_min_children_per_line(3)
            flow.set_row_spacing(4)
            flow.set_column_spacing(4)
            flow.set_margin_top(8)
            flow.set_margin_bottom(8)
            flow.set_margin_start(12)
            flow.set_margin_end(12)

            for band in bands:
                check = Gtk.CheckButton(label=C.band_label(band))
                check.set_active(everything or band in current)
                check.add_css_class("card")
                self._checks[band] = check
                flow.append(check)

            group.add(flow)

        if not supported:
            page.add(banner("This modem does not report its supported bands."))

    def _set_all(self, bands: list[int], active: bool) -> None:
        for band in bands:
            check = self._checks.get(band)
            if check is not None:
                check.set_active(active)

    def _save(self) -> None:
        selected = [band for band, check in self._checks.items() if check.get_active()]
        if not selected:
            from ..widgets import toast
            toast(self.window, "Select at least one band")
            return

        def task():
            self.modem.set_current_bands(selected)

        def done(result, error) -> None:
            from ..widgets import toast
            if error is not None:
                toast(self.window, f"Band update failed: {error}")
            else:
                toast(self.window, f"{len(selected)} bands applied")
                if self.on_saved is not None:
                    self.on_saved()
            self.close()

        run_in_background(self.window, task, done)


def _box(*children) -> Gtk.Box:
    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
    for child in children:
        box.append(child)
    return box
