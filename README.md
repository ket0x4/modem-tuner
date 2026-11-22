# Modem Tuner

A GTK 4 + libadwaita front end for ModemManager, built for phones running
postmarketOS and Plasma Mobile. It exposes the parts of the modem API that
`mmcli` can print but most graphical tools never show: preferred access mode,
individual band selection, capabilities, APN profiles, SIM PIN state, USSD,
signal polling and thresholds, AGPS, cell broadcast and SAR.

Every page reads live values over D-Bus and updates when ModemManager emits
`PropertiesChanged`, so no polling loop is needed.

## What it talks to

Plain `Gio.DBusProxy` on the **system bus**. No AT commands are parsed and no
ModemManager library is required beyond the typelib, which is used only to read
the enum values so the numbers always match the running ModemManager.

| Section | Interfaces |
| --- | --- |
| Status | `Modem`, `Modem.Modem3gpp`, `Modem.Signal`, Bearer objects |
| Radio | `Modem` (modes, capabilities, bands, power) |
| Network | `Modem.Modem3gpp`, `Modem.Modem3gpp.Ussd` |
| APN profiles | `Modem.Modem3gpp.ProfileManager` |
| SIM | `Sim` |
| Signal | `Modem.Signal` |
| Location | `Modem.Location` |
| Advanced | `Modem.Sar`, `Modem.Messaging`, `Modem.CellBroadcast`, `Modem.Firmware`, `Modem.Simple` |

## Permissions

ModemManager ships a D-Bus policy that denies most method calls to
unprivileged users and then re-allows a documented subset. Modem Tuner sends
the calls and shows the resulting error instead of hiding the control, so a
blocked feature (SAR is the common one) reads as
`permission denied by the system bus policy` rather than a silent failure.

To grant the missing methods, add a bus policy for the `wheel` group — this is
a system change, review it before applying:

```xml
<!-- /etc/dbus-1/system.d/50-modemmanager-wheel.conf -->
<busconfig>
  <policy group="wheel">
    <allow send_destination="org.freedesktop.ModemManager1"
           send_interface="org.freedesktop.ModemManager1.Modem.Sar"/>
  </policy>
</busconfig>
```

AT passthrough (`Modem.Command`) additionally requires ModemManager to run
with `--debug`; without it the daemon answers
`Operation only allowed in debug mode`.

## Running

Requires GTK 4, libadwaita 1, PyGObject and the ModemManager typelib
(`libmm-glib`).

```sh
PYTHONPATH=src python3 -m modem_tuner          # from the source tree
PYTHONPATH=src python3 -m modem_tuner --version
```

The window follows the modem as ModemManager adds or removes it, and offers a
Retry button when no modem is present. Long D-Bus operations show a spinner in
the header with a cancel button; the modem call itself cannot be aborted, so the
next property change refreshes the page either way.

or install it:

```sh
./install.sh                        # /usr/local, asks for sudo
PREFIX=~/.local ./install.sh        # per-user, no sudo needed
DESTDIR=/tmp/stage ./install.sh     # staging for a package
```

The installer checks for PyGObject, GTK 4, libadwaita and the ModemManager
typelib before copying anything, so a missing dependency fails with a clear
message instead of an import error at first launch.

## Layout

```
src/modem_tuner/
  app.py            application, actions, about dialog
  window.py         window, section menu, modem selection, hotplug watch
  client.py         ModemManager D-Bus client (Modem, Sim, Bearer, Message)
  constants.py      enum values and human labels
  widgets.py        shared rows, background tasks, list helpers
  pages/_base.py    shared bind/refresh plumbing for the pages
  pages/            one module per section
data/
  modem-tuner           launcher, resolves its own prefix
  *.desktop.in          desktop entry with @BINDIR@ substitution
  *.metainfo.xml        AppStream metadata
  *.svg                 application icon
install.sh          installs into PREFIX, supports DESTDIR and sudo
meson.build         alternative install path
pyproject.toml      packaging metadata and lint config
```

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 -m compileall -q src tests
```

`tests/test_live_modem.py` exercises the real modem and skips when none is
present. It also compares every client variant type against the introspected
D-Bus signatures, which catches struct/signature drift. CI runs the same checks
and validates the desktop entry and AppStream metadata.

## Notes on behaviour

- **Signal polling** is reset to `0` when the Signal page opens. ModemManager
  keeps the last rate for the lifetime of the daemon, and a non-zero rate keeps
  the modem awake, so polling is opt-in from that page.
- **SIM lock** is reported as `(not blocking)` when the modem is registered or
  connected: `UnlockRequired` keeps the last lock capability around even after
  the PIN was accepted.
- **Long operations** — network scan, register, PIN/PUK, band changes — run on
  a worker thread so the window stays responsive; scan can take a minute.
- Band selection writes the explicit list rather than `ANY`, because some
  Qualcomm modems silently ignore `ANY` after a band restriction was applied.
  The picker has a filter box and current/all/none presets.
- **Network selection** drops the active data bearer first: ModemManager
  refuses `Register` while a bearer is connected. The app asks before
  disconnecting, then registers automatic or the chosen operator.
- **Messaging** lists stored SMS and can create one; **cell broadcast** accepts
  ranges such as `4370-4380`. Firmware images can be selected when the modem
  reports a unique ID.

## Licence

MIT.
