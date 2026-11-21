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
python3 -m modem_tuner          # from the source tree, with PYTHONPATH=src
```

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
  window.py         window, section menu, modem selection
  client.py         ModemManager D-Bus client (Modem, Sim)
  constants.py      enum values and human labels
  widgets.py        shared rows, background worker, list helpers
  pages/            one module per section
data/
  modem-tuner           launcher, resolves its own prefix
  *.desktop.in          desktop entry with @BINDIR@ substitution
  *.svg                 application icon
install.sh          installs into PREFIX, supports DESTDIR and sudo
```

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

## Licence

MIT.
