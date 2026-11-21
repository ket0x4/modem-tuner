#!/bin/sh
set -eu

PREFIX=${PREFIX:-$HOME/.local}
BINDIR="$PREFIX/bin"
APPDIR="$PREFIX/share/applications"
ICONDIR="$PREFIX/share/icons/hicolor/scalable/apps"
LIBDIR="$PREFIX/lib/modem-tuner"
APPID=io.github.modemtuner.ModemTuner

DIR=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)

echo "Installing Modem Tuner into $PREFIX"

install -d "$LIBDIR"
cp -r "$DIR/src/modem_tuner" "$LIBDIR/"
find "$LIBDIR" -name '__pycache__' -type d -prune -exec rm -rf {} +

install -d "$BINDIR"
cat > "$BINDIR/modem-tuner" <<LAUNCHER
#!/bin/sh
exec python3 -c 'import sys; sys.path.insert(0, "$LIBDIR"); from modem_tuner.app import main; sys.exit(main())' "\$@"
LAUNCHER
chmod 755 "$BINDIR/modem-tuner"

install -d "$APPDIR"
sed "s|@BINDIR@|$BINDIR|g" "$DIR/data/$APPID.desktop.in" > "$APPDIR/$APPID.desktop"

install -d "$ICONDIR"
install -m644 "$DIR/data/$APPID.svg" "$ICONDIR/$APPID.svg"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPDIR" >/dev/null 2>&1 || true
fi
if command -v gtk4-update-icon-cache >/dev/null 2>&1; then
    gtk4-update-icon-cache -q -t -f "$PREFIX/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo "Done. Run 'modem-tuner'."
