import QtQuick
import QtQuick.Controls

Rectangle {
    id: panel
    property bool opened: false
    property string source: "internet"
    property string confirmKey: ""
    property string movedKey: ""
    readonly property bool canRemove: ["idle", "stopped", "completed"].indexOf(radioBridge.state) >= 0
    visible: opened; color: "#111922"
    function open(sourceName) {
        source = sourceName; confirmKey = ""; movedKey = ""; removeProgress.checked = false
        presetBridge.open(sourceName); opened = true
    }
    MouseArea { anchors.fill: parent }
    component Action: Button {
        id: button
        focusPolicy: Qt.NoFocus; font.pixelSize: 19
        contentItem: Text {
            text: button.text; font: button.font; textFormat: Text.PlainText
            color: "#edf2f5"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            opacity: button.enabled ? 1 : 0.4
        }
        background: Rectangle { radius: 12; color: button.down ? "#43675f" : "#283744" }
    }
    Text { x: 32; y: 24; text: panel.source === "podcast" ? "Manage subscriptions" : "Manage presets"; color: "#f3ddb1"; font.pixelSize: 30; font.bold: true }
    Action {
        x: 1008; y: 16; width: 240; height: 60; text: "Back to Presets"; enabled: !presetBridge.busy
        onClicked: { panel.opened = false; radioBridge.refreshCatalogue() }
    }
    Text {
        x: 32; y: 96; width: 920; height: 60; textFormat: Text.PlainText
        text: presetBridge.message
        color: "#a3e4ca"; font.pixelSize: 20; wrapMode: Text.WordWrap
    }
    Action { x: 1008; y: 96; width: 240; height: 60; text: "Stop playback"; enabled: !panel.canRemove; onClicked: radioBridge.stop() }
    CheckBox {
        id: removeProgress
        x: 32; y: 162; width: 1170; height: 60; visible: panel.source === "podcast"
        enabled: !presetBridge.busy
        text: "Also delete this podcast's saved listening progress (otherwise kept)"
        font.pixelSize: 21
    }
    Connections {
        target:presetBridge
        function onSaved() {
            if (!panel.opened || panel.movedKey === "") return
            Qt.callLater(function() {
                for(var i=0;i<presetBridge.items.length;++i)
                    if(presetBridge.items[i].key===panel.movedKey) {presets.positionViewAtIndex(i,ListView.Contain);break}
            })
        }
    }
    ListView {
        id: presets
        x: 32; y: 234; width: 1216; height: 454; spacing: 12; clip: true; model: presetBridge.items
        delegate: Rectangle {
            required property var modelData
            required property int index
            width: presets.width; height: 112; radius: 12; color: "#1c2934"
            border.color: panel.movedKey === modelData.key ? "#a3e4ca" : "transparent"; border.width:2
            Text { x: 16; y: 12; width: parent.width - 740; height: 36; text: modelData.name; textFormat: Text.PlainText; color: "#edf2f5"; font.pixelSize: 23; elide: Text.ElideRight }
            Text {
                x: 16; y: 56; width: parent.width - 740; height: 44
                text: panel.confirmKey === modelData.key ? "Confirm removal of this named preset/subscription?" : modelData.detail
                textFormat: Text.PlainText; color: "#aabcc9"; font.pixelSize: 18; wrapMode: Text.WordWrap
            }
            Action {
                anchors.right: parent.right; anchors.rightMargin: 568; y:20; width:148; height:72
                text:"Move up"; enabled:!presetBridge.busy && index > 0
                onClicked:{panel.confirmKey="";panel.movedKey=modelData.key;presetBridge.move(index,-1)}
            }
            Action {
                anchors.right: parent.right; anchors.rightMargin: 408; y:20; width:148; height:72
                text:"Move down"; enabled:!presetBridge.busy && index + 1 < presetBridge.items.length
                onClicked:{panel.confirmKey="";panel.movedKey=modelData.key;presetBridge.move(index,1)}
            }
            Action {
                anchors.right: parent.right; anchors.rightMargin: 172; y: 20; width: 224; height: 72
                enabled: !presetBridge.busy && panel.canRemove
                text: panel.confirmKey === modelData.key ? "Confirm removal" : panel.source === "podcast" ? "Unsubscribe" : "Delete"
                onClicked: {
                    if (panel.confirmKey === modelData.key) { presetBridge.remove(index, removeProgress.checked); panel.confirmKey = "" }
                    else panel.confirmKey = modelData.key
                }
            }
            Action {
                anchors.right: parent.right; anchors.rightMargin: 12; y: 20; width: 148; height: 72; text: "Cancel"
                visible: panel.confirmKey === modelData.key; enabled: !presetBridge.busy
                onClicked: panel.confirmKey = ""
            }
        }
        ScrollBar.vertical: ScrollBar {}
    }
}
