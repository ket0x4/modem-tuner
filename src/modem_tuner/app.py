"""Application entry point."""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, Gtk  # noqa: E402

from .window import ModemTunerWindow  # noqa: E402

APP_ID = "io.github.modemtuner.ModemTuner"
VERSION = "1.0.0"


class ModemTunerApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window: ModemTunerWindow | None = None
        self._build_actions()

    def _build_actions(self) -> None:
        for name, callback, accels in (
            ("reload", lambda *_: self.window.reload() if self.window else None,
             ["<primary>r", "F5"]),
            ("quit", lambda *_: self.quit(), ["<primary>q"]),
            ("about", self._on_about, []),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accels:
                self.set_accels_for_action(f"app.{name}", accels)

    def _on_about(self, *_args) -> None:
        about = Adw.AboutDialog(
            application_name="Modem Tuner",
            application_icon=APP_ID,
            developer_name="modem-tuner",
            version=VERSION,
            comments="Fine-grained control over a ModemManager modem: preferred "
                     "mode, bands, APN profiles, SIM PIN, USSD, signal polling "
                     "and the less obvious interfaces.",
            website="https://github.com/modem-tuner/modem-tuner",
            issue_url="https://github.com/modem-tuner/modem-tuner/issues",
            license_type=Gtk.License.MIT_X11,
        )
        about.add_credit_section(
            "Built with",
            ["GTK 4", "libadwaita", "ModemManager (libmm-glib typelib)"])
        about.present(self.window)

    def do_activate(self) -> None:
        if self.window is None:
            self.window = ModemTunerWindow(application=self)
        self.window.present()

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)


def main(argv: list[str] | None = None) -> int:
    app = ModemTunerApp()
    return app.run(argv if argv is not None else sys.argv)
