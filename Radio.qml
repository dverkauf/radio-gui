import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: root
    property bool windowed: false
    property int contentRotation: 0
    property string backendName: "unknown"
    width: 1280; height: 720
    visible: true
    visibility: windowed ? Window.Windowed : Window.FullScreen
    title: "La Calma · Radio"
    color: "#111922"
    font.family: "DejaVu Sans"
    font.pixelSize: 22
    Shortcut { sequence: "Escape"; onActivated: Qt.quit() }
    Shortcut { sequence: "Ctrl+Q"; onActivated: Qt.quit() }
    component TouchButton: Button {
        id: button
        property bool accent: false
        font.pixelSize: 23
        contentItem: Text {
            text: button.text; font: button.font; textFormat: Text.PlainText
            color: button.accent ? "#102521" : "#edf2f5"
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            opacity: button.enabled ? 1 : 0.4
        }
        background: Rectangle {
            radius: 14
            color: button.down ? "#63bfa7" : button.accent ? "#a3e4ca" : "#283744"
            opacity: button.enabled ? 1 : 0.5
            border.width: button.activeFocus ? 2 : 0; border.color: "white"
        }
    }
    Item {
        width: 1280; height: 720; anchors.centerIn: parent
        rotation: root.contentRotation
        scale: root.contentRotation % 180 === 0 ? Math.min(root.width / width, root.height / height) : Math.min(root.height / width, root.width / height)
        Rectangle {
            x: 32; y: 16; width: 88; height: 88; radius: 16; color: "#faf6ed"
            Image { anchors.fill: parent; anchors.margins: 6; source: "assets/la-calma.svg"; fillMode: Image.PreserveAspectFit }
        }
        Text { x: 146; y: 23; text: "La Calma · Radio"; color: "#f3ddb1"; font.pixelSize: 32; font.bold: true }
        Text { x: 146; y: 68; text: (radioBridge.activeSource ? radioBridge.activeSource.toUpperCase() + " · " : "") + radioBridge.state; color: "#aabcc9"; textFormat: Text.PlainText }
        TouchButton { x: 1128; y: 25; width: 120; height: 76; text: "Exit"; onClicked: Qt.quit() }
        Row {
            x: 32; y: 120; spacing: 16
            Repeater {
                model: [{key: "fm", title: "FM"}, {key: "dab", title: "DAB+"}, {key: "internet", title: "Internet"}]
                delegate: TouchButton {
                    required property var modelData
                    width: 240; height: 60; text: modelData.title
                    accent: radioBridge.source === modelData.key
                    onClicked: radioBridge.setSource(modelData.key)
                }
            }
        }
        ListView {
            id: stations
            x: 32; y: 198; width: 1216; height: 234; spacing: 12; clip: true
            model: radioBridge.stations
            delegate: TouchButton {
                required property var modelData
                width: stations.width; height: 76
                text: modelData.name + (modelData.detail ? " · " + modelData.detail : ""); accent: radioBridge.selectedId === modelData.id
                enabled: radioBridge.state !== "connecting" && radioBridge.state !== "failed"
                onClicked: radioBridge.play(modelData.id)
            }
            ScrollBar.vertical: ScrollBar {}
        }
        Text {
            x: 48; y: 275; width: 1184
            visible: radioBridge.state !== "connecting" && radioBridge.stations.length === 0
            text: radioBridge.catalogueError !== "" ? "Cannot read saved stations: " + radioBridge.catalogueError
                : "No saved " + radioBridge.source.toUpperCase() + " stations. Use radio-cli to scan or save stations, then reopen this screen."
            textFormat: Text.PlainText
            color: "#aabcc9"; wrapMode: Text.WordWrap
        }
        Text { x: 32; y: 447; width: 1216; text: radioBridge.station; textFormat: Text.PlainText; color: "#edf2f5"; font.pixelSize: 28; elide: Text.ElideRight }
        Text { x: 32; y: 491; width: 1216; height: 60; text: radioBridge.broadcastText; textFormat: Text.PlainText; color: "#a3e4ca"; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
        Text { x: 32; y: 552; width: 1216; height: 52; text: radioBridge.error; textFormat: Text.PlainText; color: "#ffbdad"; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
        TouchButton { x: 32; y: 620; width: 336; height: 72; text: "Stop"; enabled: ["starting", "playing", "paused", "stopping"].indexOf(radioBridge.state) >= 0; onClicked: radioBridge.stop() }
        Text { x: 408; y: 608; text: "Volume: " + Math.round(radioBridge.volume * 100) + "%"
            + (Math.abs(radioBridge.requestedVolume - radioBridge.volume) > 0.001
                ? " · requested " + Math.round(radioBridge.requestedVolume * 100) + "%" : ""); color: "#edf2f5" }
        Slider {
            x: 400; y: 643; width: 848; height: 48
            from: 0; to: 1; stepSize: 0.05; value: radioBridge.requestedVolume
            enabled: radioBridge.volumeControl
            onMoved: radioBridge.setVolume(value)
        }
    }
}
