// Tray widget for the Retro 87 session service (retro87_service.py, io.github.JoseStud.Retro87).
import QtQuick
import QtQuick.Layouts
import QtQuick.Dialogs
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import org.kde.plasma.workspace.dbus as DBus

PlasmoidItem {
    id: root

    property var st: ({})
    property string message: ""
    property bool busy: false
    readonly property bool ready: st.connected === true && st.initialized === true
    readonly property var presetNames: ({
        "off": i18n("Off"), "resonance": i18n("Resonance"), "starlight": i18n("Starlight"),
        "solid": i18n("Solid"), "cycle": i18n("Cycle"), "color-ripple": i18n("Colour ripple"),
        "breathing": i18n("Breathing"), "ripple": i18n("Ripple")
    })

    function call(member, args) {
        busy = true
        DBus.SessionBus.asyncCall({
            service: "io.github.JoseStud.Retro87", path: "/io/github/JoseStud/Retro87",
            iface: "io.github.JoseStud.Retro87", member: member, arguments: args
        }, function (reply) {
            busy = false
            if (member === "OpenApp")
                return
            const state = JSON.parse(reply.value.value)
            root.st = state
            root.message = state.message || ""
        }, function (error) {
            busy = false
            root.st = {}
            root.message = i18n("The Retro 87 service is not running. Start it with: systemctl --user start retro87")
        })
    }
    function set(field, value) { call("Set", [field, String(value)]) }

    Plasmoid.icon: "input-keyboard"
    Plasmoid.status: st.connected ? PlasmaCore.Types.ActiveStatus : PlasmaCore.Types.PassiveStatus
    toolTipMainText: i18n("Retro 87")
    toolTipSubText: !st.connected ? (st.error || i18n("Keyboard not connected"))
        : st.perKey ? i18n("Per-key lighting, %1%", st.brightness)
        : st.brightness !== null && st.brightness !== undefined ? i18n("%1, %2%", presetNames[st.preset] || st.preset, st.brightness)
        : (presetNames[st.preset] || st.preset)

    onExpandedChanged: if (root.expanded) call("Refresh", [])
    Component.onCompleted: call("Status", [])

    Timer {  // Pick up changes made through the Brightness applet or keyboard keys.
        interval: 3000; repeat: true; running: root.expanded && !root.busy
        onTriggered: root.call("Status", [])
    }

    fullRepresentation: PlasmaExtras.Representation {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 18
        Layout.minimumHeight: Kirigami.Units.gridUnit * 16
        collapseMarginsHint: true

        header: PlasmaExtras.PlasmoidHeading {
            RowLayout {
                anchors.fill: parent
                PlasmaExtras.Heading {
                    Layout.fillWidth: true
                    level: 1
                    text: st.connected ? (st.profileName || i18n("Retro 87")) : i18n("Retro 87")
                }
                PlasmaComponents3.BusyIndicator {
                    Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                    Layout.preferredWidth: Layout.preferredHeight
                    running: root.busy
                    visible: running
                }
                PlasmaComponents3.ToolButton {
                    icon.name: "view-refresh"
                    onClicked: root.call("Refresh", [])
                    PlasmaComponents3.ToolTip { text: i18n("Re-read the keyboard") }
                }
                PlasmaComponents3.ToolButton {
                    icon.name: "configure"
                    onClicked: root.call("OpenApp", [])
                    PlasmaComponents3.ToolTip { text: i18n("Open the Retro 87 app (keys, per-key colours, profiles)") }
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: text !== ""
                type: Kirigami.MessageType.Error
                text: root.message || (st.connected === false ? (st.error || "") : "")
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: st.connected === true && st.initialized === false
                type: Kirigami.MessageType.Warning
                text: i18n("The keyboard has no profile yet. Create one in the Retro 87 app.")
            }
            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: root.ready && st.profileActive === false
                type: Kirigami.MessageType.Information
                text: i18n("Profile inactive: the keyboard is using its onboard lighting. Press the keyboard's Profile button once to use these settings.")
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                enabled: root.ready && !root.busy
                columnSpacing: Kirigami.Units.largeSpacing

                PlasmaComponents3.Label { text: i18n("Match wallpaper:") }
                PlasmaComponents3.ComboBox {
                    Layout.fillWidth: true
                    model: [
                        { value: "off", text: i18n("Off") },
                        { value: "color", text: i18n("Colour") },
                        { value: "keys", text: i18n("Picture on keys") }
                    ].concat(st.wallpaperLiveAvailable ? [{ value: "live", text: st.wallpaperLiveUsb ? i18n("Live animation (USB)") : i18n("Live animation (experimental, wears flash)") }] : [])
                     .concat(st.wallpaperSync === "display" ? [{ value: "display", text: i18n("Full display (experimental)") }] : [])
                    textRole: "text"
                    valueRole: "value"
                    currentIndex: ["off", "color", "keys", "live", "display"].indexOf(st.wallpaperSync || "off")
                    onActivated: root.set("wallpaper", currentValue)
                    PlasmaComponents3.ToolTip {
                        text: i18n("Follow the waywallen wallpaper: its main colour in the current effect, or the picture spread over the keys. Updates when the wallpaper changes.")
                    }
                }
                Item { visible: !!st.wallpaperLiveError; implicitWidth: 1 }
                PlasmaComponents3.Label {
                    Layout.fillWidth: true
                    visible: !!st.wallpaperLiveError
                    text: st.wallpaperLiveError || ""
                    wrapMode: Text.WordWrap
                }
                Item { visible: !!st.wallpaperName && st.wallpaperSync !== "off"; implicitWidth: 1 }
                PlasmaComponents3.Label {
                    Layout.fillWidth: true
                    visible: !!st.wallpaperName && st.wallpaperSync !== "off"
                    text: st.wallpaperName || ""
                    elide: Text.ElideRight
                    opacity: 0.7
                }

                PlasmaComponents3.Label { text: i18n("Per-key lighting:") }
                PlasmaComponents3.Switch {
                    checked: st.perKey === true
                    enabled: st.perKeyStored === true || st.perKey === true
                    onToggled: root.set("perkey", checked ? "on" : "off")
                    PlasmaComponents3.ToolTip {
                        text: st.perKeyStored ? i18n("Show the per-key colours stored on the keyboard")
                                              : i18n("Create a per-key layout in the Retro 87 app first")
                    }
                }

                PlasmaComponents3.Label { text: i18n("Effect:"); visible: !st.perKey }
                PlasmaComponents3.ComboBox {
                    id: presetBox
                    Layout.fillWidth: true
                    visible: !st.perKey
                    model: (st.presets || []).map(p => ({ value: p, text: root.presetNames[p] || p }))
                    textRole: "text"
                    valueRole: "value"
                    currentIndex: (st.presets || []).indexOf(st.preset)
                    onActivated: root.set("preset", currentValue)
                }

                PlasmaComponents3.Label {
                    text: i18n("Brightness:")
                    visible: st.brightness !== null && st.brightness !== undefined
                }
                RowLayout {
                    visible: st.brightness !== null && st.brightness !== undefined
                    PlasmaComponents3.Slider {
                        id: brightness
                        Layout.fillWidth: true
                        from: 0; to: 100; stepSize: 5
                        Binding on value { value: st.brightness || 0; when: !brightness.pressed && !brightnessDelay.running }
                        onMoved: brightnessDelay.restart()
                        Timer { id: brightnessDelay; interval: 400; onTriggered: root.set("brightness", Math.round(brightness.value)) }
                    }
                    PlasmaComponents3.Label {
                        text: i18n("%1%", Math.round(brightness.value))
                        Layout.minimumWidth: Kirigami.Units.gridUnit * 2
                    }
                }

                PlasmaComponents3.Label { text: i18n("Speed:"); visible: st.hasSpeed === true && st.speed !== null }
                RowLayout {
                    visible: st.hasSpeed === true && st.speed !== null
                    PlasmaComponents3.Slider {
                        id: speed
                        Layout.fillWidth: true
                        from: 1; to: 10; stepSize: 1
                        Binding on value { value: st.speed || 5; when: !speed.pressed && !speedDelay.running }
                        onMoved: speedDelay.restart()
                        Timer { id: speedDelay; interval: 400; onTriggered: root.set("speed", Math.round(speed.value)) }
                    }
                    PlasmaComponents3.Label {
                        text: Math.round(speed.value)
                        Layout.minimumWidth: Kirigami.Units.gridUnit * 2
                    }
                }

                PlasmaComponents3.Label { text: st.hasEcho ? i18n("Background:") : i18n("Colour:"); visible: st.hasColor === true }
                ColorRow { visible: st.hasColor === true; field: "color"; current: st.color || "" }

                PlasmaComponents3.Label { text: i18n("Highlight:"); visible: st.hasEcho === true }
                ColorRow { visible: st.hasEcho === true; field: "echo"; current: st.echo || "" }
            }

            PlasmaComponents3.Label {
                Layout.fillWidth: true
                visible: root.ready && st.perKey === true
                wrapMode: Text.WordWrap
                opacity: 0.7
                text: i18n("Colours and effect are edited per key in the Retro 87 app.")
            }
            Item { Layout.fillHeight: true }
        }
    }

    component ColorRow: RowLayout {
        id: row
        property string field
        property string current
        spacing: Kirigami.Units.smallSpacing
        Repeater {
            model: ["#ff0000", "#ff8000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff", "#ffffff"]
            delegate: Rectangle {
                required property string modelData
                implicitWidth: Kirigami.Units.iconSizes.small + 4
                implicitHeight: implicitWidth
                radius: 3
                color: modelData
                border.width: row.current.toLowerCase() === modelData ? 2 : 1
                border.color: row.current.toLowerCase() === modelData ? Kirigami.Theme.highlightColor : Kirigami.Theme.disabledTextColor
                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: root.set(row.field, parent.modelData)
                }
            }
        }
        PlasmaComponents3.ToolButton {
            icon.name: "color-picker"
            onClicked: dialog.open()
            PlasmaComponents3.ToolTip { text: i18n("Other colour…") }
        }
        ColorDialog {
            id: dialog
            selectedColor: row.current || "#ffffff"
            onAccepted: root.set(row.field, selectedColor.toString().slice(0, 7))
        }
    }
}
