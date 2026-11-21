import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: root
    property bool windowed: false
    property int contentRotation: 0
    property string backendName: "unknown"
    property int pageIndex: 0
    property int tapCount: 0
    property string selection: "NDR 2"
    readonly property var sections: ["FM", "DAB+", "Internet", "Podcasts"]
    readonly property var samples: pageIndex === 3
        ? ["עושים תוכנה", "עושים היסטוריה", "English + עברית"]
        : pageIndex === 2 ? ["NDR 2 · Internet", "Jazz · Internet", "World radio"]
        : pageIndex === 1 ? ["NDR 2 NDS", "Deutschlandfunk", "RADIO 21"]
        : ["NDR 2", "RADIO 21", "Deutschlandfunk"]
    width: 1280
    height: 720
    visible: true
    visibility: windowed ? Window.Windowed : Window.FullScreen
    title: "Radio · display prototype"
    color: "#111922"
    font.family: "DejaVu Sans"
    font.pixelSize: 22

    Shortcut { sequence: "Escape"; onActivated: Qt.quit() }
    Shortcut { sequence: "Ctrl+Q"; onActivated: Qt.quit() }

    component TouchButton: Button {
        id: control
        property bool accent: false
        implicitHeight: 76
        font.pixelSize: 24
        contentItem: Text {
            text: control.text
            font: control.font
            color: control.accent ? "#102521" : "#edf2f5"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            textFormat: Text.PlainText
        }
        background: Rectangle {
            radius: 14
            color: control.down ? "#63bfa7" : control.accent ? "#a3e4ca" : "#283744"
            border.width: control.activeFocus ? 2 : 0
            border.color: "#ffffff"
        }
    }

    Item {
        id: canvas
        width: 1280
        height: 720
        anchors.centerIn: parent
        rotation: root.contentRotation
        scale: root.contentRotation % 180 === 0
            ? Math.min(root.width / width, root.height / height)
            : Math.min(root.height / width, root.width / height)

        RowLayout {
            x: 32; y: 8; width: 1216; height: 104
            spacing: 18
            Rectangle {
                Layout.preferredWidth: 96
                Layout.preferredHeight: 96
                radius: 16
                color: "#faf6ed"
                Image {
                    anchors.fill: parent
                    anchors.margins: 4
                    source: "assets/la-calma.svg"
                    sourceSize.width: 192
                    sourceSize.height: 192
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                }
            }
            ColumnLayout {
                Layout.fillWidth: true
                Text { text: "La Calma"; color: "#e8d8b6"; font.pixelSize: 32; font.bold: true }
                Text { text: "Display & touch check · no audio"; color: "#a5b7c4"; font.pixelSize: 20 }
            }
            TouchButton { text: "Exit"; Layout.preferredWidth: 130; onClicked: Qt.quit() }
        }

        ColumnLayout {
            x: 32; y: 130; width: 210; spacing: 16
            Repeater {
                model: root.sections
                TouchButton {
                    required property string modelData
                    required property int index
                    text: modelData
                    accent: root.pageIndex === index
                    Layout.fillWidth: true
                    onClicked: {
                        root.pageIndex = index
                        root.selection = root.samples[0]
                        root.tapCount++
                    }
                }
            }
        }

        ColumnLayout {
            x: 280; y: 130; width: 968; spacing: 16
            Text { text: root.sections[root.pageIndex]; color: "#ffffff"; font.pixelSize: 34; font.bold: true }
            Text { text: "Tap a sample to check selection feedback"; color: "#a5b7c4"; font.pixelSize: 21 }
            Repeater {
                model: root.samples
                Rectangle {
                    required property string modelData
                    Layout.fillWidth: true
                    Layout.preferredHeight: 82
                    radius: 14
                    color: root.selection === modelData ? "#263f3b" : "#1c2934"
                    border.width: root.selection === modelData ? 2 : 1
                    border.color: root.selection === modelData ? "#a3e4ca" : "#344451"
                    Text {
                        anchors.fill: parent; anchors.margins: 22
                        text: modelData; textFormat: Text.PlainText
                        color: "#f1f5f7"; font.pixelSize: 27
                        horizontalAlignment: root.pageIndex === 3 ? Text.AlignRight : Text.AlignLeft
                        verticalAlignment: Text.AlignVCenter
                    }
                    TapHandler { onTapped: { root.selection = modelData; root.tapCount++ } }
                }
            }
            Text {
                Layout.fillWidth: true
                text: root.pageIndex === 3 ? "מצילים חיי אדם באמצעות Deep Learning · פרק 42" : "Selected sample: " + root.selection
                textFormat: Text.PlainText
                color: "#d4e4ec"; font.pixelSize: 24
                horizontalAlignment: root.pageIndex === 3 ? Text.AlignRight : Text.AlignLeft
                wrapMode: Text.WordWrap
            }
        }

        Rectangle {
            x: 32; y: 566; width: 1216; height: 122; radius: 18; color: "#1c2934"
            RowLayout {
                anchors.fill: parent; anchors.margins: 22; spacing: 24
                ColumnLayout {
                    Layout.preferredWidth: 225
                    Text { text: "Touch events: " + root.tapCount; color: "#a3e4ca"; font.pixelSize: 23 }
                    Text { text: "Qt platform: " + root.backendName; color: "#a5b7c4"; font.pixelSize: 16 }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Text { text: "Slider test: " + Math.round(slider.value * 100) + "%"; color: "#ffffff"; font.pixelSize: 22 }
                    Slider {
                        id: slider
                        Layout.fillWidth: true; Layout.preferredHeight: 52
                        from: 0; to: 1; value: 0.35
                        onMoved: root.tapCount++
                    }
                }
                TouchButton {
                    text: "Touch test"; accent: true; Layout.preferredWidth: 185
                    onClicked: root.tapCount++
                }
            }
        }
    }
}
