#!/usr/bin/env bash
# KDE Plasma integration for Retro 87 tools: tray widget, session service and
# keyboard-backlight bridge.
#
#   ./install-kde.sh                 install everything (asks for sudo once, for the backlight)
#   ./install-kde.sh --no-backlight  tray widget and service only; no root needed
#   ./install-kde.sh --uninstall     remove everything this script installed
set -euo pipefail
dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python="$dir/.venv/bin/python"
units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
dbus="${XDG_DATA_HOME:-$HOME/.local/share}/dbus-1/services"
plasmoid=io.github.josestud.retro87
rules=/etc/udev/rules.d/70-retro87-backlight.rules
modules=/etc/modules-load.d/retro87-uleds.conf

render() { sed -e "s|@DIR@|$dir|g" -e "s|@PYTHON@|$python|g" -e "s|@USER@|$USER|g" "$1"; }

if [[ "${1:-}" == "--uninstall" ]]; then
    systemctl --user disable --now retro87.service 2>/dev/null || true
    rm -f "$units/retro87.service" "$dbus/io.github.JoseStud.Retro87.service"
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

if [[ "${1:-}" != "--no-backlight" ]]; then
    echo "Backlight setup needs sudo once, to:"
    echo "  - load the kernel's uleds module now and at boot ($modules)"
    echo "  - let your session create the keyboard-backlight LED ($rules)"
    render "$dir/kde/70-retro87-backlight.rules" | sudo tee "$rules" >/dev/null
    echo uleds | sudo tee "$modules" >/dev/null
    sudo udevadm control --reload
    sudo modprobe uleds
    sudo udevadm trigger --action=add /sys/devices/virtual/misc/uleds
fi

if kpackagetool6 -t Plasma/Applet -s "$plasmoid" >/dev/null 2>&1; then
    kpackagetool6 -t Plasma/Applet -u "$dir/kde/plasmoid"
else
    kpackagetool6 -t Plasma/Applet -i "$dir/kde/plasmoid"
fi

mkdir -p "$units" "$dbus"
render "$dir/kde/retro87.service" > "$units/retro87.service"
render "$dir/kde/io.github.JoseStud.Retro87.service" > "$dbus/io.github.JoseStud.Retro87.service"
systemctl --user daemon-reload
systemctl --user enable retro87.service
systemctl --user restart retro87.service

cat <<EOF

Installed. Service log: journalctl --user -u retro87
Show the widget: right-click the system tray arrow > Configure System Tray >
Entries > Retro 87 Lighting > Always shown (or add it to a panel as a widget).
EOF
