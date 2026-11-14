# Build with packaging/build-rpm.sh (it passes app_version from microview.py)
%{!?app_version: %global app_version 0}

Name:           microview
Version:        %{app_version}
Release:        1%{?dist}
Summary:        Viewer for USB microscopes (UVC)
License:        GPL-3.0-or-later
URL:            https://github.com/ptdxl/microview
Source0:        microview.py
Source1:        microview.svg
Source2:        microview.desktop
Source3:        LICENSE
BuildArch:      noarch

Requires:       python3-pyside6
Requires:       qt6-qtmultimedia
Requires:       qt6-qtsvg
Requires:       /usr/bin/ffmpeg
Requires:       hicolor-icon-theme

%description
MicroView shows the live image of a USB microscope (any UVC camera) and lets
you take photos, record video, adjust brightness and contrast, rotate and
mirror the image, zoom digitally and measure distances after calibration.

%prep

%build

%install
install -Dpm 0755 %{SOURCE0} %{buildroot}%{_bindir}/microview
install -Dpm 0644 %{SOURCE1} %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/microview.svg
install -Dpm 0644 %{SOURCE2} %{buildroot}%{_datadir}/applications/microview.desktop

install -Dpm 0644 %{SOURCE3} %{buildroot}%{_licensedir}/%{name}/LICENSE

%files
%license %{_licensedir}/%{name}/LICENSE
%{_bindir}/microview
%{_datadir}/icons/hicolor/scalable/apps/microview.svg
%{_datadir}/applications/microview.desktop

%changelog
* Sat Nov 14 2026 Ptdxl - 1.3-1
- Zoom in/out buttons; Zoom 1x is disabled when not zoomed in

* Sat Nov 14 2026 Ptdxl - 1.2-1
- Record video through FFmpeg as 8-bit 4:2:0 H.264, including rotation and measurements
- Read and set camera controls directly through V4L2 (v4l-utils no longer needed)
- English user interface with Dutch translation
- License: GPL-3.0-or-later

* Sat Nov 14 2026 Ptdxl - 1.1-1
- First package
