import QtQuick
import QtQuick.Controls

Rectangle {
    id: panel
    property bool opened: false
    property string source: "fm"
    property int confirmIndex: -1
    visible: opened
    color: "#111922"
    function open(sourceName) {
        source = sourceName; confirmIndex = -1; scanBridge.open(sourceName); opened = true
    }
    MouseArea { anchors.fill: parent }
    component Action: Button {
        id: button
        focusPolicy: Qt.NoFocus; font.pixelSize: 22
        contentItem: Text {
            text: button.text; font: button.font; textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: "#edf2f5"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            opacity: button.enabled ? 1 : 0.4
        }
        background: Rectangle { radius: 12; color: button.down ? "#43675f" : "#283744" }
    }
    Text { x: 32; y: 24; text: panel.source === "fm" ? "Find FM stations" : "Find DAB+ stations"; color: "#f3ddb1"; font.pixelSize: 30; font.bold: true }
    Action {
        x: 1008; y: 16; width: 240; height: 60; text: "Back to Presets"; enabled: !scanBridge.busy
        onClicked: { panel.opened = false; radioBridge.refreshCatalogue() }
    }
    ComboBox {
        x: 32; y: 96; width: 472; height: 60; visible: panel.source === "dab"
        model: scanBridge.locations; textRole: "label"; valueRole: "name"
        currentIndex: { for (var i = 0; i < scanBridge.locations.length; ++i) if (scanBridge.locations[i].name === scanBridge.location) return i; return -1 }
        enabled: !scanBridge.busy
        onActivated: scanBridge.setLocation(currentValue)
        font.pixelSize: 22
    }
    Action {
        x:520; y:96; width:232; height:60; text:"Reception locations…"
        visible:panel.source==="dab"; enabled:!scanBridge.busy
        onClicked:reception.open()
    }
    Text {
        x: 32; y: 108; width: 720; height: 50; visible: panel.source === "fm"
        text: "FM/DAB playback stops before scanning. Internet/podcasts can continue."
        textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: "#aabcc9"; font.pixelSize: 20
    }
    Action { x: 768; y: 96; width: 240; height: 60; text: "Start new scan"; enabled: !scanBridge.busy; onClicked: { panel.confirmIndex = -1; scanBridge.scan() } }
    Action { x: 1024; y: 96; width: 224; height: 60; text: scanBridge.cancelling ? "Cleaning up…" : "Cancel"; enabled: scanBridge.busy && !scanBridge.cancelling; onClicked: scanBridge.cancel() }
    Text {
        x: 32; y: 198; width: 1150; height: 50; text: scanBridge.message
        textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: "#a3e4ca"; font.pixelSize: 19
    }
    Text {
        x:32; y:164; width:1216; height:28; visible:panel.source === "dab"
        text: { for(var i=0;i<scanBridge.locations.length;++i) if(scanBridge.locations[i].name===scanBridge.location) return "Blocks: " + scanBridge.locations[i].channels.join(", "); return "" }
        textFormat:Text.PlainText; color:"#aabcc9"; font.pixelSize:16; elide:Text.ElideRight
    }
    BusyIndicator { x: 1192; y: 190; width: 44; height: 44; running: scanBridge.busy }
    ListView {
        id: results
        x: 32; y: 260; width: 1216; height: 420; clip: true; spacing: 10; model: scanBridge.items
        delegate: Rectangle {
            required property var modelData
            required property int index
            width: results.width; height: 124; radius: 12; color: "#1c2934"
            Text { x: 16; y: 10; width: parent.width - 352; height: 34; text: modelData.name; textFormat: Text.PlainText; color: "#edf2f5"; font.pixelSize: 23; elide: Text.ElideRight }
            Text {
                x: 16; y: 50; width: parent.width - 352; height: 66
                text: panel.confirmIndex === index && panel.source === "dab"
                    ? "Saving replaces this block's saved services with all " + modelData.count + " services listed. Tap Confirm to save."
                    : modelData.detail
                textFormat: Text.PlainText; color: "#aabcc9"; font.pixelSize: 18; wrapMode: Text.WordWrap; maximumLineCount: 3; elide: Text.ElideRight
            }
            Row {
                anchors.right: parent.right; anchors.rightMargin: 12; y: 22; spacing: 8
                visible: panel.source === "fm"
                Action { width: 148; height: 80; text: "Identify"; enabled: !scanBridge.busy; onClicked: scanBridge.identify(index) }
                Action { width: 172; height: 80; text: "Save preset"; enabled: !scanBridge.busy && modelData.can_save === true; onClicked: scanBridge.save(index) }
            }
            Action {
                anchors.right: parent.right; anchors.rightMargin: 12; y: 22; width: 244; height: 80
                visible: panel.source === "dab"
                text: panel.confirmIndex === index ? "Confirm save block" : "Save block (" + modelData.count + ")"
                enabled: !scanBridge.busy
                onClicked: {
                    if (panel.confirmIndex === index) { scanBridge.save(index); panel.confirmIndex = -1 }
                    else panel.confirmIndex = index
                }
            }
        }
        ScrollBar.vertical: ScrollBar {}
    }
    ReceptionLocations { id:reception; anchors.fill:parent; z:10 }
}
