# PyInstaller recipe for the portable version; used by packaging/build-portable.sh.
# Result: dist/MicroView-<version>-<system>-<arch>[.exe]
import os
import platform
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH).parent
version = re.search(r'^APP_VERSION = "(.*)"$', (root / "microview.py").read_text(encoding="utf-8"), re.M).group(1)
system = {"linux": "linux", "win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform)
arch = {"amd64": "x86_64"}.get(platform.machine().lower(), platform.machine().lower())
name = f"MicroView-{version}-{system}-{arch}"

# imageio-ffmpeg carries the FFmpeg program used for video recording
datas, binaries, hiddenimports = collect_all("imageio_ffmpeg")
datas.append((str(root / "microview.svg"), "."))

a = Analysis([str(root / "microview.py")], binaries=binaries, datas=datas, hiddenimports=hiddenimports)

# Font handling must come from the system the program runs on: a bundled fontconfig that is
# older than the system's configuration files cannot read them. The libraries below are present
# on every Linux desktop; the ones besides fontconfig and freetype are left out because the
# system's freetype and fontconfig have to load matching versions of them.
SYSTEM_LIBRARIES = ("libfontconfig.so", "libfreetype.so", "libharfbuzz.so", "libexpat.so", "libz.so")
if system == "linux":
    a.binaries = [entry for entry in a.binaries
                  if not os.path.basename(entry[0]).startswith(SYSTEM_LIBRARIES)]

pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name=name,
    console=False,
    upx=False,
    icon=str(root / "packaging" / "microview.ico") if system == "windows" else None,
)
