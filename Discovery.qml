import QtQuick
import QtQuick.Controls

Rectangle {
    id: panel
    property bool opened: false
    property string source: "internet"
    signal closed()
    visible: opened
    color: "#111922"
    function open(sourceName) {
        source = sourceName
        query.text = ""
        keyboard.opened = false
        discoveryBridge.open(sourceName)
        opened = true
    }
    MouseArea { anchors.fill: parent }
    component Action: Button {
        id: button
        focusPolicy: Qt.NoFocus
        font.pixelSize: 22
        contentItem: Text {
            text: button.text; font: button.font; textFormat: Text.PlainText
            color: "#edf2f5"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            opacity: button.enabled ? 1 : 0.4
        }
        background: Rectangle { radius: 12; color: button.down ? "#43675f" : "#283744" }
    }
    Text {
        x: 32; y: 24; text: panel.source === "podcast" ? "Find podcasts" : "Find Internet stations"
        color: "#f3ddb1"; font.pixelSize: 30; font.bold: true
    }
    Action {
        x: 1008; y: 16; width: 240; height: 60; text: "Back to Presets"
        enabled: !discoveryBridge.saving
        onClicked: {
            discoveryBridge.cancel(); keyboard.opened = false; panel.opened = false
            radioBridge.refreshCatalogue(); panel.closed()
        }
    }
    TextField {
        id: query
        objectName: "discoveryQuery"
        x: 32; y: 96; width: 864; height: 64
        color: "#edf2f5"; font.pixelSize: 27; maximumLength: 200
        placeholderText: "Enter a name · עברית · Ελληνικά"
        selectByMouse: true
        readOnly: discoveryBridge.busy
        background: Rectangle { radius: 12; color: "#253640"; border.color: query.activeFocus ? "#a3e4ca" : "#405562"; border.width: 2 }
        onActiveFocusChanged: if (activeFocus) { keyboardEditor.setTarget(query); keyboard.opened = true }
        onAccepted: { keyboard.opened = false; discoveryBridge.search(text) }
        TapHandler { onTapped: if (!discoveryBridge.busy) { query.forceActiveFocus(); keyboardEditor.setTarget(query); keyboard.opened = true } }
    }
    Action {
        x: 912; y: 96; width: 160; height: 64; text: "Search"
        enabled: !discoveryBridge.busy && query.text.trim().length > 0
        onClicked: { keyboard.opened = false; discoveryBridge.search(query.text) }
    }
    Action {
        x: 1088; y: 96; width: 160; height: 64; text: "Cancel"
        enabled: discoveryBridge.busy && !discoveryBridge.saving
        onClicked: discoveryBridge.cancel()
    }
    Text {
        x: 32; y: 174; width: 1216; height: 60
        text: discoveryBridge.message; textFormat: Text.PlainText; wrapMode: Text.WordWrap
        color: "#a3e4ca"; font.pixelSize: 20
    }
    ListView {
        id: results
        x: 32; y: 242; width: 1216; height: keyboard.opened ? 100 : 446
        visible: !keyboard.opened
        clip: true; spacing: 10; model: discoveryBridge.items
        delegate: Rectangle {
            required property var modelData
            required property int index
            width: results.width; height: 100; radius: 12; color: "#1c2934"
            Text {
                x: 16; y: 12; width: parent.width - 216; height: 36
                text: modelData.name; textFormat: Text.PlainText; color: "#edf2f5"; font.pixelSize: 23; elide: Text.ElideRight
            }
            Text {
                x: 16; y: 55; width: parent.width - 216; height: 32
                text: modelData.detail; textFormat: Text.PlainText; color: "#aabcc9"; font.pixelSize: 18; elide: Text.ElideRight
            }
            Action {
                anchors.right: parent.right; anchors.rightMargin: 12; y: 15; width: 176; height: 70
                text: panel.source === "podcast" ? "Subscribe" : "Save"
                enabled: !discoveryBridge.busy
                onClicked: discoveryBridge.save(index)
            }
        }
        ScrollBar.vertical: ScrollBar {}
    }
    KeyboardPanel { id: keyboard; x: 16; y: 360; width: 1248; editor: keyboardEditor }
}
