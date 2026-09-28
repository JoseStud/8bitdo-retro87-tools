#!/usr/bin/env bash
# KDE Plasma integration for Retro 87 tools: tray widget, session service and
# keyboard-backlight bridge.
#
#   ./install-kde.sh                 install everything (asks for sudo once, for the backlight)
#   ./install-kde.sh --no-backlight  tray widget and service only; no root needed
#   ./install-kde.sh --direct        no OpenRGB: the service opens the keyboard itself
#   ./install-kde.sh --uninstall     remove everything this script installed
#
# By default the keyboard is driven through an OpenRGB server run as the user
# unit retro87-openrgb (OpenRGB with the Retro 87 support). The openrgb binary
# is taken from $OPENRGB, else from PATH.
set -euo pipefail
dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python="$dir/.venv/bin/python"
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
dbus="${XDG_DATA_HOME:-$HOME/.local/share}/dbus-1/services"
plasmoid=io.github.josestud.retro87
rules=/etc/udev/rules.d/70-retro87-backlight.rules
modules=/etc/modules-load.d/retro87-uleds.conf

backlight=1 direct=0 uninstall=0
for arg in "$@"; do
    case "$arg" in
        --no-backlight) backlight=0 ;;
        --direct) direct=1 ;;
        --uninstall) uninstall=1 ;;
        *) echo "Unknown option $arg" >&2; exit 2 ;;
    esac
done
openrgb="${OPENRGB:-$(command -v openrgb || true)}"
args=""
[[ $direct == 1 ]] && args="--direct"

render() { sed -e "s|@DIR@|$dir|g" -e "s|@PYTHON@|$python|g" -e "s|@USER@|$USER|g" \
               -e "s|@OPENRGB@|$openrgb|g" -e "s|@ARGS@|$args|g" "$1"; }

if [[ $uninstall == 1 ]]; then
    systemctl --user disable --now retro87.service retro87-openrgb.service 2>/dev/null || true
    rm -f "$units/retro87.service" "$units/retro87-openrgb.service" "$dbus/io.github.JoseStud.Retro87.service"
    systemctl --user daemon-reload
    kpackagetool6 -t Plasma/Applet -r "$plasmoid" 2>/dev/null || true
    if [[ -e "$rules" || -e "$modules" ]]; then
        echo "Removing the backlight setup (sudo): $rules $modules"
        sudo rm -f "$rules" "$modules"
        sudo udevadm control --reload
    fi
    systemctl --user try-restart plasma-powerdevil.service || true
    echo "Uninstalled. Backups in ~/.local/share/retro87-tools are kept."
    exit 0
fi

if [[ ! -x "$python" ]] || ! "$python" -c "import PySide6.QtDBus" 2>/dev/null; then
    echo "Install the Python environment first: python3 -m venv .venv && .venv/bin/pip install -r requirements-gui.txt" >&2
    exit 1
fi

if [[ $direct == 0 && ! -x "$openrgb" ]]; then
    echo "OpenRGB not found. Build OpenRGB with the Retro 87 support and run" >&2
    echo "  OPENRGB=/path/to/openrgb ./install-kde.sh" >&2
    echo "or install with --direct to let the service open the keyboard itself." >&2
    exit 1
fi

if [[ $backlight == 1 ]]; then
    echo "Backlight setup needs sudo once, to:"
    echo "  - load the kernel's uleds module now and at boot ($modules)"
    echo "  - let your session create the keyboard-backlight LED ($rules)"
    echo "  - let your session use the keyboard over its USB cable: settings and live colours ($rules)"
    render "$dir/kde/70-retro87-backlight.rules" | sudo tee "$rules" >/dev/null
    echo uleds | sudo tee "$modules" >/dev/null
    sudo udevadm control --reload
    # Already loaded after a kernel update, modprobe cannot find the old kernel's modules.
    [[ -d /sys/module/uleds ]] || sudo modprobe uleds
    sudo udevadm trigger --action=add /sys/devices/virtual/misc/uleds
    sudo udevadm trigger --action=change --subsystem-match=usb --attr-match=idVendor=2dc8 --attr-match=idProduct=2028
    sudo udevadm trigger --action=change --subsystem-match=hidraw
fi

if kpackagetool6 -t Plasma/Applet -s "$plasmoid" >/dev/null 2>&1; then
    kpackagetool6 -t Plasma/Applet -u "$dir/kde/plasmoid"
else
    kpackagetool6 -t Plasma/Applet -i "$dir/kde/plasmoid"
fi

mkdir -p "$units" "$dbus"
render "$dir/kde/retro87.service" > "$units/retro87.service"
render "$dir/kde/io.github.JoseStud.Retro87.service" > "$dbus/io.github.JoseStud.Retro87.service"
if [[ $direct == 0 ]]; then
    render "$dir/kde/retro87-openrgb.service" > "$units/retro87-openrgb.service"
else
    systemctl --user disable --now retro87-openrgb.service 2>/dev/null || true
    rm -f "$units/retro87-openrgb.service"
fi
systemctl --user daemon-reload
if [[ $direct == 0 ]]; then
    systemctl --user enable retro87-openrgb.service
    systemctl --user restart retro87-openrgb.service
fi
systemctl --user enable retro87.service
systemctl --user restart retro87.service

cat <<EOF

Installed. Service log: journalctl --user -u retro87${openrgb:+ (OpenRGB: journalctl --user -u retro87-openrgb)}
Show the widget: right-click the system tray arrow > Configure System Tray >
Entries > Retro 87 Lighting > Always shown (or add it to a panel as a widget).
EOF
