#!/usr/bin/env bash
# Installs MicroView for the current user, without root.
#   ./install.sh              install or update
#   ./install.sh --uninstall  remove
# For a system-wide install on Fedora see packaging/build-rpm.sh.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
data="${XDG_DATA_HOME:-$HOME/.local/share}"
bin="$HOME/.local/bin/microview"
icon="$data/icons/hicolor/scalable/apps/microview.svg"
desktop="$data/applications/microview.desktop"

refresh() {
    command -v update-desktop-database >/dev/null && update-desktop-database "$data/applications" || true
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t "$data/icons/hicolor" 2>/dev/null || true
}

if [ "${1:-}" = "--uninstall" ]; then
    rm -f "$bin" "$icon" "$desktop"
    refresh
    echo "MicroView has been removed."
    exit 0
fi

python3 -c "import PySide6.QtMultimedia" 2>/dev/null || {
    echo "PySide6 is missing. Install it first, for example:" >&2
    echo "  Fedora:  sudo dnf install python3-pyside6 ffmpeg-free" >&2
    echo "  Other:   pip install -r requirements.txt  (in a virtual environment)" >&2
    exit 1
}
command -v ffmpeg >/dev/null || python3 -c "import imageio_ffmpeg" 2>/dev/null ||
    echo "Note: ffmpeg is missing; video recording works once you install the 'ffmpeg' package." >&2

install -Dpm 0755 "$here/microview.py" "$bin"
install -Dpm 0644 "$here/microview.svg" "$icon"
install -Dpm 0644 "$here/microview.desktop" "$desktop"
# full path, so the menu entry also works when ~/.local/bin is not in PATH
sed -i "s|^Exec=microview$|Exec=$bin|" "$desktop"
refresh

echo "Installed:"
echo "  $bin"
echo "  $icon"
echo "  $desktop"
case ":$PATH:" in
    *":$HOME/.local/bin:"*) echo "Start with: microview (or from the application menu)" ;;
    *) echo "Start from the application menu, or with: $bin" ;;
esac
