"""APN profiles stored on the modem."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from .. import constants as C  # noqa: E402
from ..client import MODEM_3GPP_PROFILE  # noqa: E402
from ..widgets import (RowList, banner, button_row, confirm, dialog_size,  # noqa: E402
                       run_in_background, toast)
from ._base import Page  # noqa: E402


class ProfilesPage(Page):
    interfaces = (MODEM_3GPP_PROFILE,)

    def __init__(self, window) -> None:
        super().__init__(window, title="APN profiles",
                         icon_name="network-workgroup-symbolic", name="profiles")

        self._group = Adw.PreferencesGroup(
            title="Profiles",
            description="Bearer profiles the modem uses for data connections.",
        )
        self.add(self._group)

        self._list = RowList()
        self._group.add(self._list)

        self._group.add(button_row(
            "Add profile", "Create a new APN profile.", "Add", self._on_add))

    def on_bound(self, modem) -> None:
        if modem.has(MODEM_3GPP_PROFILE):
            self._connect_updated(modem)

    def _connect_updated(self, modem) -> None:
        try:
            modem.signal(MODEM_3GPP_PROFILE, "Updated", lambda *_a: self.refresh())
        except Exception:  # noqa: BLE001 - not all versions emit it
            pass

    def refresh(self) -> None:
        self._list.clear()
        if self.modem is None:
            return
        try:
            profiles = self.modem.list_profiles()
        except Exception as exc:  # noqa: BLE001
            self._list.add(banner(f"Cannot read profiles: {exc}"))
            return
        if not profiles:
            self._list.add(banner("The modem reports no profiles.", "info"))
            return
        for profile in profiles:
            self._add_row(profile)

    def _add_row(self, profile: dict) -> None:
        apn = str(profile.get("apn") or "(no APN)")
        name = str(profile.get("profile-name") or "")
        profile_id = profile.get("profile-id")
        apn_type = int(profile.get("apn-type", 0) or 0)
        ip_type = int(profile.get("ip-type", 0) or 0)
        enabled = bool(profile.get("profile-enabled", True))

        details = [
            f"id {profile_id}" if profile_id is not None else "",
            name,
            C.apn_type_label(apn_type),
            C.IP_TYPE_LABELS.get(ip_type, ""),
            "" if enabled else "disabled",
        ]
        row = Adw.ActionRow(title=apn, subtitle=" · ".join(d for d in details if d))

        edit = Gtk.Button(icon_name="document-edit-symbolic", valign=Gtk.Align.CENTER)
        edit.add_css_class("flat")
        edit.connect("clicked", lambda _b, p=profile: self._on_edit(p))
        row.add_suffix(edit)

        delete = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER)
        delete.add_css_class("flat")
        delete.connect("clicked", lambda _b, p=profile: self._on_delete(p))
        row.add_suffix(delete)

        self._list.add(row)

    # -- actions ----------------------------------------------------------

    def _on_add(self) -> None:
        self._edit_profile({})

    def _on_edit(self, profile: dict) -> None:
        self._edit_profile(profile)

    def _edit_profile(self, profile: dict) -> None:
        dialog = ProfileDialog(self.window, profile, self._save_profile)
        dialog.present(self.get_root() or self.window)

    def _save_profile(self, profile: dict) -> None:
        if self.modem is None:
            return

        def done(_result, error) -> None:
            if error is not None:
                toast(self.window, f"Save failed: {error}")
            else:
                toast(self.window, "Profile saved")
                self.refresh()

        run_in_background(self.window, lambda: self.modem.set_profile(profile), done)

    def _on_delete(self, profile: dict) -> None:
        if self.modem is None:
            return
        apn = str(profile.get("apn") or "(no APN)")

        def do_delete() -> None:
            def done(_result, error) -> None:
                if error is not None:
                    toast(self.window, f"Delete failed: {error}")
                else:
                    toast(self.window, "Profile deleted")
                    self.refresh()

            run_in_background(self.window, lambda: self.modem.delete_profile(profile), done)

        confirm(self.window, "Delete profile?", f"APN {apn} will be removed.",
                "Delete", do_delete, destructive=True)


class ProfileDialog(Adw.Dialog):
    def __init__(self, window, profile: dict, on_save) -> None:
        super().__init__()
        self.window = window
        self.profile = dict(profile)
        self.on_save = on_save

        self.set_title("APN profile")
        self.set_content_width(dialog_size(400, 0)[0])

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(False)
        toolbar.add_top_bar(header)

        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")
        save.connect("clicked", lambda _b: self._save())
        header.pack_end(save)

        page = Adw.PreferencesPage()
        toolbar.set_content(page)
        self.set_child(toolbar)

        group = Adw.PreferencesGroup()
        page.add(group)

        self._apn = Adw.EntryRow(title="APN")
        self._apn.set_text(str(profile.get("apn") or ""))
        group.add(self._apn)

        self._name = Adw.EntryRow(title="Profile name")
        self._name.set_text(str(profile.get("profile-name") or ""))
        group.add(self._name)

        self._user = Adw.EntryRow(title="Username")
        self._user.set_text(str(profile.get("user") or ""))
        group.add(self._user)

        self._password = Adw.PasswordEntryRow(title="Password")
        self._password.set_text(str(profile.get("password") or ""))
        group.add(self._password)

        auth_codes = [name for _value, name in sorted(C.AUTH_LABELS.items())]
        self._auth_values = [value for value, _name in sorted(C.AUTH_LABELS.items())]
        self._auth = Adw.ComboRow(title="Authentication")
        self._auth.set_model(Gtk.StringList.new(auth_codes))
        auth = int(profile.get("allowed-auth", 1) or 1)
        if auth in self._auth_values:
            self._auth.set_selected(self._auth_values.index(auth))
        group.add(self._auth)

        self._ip_values = C.IP_TYPE_VALUES
        self._ip = Adw.ComboRow(title="IP type")
        self._ip.set_model(Gtk.StringList.new(C.IP_TYPE_DIALOG_LABELS))
        current_ip = int(profile.get("ip-type", 3) or 3)
        self._ip.set_selected(self._ip_values.index(current_ip)
                              if current_ip in self._ip_values else 0)
        group.add(self._ip)

        self._apn_type_checks: dict[int, Gtk.CheckButton] = {}
        type_group = Adw.PreferencesGroup(
            title="APN types",
            description="At least one type is required by most networks.",
        )
        page.add(type_group)
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(3)
        flow.set_row_spacing(4)
        flow.set_column_spacing(4)
        flow.set_margin_top(8)
        flow.set_margin_bottom(8)
        flow.set_margin_start(12)
        flow.set_margin_end(12)
        active_types = int(profile.get("apn-type", 2) or 2)
        for value, label in sorted(C.APN_TYPE_LABELS.items()):
            check = Gtk.CheckButton(label=label)
            check.set_active(bool(active_types & value))
            check.add_css_class("card")
            self._apn_type_checks[value] = check
            flow.append(check)
        type_group.add(flow)

        self._enabled = Adw.SwitchRow(title="Enabled")
        self._enabled.set_active(bool(profile.get("profile-enabled", True)))
        type_group.add(self._enabled)

    def _save(self) -> None:
        apn_type = 0
        for value, check in self._apn_type_checks.items():
            if check.get_active():
                apn_type |= value

        result: dict = dict(self.profile)
        result["apn"] = self._apn.get_text().strip()
        result["profile-name"] = self._name.get_text().strip()
        result["user"] = self._user.get_text().strip()
        result["password"] = self._password.get_text()
        result["allowed-auth"] = self._auth_values[max(0, self._auth.get_selected())]
        result["ip-type"] = self._ip_values[max(0, self._ip.get_selected())]
        result["apn-type"] = apn_type or 2
        result["profile-enabled"] = self._enabled.get_active()

        if not result["apn"]:
            toast(self.window, "An APN is required")
            return

        self.on_save(result)
        self.close()
