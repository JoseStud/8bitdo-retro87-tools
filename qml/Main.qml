import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs

ApplicationWindow {
    id: window
    required property var bridge
    readonly property var deviceState: bridge.state
    property int page: 0
    property string selectedKey: "capslock"
    property string selectedLabel: "Caps Lock"
    property string fileAction: "open"
    property bool exitConfirmed: false
    width: 1200; height: 800
    minimumWidth: 1000; minimumHeight: 700
    visible: true
    title: "Retro 87 Tools · Unofficial — Mecha BREAK: Panther"
    color: "#171717"
    font.family: "Noto Sans"
    font.pixelSize: 13
    palette.window: "#171717"
    palette.windowText: "#e8e8e8"
    palette.base: "#252525"
    palette.alternateBase: "#303030"
    palette.text: "#e8e8e8"
    palette.button: "#303030"
    palette.buttonText: "#e8e8e8"
    palette.highlight: "#72d7ed"
    palette.highlightedText: "#171717"
    palette.mid: "#454545"
    onClosing: function(close) {
        if (window.deviceState.busy) { close.accepted = false; return }
        if (window.deviceState.dirty && !exitConfirmed) { close.accepted = false; quitDialog.open() }
    }

    component Note: Label {
        color: "#a5a5a5"
        wrapMode: Text.WordWrap
        Layout.fillWidth: true
        textFormat: Text.PlainText
    }
    component Action: Button {
        implicitHeight: 36
        focusPolicy: Qt.StrongFocus
        background: Rectangle {
            radius: 3
            color: parent.down ? "#454545" : parent.hovered ? "#383838" : "#303030"
            border.color: parent.activeFocus ? "#72d7ed" : "#484848"
            opacity: parent.enabled ? 1 : 0.4
        }
        contentItem: Text {
            text: parent.text; font: parent.font
            color: parent.enabled ? "#e8e8e8" : "#777777"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 24; spacing: 16
        RowLayout {
            Layout.fillWidth: true; Layout.preferredHeight: 60
            Action { text: "‹  Profiles"; onClicked: window.page = 4 }
            Item { Layout.fillWidth: true }
            Repeater {
                model: ["⌨  Keys", "⑂  Macros", "◖  Volume", "☼  Lighting"]
                delegate: Button {
                    required property string modelData
                    required property int index
                    text: modelData
                    checkable: true; checked: window.page === index
                    implicitWidth: 102; implicitHeight: 52
                    onClicked: window.page = index
                    background: Rectangle {
                        color: "transparent"
                        Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 2; color: "#72d7ed"; visible: parent.parent.checked }
                    }
                    contentItem: Text { text: parent.text; font: parent.font; color: parent.checked || parent.activeFocus ? "#72d7ed" : "#a5a5a5"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                }
            }
            Item { Layout.fillWidth: true }
            Action { text: window.deviceState.busy ? "Working…" : "Read / reconnect"; enabled: !window.deviceState.busy && !window.deviceState.dirty; onClicked: bridge.connectDevice() }
        }
        RowLayout {
            Layout.fillWidth: true
            Label { text: "Current profile: " + window.deviceState.profileName; font.pixelSize: 16; textFormat: Text.PlainText }
            Label {
                visible: window.deviceState.loaded && window.deviceState.initialized
                text: window.deviceState.profileActive ? "· active" : "· inactive: press the keyboard's Profile button to use these lighting settings"
                color: window.deviceState.profileActive ? "#a5d6a7" : "#ffcc80"; textFormat: Text.PlainText
            }
            Item { Layout.fillWidth: true }
            Label { text: window.deviceState.live ? (window.deviceState.connection || "Keyboard") + " · last read" : "Offline · no live device state"; color: "#a5a5a5" }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: "#303030" }

        StackLayout {
            currentIndex: window.page
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0
            clip: true
            // Keys
            ScrollView {
                id: keysScroll
                contentWidth: availableWidth; clip: true
                ScrollBar.vertical.policy: ScrollBar.AlwaysOn
            RowLayout {
                width: keysScroll.availableWidth; spacing: 30
                    ColumnLayout {
                        Layout.preferredWidth: 235; Layout.alignment: Qt.AlignTop; spacing: 12
                        Label { text: window.selectedLabel; font.pixelSize: 19 }
                        Note { text: "Current / staged assignment" }
                        Note { text: window.deviceState.mappings[window.selectedKey] || "Unknown"; color: "#e8e8e8" }
                        Action { text: "Create Profile…"; visible: !window.deviceState.initialized; enabled: window.deviceState.loaded && !window.deviceState.busy; onClicked: profileDialog.open() }
                        Note { visible: !window.deviceState.initialized; text: "Create a profile explicitly before remapping. Nothing is written until Apply." }
                        Label { text: "Assign key" }
                        TextField { id: targetSearch; Layout.fillWidth: true; placeholderText: "Filter target keys…"; enabled: window.deviceState.initialized }
                        ComboBox {
                            id: target
                            objectName: "targetPicker"
                            Layout.fillWidth: true
                            textRole: "label"; valueRole: "name"
                            model: bridge.targets.filter(function(t) { return t.label.toLowerCase().indexOf(targetSearch.text.toLowerCase()) >= 0 || t.name.indexOf(targetSearch.text.toLowerCase()) >= 0 })
                            enabled: window.deviceState.initialized && !window.deviceState.busy
                        }
                        Action { text: "Stage assignment"; objectName: "stageMap"; Layout.fillWidth: true; enabled: window.deviceState.initialized && target.currentIndex >= 0 && !window.deviceState.busy; onClicked: bridge.stageMap(window.selectedKey, target.currentValue) }
                        Action { text: "Stage default"; Layout.fillWidth: true; enabled: window.deviceState.initialized && !window.deviceState.busy; onClicked: bridge.stageDefault(window.selectedKey) }
                        Action { text: "Disable key"; Layout.fillWidth: true; enabled: window.deviceState.initialized && !window.deviceState.busy; onClicked: bridge.stageMap(window.selectedKey, "none") }
                        Note { text: "Fn and Game Bar are not remappable here. Unsupported assignments are preserved until explicitly replaced." }
                        Note { text: "Mouse, multimedia and shortcut combinations: protocol work still in progress."; color: "#dba836" }
                    }
                ColumnLayout {
                    Layout.fillWidth: true; Layout.fillHeight: true; spacing: 20
                    Note { text: "MECHA BREAK: PANTHER   /   reconstructed keyboard view"; font.pixelSize: 11; horizontalAlignment: Text.AlignRight }
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: width / 18.5 * 7 + 32
                        color: "#252525"; radius: 7; border.color: "#404040"
                        Item {
                            id: keyboard
                            anchors.fill: parent; anchors.margins: 16
                            readonly property real unit: width / 18.5
                            Repeater {
                                model: bridge.keyLayout
                                delegate: Button {
                                    required property var modelData
                                    x: modelData.x * keyboard.unit
                                    y: modelData.y * keyboard.unit
                                    width: modelData.units * keyboard.unit - 3
                                    height: keyboard.unit - 3
                                    text: modelData.label
                                    enabled: modelData.editable
                                    objectName: "key_" + modelData.key
                                    Accessible.name: modelData.label + ", " + (window.deviceState.mappings[modelData.key] || "not remappable")
                                    onClicked: { window.selectedKey = modelData.key; window.selectedLabel = modelData.label }
                                    ToolTip.visible: hovered
                                    ToolTip.text: modelData.label + ": " + (window.deviceState.mappings[modelData.key] || "not remappable")
                                    background: Rectangle {
                                        radius: 3; color: parent.down ? "#454545" : "#333333"
                                        border.width: parent.activeFocus || window.selectedKey === modelData.key ? 2 : 1
                                        border.color: parent.activeFocus || window.selectedKey === modelData.key ? "#72d7ed" : "#4b4b4b"
                                    }
                                    contentItem: Text {
                                        text: parent.text; color: parent.enabled ? "#dedede" : "#777777"
                                        font.pixelSize: Math.max(8, keyboard.unit * 0.23)
                                        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter; spacing: 24
                        Repeater {
                            model: ["ka", "kb"]
                            delegate: Action {
                                required property string modelData
                                text: modelData === "ka" ? "Super A" : "Super B"
                                implicitWidth: 112; implicitHeight: 66
                                onClicked: { window.selectedKey = modelData; window.selectedLabel = text }
                            }
                        }
                    }
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter; spacing: 5
                        Repeater {
                            model: 8
                            delegate: Action {
                                required property int index
                                text: "K" + (index + 1); implicitWidth: 45
                                Accessible.name: "Extension key " + (index + 1)
                                onClicked: { window.selectedKey = "k" + (index + 1); window.selectedLabel = "Extension " + text }
                            }
                        }
                    }
                    Note { text: "Select a key to inspect or stage a new assignment. Cyan outline = selection, not a saved remap."; horizontalAlignment: Text.AlignHCenter }
                    Item { Layout.fillHeight: true }
                }
            }
            }
            // Macros: truthful capability boundary, extended by macro editor component.
            ColumnLayout {
                spacing: 18
                Label { text: "Macros"; font.pixelSize: 22 }
                Note { text: "Macro storage is partly decoded, but safe backup and restoration are not established. Hardware macro editing remains unavailable."; color: "#dba836" }
                Note { text: "The official app supports recording, per-event delays and repetition. These controls will not send guessed packets. Full keyboard parity is still in progress." }
                Item { Layout.fillHeight: true }
            }
            // Volume
            ColumnLayout {
                spacing: 16
                Label { text: "Keyboard sound"; font.pixelSize: 22 }
                Note { text: "Saved / staged level: " + (window.deviceState.volume === null || window.deviceState.volume === undefined ? "Device default / unknown" : window.deviceState.volume) }
                Note { text: "This is the keyboard’s device sound setting, not Linux system volume." }
                RowLayout {
                    SpinBox { id: volumeLevel; objectName: "volumeLevel"; from: 1; to: 5; value: 2 }
                    Action { text: "Stage sound level"; objectName: "stageVolume"; enabled: window.deviceState.loaded && !window.deviceState.busy; onClicked: bridge.stageVolume(volumeLevel.value) }
                }
                Note { text: "Proposed level (1–5), decoded from the official app." }
                Item { Layout.fillHeight: true }
            }
            // Lighting
            ScrollView {
                id: lightingScroll; objectName: "lightingScroll"
                contentWidth: availableWidth; clip: true
                ScrollBar.vertical.policy: ScrollBar.AlwaysOn
            ColumnLayout {
                width: lightingScroll.availableWidth; spacing: 28
            RowLayout {
                Layout.fillWidth: true; spacing: 40
                ColumnLayout {
                    Layout.preferredWidth: 285; spacing: 12
                    Label { text: "Preset lighting"; font.pixelSize: 22 }
                    Note { text: "Saved effect: " + window.deviceState.savedLighting.mode }
                    Note { text: "Saved parameters: " + (window.deviceState.savedLighting.brightness == null ? "device default / unknown" : window.deviceState.savedLighting.brightness + "%") }
                    ComboBox { id: effect; objectName: "effectPicker"; Layout.fillWidth: true; model: ["solid", "breathing", "off", "cycle", "color-ripple", "ripple", "resonance", "starlight"] }
                    Label { text: "Color / background (RGB hex)" }
                    TextField { id: rgb; objectName: "rgbColor"; text: "#8000ff"; Layout.fillWidth: true; placeholderText: "#RRGGBB"; maximumLength: 7; enabled: ["solid", "breathing", "ripple", "resonance", "starlight"].indexOf(effect.currentText) >= 0 }
                    Label { text: "Brightness: " + Math.round(brightness.value) + "%" }
                    Slider { id: brightness; Layout.fillWidth: true; from: 0; to: 100; value: 50; stepSize: 1; enabled: effect.currentText !== "off" }
                    Label { text: "Effect speed: " + Math.round(speed.value) }
                    Slider { id: speed; Layout.fillWidth: true; from: 1; to: 10; value: 5; stepSize: 1; enabled: effect.currentText !== "solid" && effect.currentText !== "off" }
                    Action { text: "Stage lighting"; objectName: "stageRgb"; Layout.fillWidth: true; enabled: window.deviceState.loaded && !window.deviceState.busy; onClicked: bridge.stageEffect(effect.currentText, rgb.text, Math.round(brightness.value), Math.round(speed.value), echoRgb.text, direction.currentIndex, starCount.value) }
                    Note { text: "These are proposed values, not a live reading. Selecting an effect or moving a slider does not write to the keyboard." }
                    Item { Layout.fillHeight: true }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 12
                    Label { text: "Local color swatch"; font.pixelSize: 18 }
                    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 70; radius: 6; color: !rgb.enabled ? "#252525" : /^#[0-9a-fA-F]{6}$/.test(rgb.text) ? rgb.text : "#252525"; opacity: !rgb.enabled ? 1 : 0.2 + brightness.value / 125; border.color: "#777777" }
                    Note { text: "Color reference only, not an effect simulation. No live RGB writes." }
                    RowLayout {
                        visible: effect.currentText === "resonance" || effect.currentText === "starlight"
                        Label { text: "Echo color" }
                        TextField { id: echoRgb; objectName: "echoColor"; text: "#ffffff"; maximumLength: 7; Layout.fillWidth: true }
                    }
                    RowLayout {
                        visible: effect.currentText === "color-ripple"
                        Label { text: "Direction" }
                        ComboBox { id: direction; objectName: "rippleDirection"; Layout.fillWidth: true; model: ["Horizontal", "Horizontal reverse", "Vertical", "Vertical reverse", "Diffuse", "Shrink"] }
                    }
                    RowLayout {
                        visible: effect.currentText === "starlight"
                        Label { text: "Star count (5–100)" }
                        SpinBox { id: starCount; objectName: "starCount"; from: 5; to: 100; value: 25; editable: true }
                    }
                    Note { text: "Current / staged mode: " + window.deviceState.lighting.mode }
                    Note { text: "Select any preset using its existing stored parameters (including device defaults)." }
                    ComboBox { id: storedPreset; Layout.fillWidth: true; model: ["off", "resonance", "starlight", "solid", "cycle", "color-ripple", "breathing", "ripple"] }
                    Action { text: "Stage stored preset"; enabled: window.deviceState.loaded && !window.deviceState.busy; onClicked: bridge.stagePreset(storedPreset.currentText) }
                    Note { text: "Stored effect settings apply only while the profile is active. Breathing colour, brightness and speed are hardware-verified; other presets use the same encoding. Selecting a preset leaves per-key mode."; color: "#dba836" }
                    Note { text: "Windows Dynamic Lighting is not available on Linux. Staging a supported preset explicitly selects the vendor RGB engine." }
                    Item { Layout.fillHeight: true }
                }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: "#303030" }
            ColumnLayout {
                id: perKey
                objectName: "perKeyLighting"
                Layout.fillWidth: true; spacing: 12
                property var colors: ({})
                property var selected: []
                property string fill: "#000000"
                function load() {
                    var leds = window.deviceState.leds || {}
                    var loaded = {}
                    var src = leds.colors || {}
                    for (var key in src) if (src[key]) loaded[key] = src[key]
                    colors = loaded
                    selected = []
                    if (leds.valid) {
                        ledEffect.currentIndex = Math.max(0, ledEffect.model.indexOf(leds.effect))
                        if (leds.brightness !== null) ledBrightness.value = leds.brightness
                        if (leds.speed !== null) ledSpeed.value = leds.speed
                        if (leds.count !== null) ledCount.value = leds.count
                    }
                }
                function valid(color) { return /^#[0-9a-fA-F]{6}$/.test(color) }
                function colorOf(key) { return colors[key] || fill }
                function toggle(key, add) {
                    var next = add ? selected.slice() : []
                    var at = next.indexOf(key)
                    if (at >= 0) next.splice(at, 1); else next.push(key)
                    selected = next
                }
                function paint(keys, color) {
                    if (!valid(color)) return
                    var next = Object.assign({}, colors)
                    for (var i = 0; i < keys.length; i++) next[keys[i]] = color.toLowerCase()
                    colors = next
                }
                Component.onCompleted: load()
                Connections { target: window.bridge; function onChanged() { if (!window.deviceState.dirty && !window.deviceState.busy) perKey.load() } }

                Label { text: "Per-key lighting"; font.pixelSize: 22 }
                Note { text: "Click a key to select it; Ctrl+click adds or removes keys. Colours are staged locally until you click “Stage per-key lighting”, then Review and Apply. Requires an active profile." }
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: width / 18.5 * 7 + 32
                    color: "#1e1e1e"; radius: 7; border.color: "#404040"
                    Item {
                        id: ledBoard
                        anchors.fill: parent; anchors.margins: 16
                        readonly property real unit: width / 18.5
                        Repeater {
                            model: bridge.keyLayout
                            delegate: Button {
                                required property var modelData
                                readonly property bool hasLed: bridge.ledKeys.indexOf(modelData.key) >= 0
                                readonly property bool picked: perKey.selected.indexOf(modelData.key) >= 0
                                x: modelData.x * ledBoard.unit
                                y: modelData.y * ledBoard.unit
                                width: modelData.units * ledBoard.unit - 3
                                height: ledBoard.unit - 3
                                text: modelData.label
                                enabled: hasLed
                                objectName: "led_" + modelData.key
                                Accessible.name: modelData.label + ", colour " + perKey.colorOf(modelData.key)
                                onClicked: perKey.toggle(modelData.key, (Qt.application.keyboardModifiers || 0) & Qt.ControlModifier)
                                ToolTip.visible: hovered
                                ToolTip.text: hasLed ? modelData.label + ": " + perKey.colorOf(modelData.key) : modelData.label + ": no LED"
                                background: Rectangle {
                                    radius: 3
                                    color: parent.hasLed ? perKey.colorOf(modelData.key) : "#2a2a2a"
                                    border.width: parent.picked ? 3 : 1
                                    border.color: parent.picked ? "#ffffff" : "#4b4b4b"
                                }
                                contentItem: Text {
                                    text: parent.text
                                    readonly property color bg: parent.hasLed ? perKey.colorOf(modelData.key) : "#2a2a2a"
                                    color: !parent.enabled ? "#666666" : (bg.r * 0.299 + bg.g * 0.587 + bg.b * 0.114) > 0.55 ? "#111111" : "#f0f0f0"
                                    font.pixelSize: Math.max(8, ledBoard.unit * 0.23)
                                    horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 10
                    Label { text: perKey.selected.length + " selected" }
                    TextField { id: keyColor; objectName: "ledKeyColor"; text: "#ff0000"; maximumLength: 7; implicitWidth: 100; placeholderText: "#RRGGBB" }
                    Rectangle { width: 28; height: 28; radius: 4; border.color: "#777777"; color: perKey.valid(keyColor.text) ? keyColor.text : "transparent" }
                    Action { text: "Colour selected"; objectName: "ledPaint"; enabled: perKey.selected.length > 0 && perKey.valid(keyColor.text); onClicked: perKey.paint(perKey.selected, keyColor.text) }
                    Action { text: "Select all"; onClicked: perKey.selected = bridge.ledKeys.slice() }
                    Action { text: "Clear selection"; enabled: perKey.selected.length > 0; onClicked: perKey.selected = [] }
                    Action { text: "Colour all"; enabled: perKey.valid(keyColor.text); onClicked: perKey.paint(bridge.ledKeys, keyColor.text) }
                    Item { Layout.fillWidth: true }
                    Action { text: "Reload from keyboard data"; enabled: !window.deviceState.busy; onClicked: perKey.load() }
                }
                RowLayout {
                    Layout.fillWidth: true; spacing: 14
                    Label { text: "Effect" }
                    ComboBox { id: ledEffect; objectName: "ledEffect"; model: ["static", "breathing", "starlight", "freeze", "off"] }
                    Label { text: "Brightness " + Math.round(ledBrightness.value) + "%" }
                    Slider { id: ledBrightness; from: 0; to: 100; value: 100; stepSize: 1; Layout.preferredWidth: 150; enabled: ledEffect.currentText !== "off" }
                    Label { text: "Speed " + Math.round(ledSpeed.value) }
                    Slider { id: ledSpeed; from: 1; to: 10; value: 5; stepSize: 1; Layout.preferredWidth: 120; enabled: ledEffect.currentText === "breathing" || ledEffect.currentText === "starlight" }
                    
                    Label { text: "Stars"; visible: ledEffect.currentText === "starlight" }
                    SpinBox { id: ledCount; from: 5; to: 100; value: 25; editable: true; visible: ledEffect.currentText === "starlight" }
                    Item { Layout.fillWidth: true }
                    Action {
                        text: "Stage per-key lighting"; objectName: "stageLeds"
                        enabled: window.deviceState.loaded && !window.deviceState.busy
                        onClicked: bridge.stageLeds(perKey.colors, "#000000", ledEffect.currentText, Math.round(ledBrightness.value), Math.round(ledSpeed.value), ledCount.value)
                    }
                }
                Note { text: "Keys without a colour are staged as off (#000000). “freeze” stops the animation on its current frame; “off” darkens all keys (0% brightness). Staging also enables per-key mode (byte 0x5f9 = 1); selecting a preset above switches back." }
            }
            }
            }
            // Profiles and recovery
            ColumnLayout {
                spacing: 14
                Label { text: "Profiles & recovery"; font.pixelSize: 22 }
                Note { text: "One device profile region. Local JSON files are snapshots, not additional onboard slots." }
                RowLayout {
                    Action { text: "Open snapshot…"; enabled: !window.deviceState.busy && !window.deviceState.dirty; onClicked: { window.fileAction = "open"; openFile.open() } }
                    Action { text: window.deviceState.initialized ? "Rename profile…" : "Create profile…"; enabled: window.deviceState.loaded && !window.deviceState.busy; onClicked: profileDialog.open() }
                }
                RowLayout {
                    Action { text: "Export baseline backup…"; enabled: window.deviceState.loaded && !window.deviceState.busy; onClicked: { window.fileAction = "backup"; saveFile.open() } }
                    Action { text: "Export staged profile…"; enabled: window.deviceState.loaded && !window.deviceState.busy; onClicked: { window.fileAction = "draft"; saveFile.open() } }
                    Action { text: "Stage profile restore…"; enabled: window.deviceState.loaded && !window.deviceState.busy; onClicked: restoreDialog.open() }
                }
                Note { text: "Snapshots contain the profile and custom LED bytes, but not macro storage or firmware. Profile restore does not restore custom LEDs or macros."; color: "#dba836" }
                Note { text: "Automatic pre-write backups: " + window.deviceState.backupDir }
                Note { text: "Apply always asks for confirmation, saves a backup first and verifies by readback. Launch with --read-only to disable writes. Never run the desktop app as root." }
                Item { Layout.fillHeight: true }
            }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: "#303030" }
        Note { text: window.deviceState.error || window.deviceState.message; color: window.deviceState.error ? "#ffb0a0" : "#a5a5a5"; maximumLineCount: 3; elide: Text.ElideRight }
        RowLayout {
            Layout.fillWidth: true
            Label { text: window.deviceState.writesEnabled ? "Writes enabled (confirmed on Apply)" : "READ-ONLY DEVICE ACCESS"; color: "#dba836"; font.pixelSize: 11 }
            Label { text: window.deviceState.dirty ? window.deviceState.byteCount + " bytes staged" : "No pending edits"; color: "#a5a5a5" }
            Item { Layout.fillWidth: true }
            Action { text: "Review changes…"; objectName: "reviewButton"; enabled: !window.deviceState.busy; onClicked: reviewDialog.open() }
            Action { text: "Discard"; objectName: "discardButton"; enabled: window.deviceState.dirty && !window.deviceState.busy; onClicked: discardDialog.open() }
            Action { text: "Apply…"; objectName: "applyButton"; enabled: window.deviceState.canApply; onClicked: applyDialog.open() }
        }
    }

    FileDialog {
        id: openFile; title: "Open Retro 87 snapshot"; nameFilters: ["Retro 87 snapshots (*.json)"]
        onAccepted: { if (window.fileAction === "restore") bridge.restoreProfile(selectedFile.toString()); else bridge.openSnapshot(selectedFile.toString()) }
    }
    FileDialog {
        id: saveFile; title: "Save snapshot to a new file"; fileMode: FileDialog.SaveFile; defaultSuffix: "json"; nameFilters: ["Retro 87 snapshots (*.json)"]
        onAccepted: bridge.exportSnapshot(selectedFile.toString(), window.fileAction === "draft")
    }
    Dialog {
        id: profileDialog; objectName: "profileDialog"; title: window.deviceState.initialized ? "Rename profile (staged)" : "Create profile (staged)"
        anchors.centerIn: parent; modal: true; width: 420; standardButtons: Dialog.Ok | Dialog.Cancel
        contentItem: ColumnLayout {
            Note { text: "Use 1–16 UTF-16 code units. This only stages the profile; Apply is a separate operation." }
            TextField { id: profileName; objectName: "profileName"; text: "Linux"; Layout.fillWidth: true; selectByMouse: true }
        }
        onAccepted: { if (window.deviceState.initialized) bridge.renameProfile(profileName.text); else bridge.createProfile(profileName.text) }
    }
    Dialog {
        id: discardDialog; objectName: "discardDialog"; title: "Discard pending edits?"; anchors.centerIn: parent; width: 540; modal: true; standardButtons: Dialog.Yes | Dialog.No
        contentItem: Label { text: "Only local edits are discarded. Device settings are unchanged." }
        onAccepted: bridge.discard()
    }
    Dialog {
        id: restoreDialog; title: "Stage profile-only restoration?"; anchors.centerIn: parent; modal: true; width: 520; standardButtons: Dialog.Yes | Dialog.No
        contentItem: Note { text: "This replaces all current staged profile edits. Macro storage and custom LED bytes will NOT be restored. Choose a snapshot next, then review and Apply separately." }
        onAccepted: { window.fileAction = "restore"; openFile.open() }
    }
    Dialog {
        id: reviewDialog; objectName: "reviewDialog"; title: window.deviceState.dirty ? "Pending changes — no settings written" : "No pending changes"
        anchors.centerIn: parent; modal: true; focus: true; width: 700; height: 430; standardButtons: Dialog.Close
        contentItem: ScrollView {
            contentWidth: availableWidth
            TextArea {
                objectName: "reviewText"
                text: window.deviceState.dirty
                    ? window.deviceState.changes.join("\n") + "\n\nByte ranges (before → after):\n" + window.deviceState.ranges.join("\n")
                    : window.deviceState.loaded
                        ? "No changes have been staged. Your loaded profile is unchanged.\n\nChoose an assignment, lighting setting, or sound level, then click its Stage button. Selecting a key or adjusting a control alone does not stage a change.\n\nReview never writes to the keyboard. Apply is a separate, explicitly enabled operation."
                        : "No configuration is loaded. Read / reconnect or open a snapshot from Profiles first.\n\nReview never writes to the keyboard."
                readOnly: true; wrapMode: TextEdit.Wrap; font.family: "monospace"; textFormat: TextEdit.PlainText; selectByMouse: true
            }
        }
    }
    Dialog {
        id: applyDialog; objectName: "applyDialog"; title: "Apply these changes to your keyboard?"; anchors.centerIn: parent; modal: true; width: 570; standardButtons: Dialog.Yes | Dialog.No
        contentItem: Note { text: window.deviceState.changes.join("\n") + "\n\nThe keyboard is re-read and backed up first, and every write is verified by readback. A disconnect mid-write can leave partial changes; restore from the backup if that happens.\n\nThis WILL change device settings. Continue?" }
        onAccepted: bridge.applyConfirmed()
    }
    Dialog {
        id: quitDialog; title: "Close and lose staged edits?"; anchors.centerIn: parent; modal: true; standardButtons: Dialog.Yes | Dialog.No
        onAccepted: { window.exitConfirmed = true; window.close() }
    }
}
