#!/usr/bin/env bash
# Builds dist/microview-<version>-*.noarch.rpm for Fedora. Needs rpm-build.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
version="$(sed -n 's/^APP_VERSION = "\(.*\)"$/\1/p' "$root/microview.py")"
[ -n "$version" ] || { echo "APP_VERSION not found in microview.py" >&2; exit 1; }

if command -v desktop-file-validate >/dev/null; then
    desktop-file-validate "$root/microview.desktop"
fi

top="$root/build/rpm"
rm -rf "$top"
rpmbuild -bb "$root/packaging/rpm/microview.spec" \
    --define "_topdir $top" \
    --define "_sourcedir $root" \
    --define "app_version $version"

mkdir -p "$root/dist"
cp "$top"/RPMS/noarch/microview-"$version"-*.noarch.rpm "$root/dist/"
echo
echo "Done. Install with:"
for rpm in "$root"/dist/microview-"$version"-*.noarch.rpm; do
    echo "  sudo dnf install $rpm"
done
