#!/bin/sh
set -eu

PREFIX=${PREFIX:-/usr/local}
DESTDIR=${DESTDIR:-}
DATADIR=${DATADIR:-$PREFIX/share}
LIBDIR="$PREFIX/lib/modem-tuner"
BINDIR="$PREFIX/bin"
APPID=io.github.modemtuner.ModemTuner

ROOT=$DESTDIR

DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

run() {
    if [ -n "$ROOT" ] || [ "$(id -u)" -eq 0 ] || [ -n "$WRITABLE" ]; then
        "$@"
    else
        sudo -- "$@"
    fi
}

# Installing under $HOME needs no privilege escalation, and sudo would fail
# outright when the script runs without a terminal. Only escalate when the
# destination really is outside the current user's reach.
WRITABLE=
if [ -d "$PREFIX" ] && [ -w "$PREFIX" ]; then
    WRITABLE=1
elif [ ! -e "$PREFIX" ] && [ -w "$(dirname "$PREFIX")" ]; then
    WRITABLE=1
fi

info() {
    printf '%s\n' "$*"
}

info "Checking dependencies"
missing=
if ! python3 -c "import gi" >/dev/null 2>&1; then
    missing="$missing python3-gobject"
fi
if ! python3 -c "import gi; gi.require_version('Gtk', '4.0')" >/dev/null 2>&1; then
    missing="$missing gtk4"
fi
if ! python3 -c "import gi; gi.require_version('Adw', '1')" >/dev/null 2>&1; then
    missing="$missing libadwaita"
fi
if ! python3 -c "import gi; gi.require_version('ModemManager', '1.0')" >/dev/null 2>&1; then
    missing="$missing libmm-glib"
fi
if [ -n "$missing" ]; then
    info "Missing dependencies:$missing"
    info "Modem Tuner needs PyGObject, GTK 4, libadwaita 1 and the ModemManager"
    info "typelib. Install them and run this script again."
    exit 1
fi

info "Installing Modem Tuner into $ROOT$PREFIX"

# Source files, one install call per file so a partial copy is obvious and the
# installed tree carries no __pycache__ from the checkout.
run install -d "$ROOT$LIBDIR/modem_tuner/pages"
for file in "$DIR"/src/modem_tuner/*.py; do
    run install -m644 "$file" "$ROOT$LIBDIR/modem_tuner/$(basename "$file")"
done
for file in "$DIR"/src/modem_tuner/pages/*.py; do
    run install -m644 "$file" "$ROOT$LIBDIR/modem_tuner/pages/$(basename "$file")"
done

run install -d "$ROOT$BINDIR"
run install -m755 "$DIR/data/modem-tuner" "$ROOT$BINDIR/modem-tuner"

run install -d "$ROOT$DATADIR/applications"
DESKTOP_TMP=$(mktemp)
trap 'rm -f "$DESKTOP_TMP"' EXIT
sed "s|@BINDIR@|$BINDIR|g" "$DIR/data/$APPID.desktop.in" > "$DESKTOP_TMP"
run install -m644 "$DESKTOP_TMP" "$ROOT$DATADIR/applications/$APPID.desktop"
rm -f "$DESKTOP_TMP"
trap - EXIT

run install -d "$ROOT$DATADIR/metainfo"
run install -m644 "$DIR/data/$APPID.metainfo.xml" \
    "$ROOT$DATADIR/metainfo/$APPID.metainfo.xml"

run install -d "$ROOT$DATADIR/icons/hicolor/scalable/apps"
run install -m644 "$DIR/data/$APPID.svg" \
    "$ROOT$DATADIR/icons/hicolor/scalable/apps/$APPID.svg"

if [ -z "$ROOT" ] || [ "$ROOT" = "/" ]; then
    for cache_tool in gtk-update-icon-cache gtk4-update-icon-cache; do
        if command -v "$cache_tool" >/dev/null 2>&1; then
            run "$cache_tool" -q -t -f "$DATADIR/icons/hicolor" || true
        fi
    done
    if command -v update-desktop-database >/dev/null 2>&1; then
        run update-desktop-database "$DATADIR/applications" || true
    fi
fi

info ""
info "Done. Launch Modem Tuner from the app grid or run modem-tuner."
info "If the icon is missing from the grid, log out and back in."
