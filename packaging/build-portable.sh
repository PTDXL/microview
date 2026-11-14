#!/usr/bin/env bash
# Builds the portable version: one executable file containing Python, Qt and FFmpeg.
# Result: dist/MicroView-<version>-<system>-<arch>[.exe]
# Needs Python 3.9+ with venv and an internet connection (fetches packages from PyPI).
# Works on Linux, and on Windows from Git Bash.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p' "$root/microview.py")"
[ -n "$version" ] || { echo "APP_VERSION not found in microview.py" >&2; exit 1; }

python="${PYTHON:-python3}"
command -v "$python" >/dev/null || python=python
venv="$root/build/venv"
"$python" -m venv "$venv"
if [ -x "$venv/bin/python" ]; then py="$venv/bin/python"; else py="$venv/Scripts/python.exe"; fi

"$py" -m pip install --quiet --upgrade pip
"$py" -m pip install --quiet -r "$root/requirements.txt" pyinstaller

case "$(uname -s)" in
    Linux*) system=linux; ext="" ;;
    MINGW*|MSYS*|CYGWIN*) system=windows; ext=".exe" ;;
    *) system="$(uname -s | tr '[:upper:]' '[:lower:]')"; ext="" ;;
esac
name="MicroView-$version-$system-$(uname -m)"

"$py" -m PyInstaller --noconfirm --clean --onefile --windowed \
    --name "$name" \
    --distpath "$root/dist" --workpath "$root/build/pyinstaller" --specpath "$root/build" \
    --add-data "$root/microview.svg:." \
    --collect-all imageio_ffmpeg \
    "$root/microview.py"

echo
echo "Done: $root/dist/$name$ext"
