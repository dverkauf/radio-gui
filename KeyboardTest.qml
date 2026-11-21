import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: root
    property bool windowed: false
    property string backendName: "unknown"
    property int contentRotation: 0
    property string submitted: ""
    width: 1280; height: 720
    visible: true
    visibility: windowed ? Window.Windowed : Window.FullScreen
    title: "La Calma · keyboard test"
    color: "#111922"
    font.family: "DejaVu Sans"
    font.pixelSize: 24
    Shortcut { sequence: "Ctrl+Q"; onActivated: Qt.quit() }
    Shortcut { sequence: "Escape"; onActivated: { if (panel.opened) panel.opened = false; else Qt.quit() } }

    Item {
        width: 1280; height: 720
        anchors.centerIn: parent
        rotation: root.contentRotation
        scale: root.contentRotation % 180 === 0
            ? Math.min(root.width / width, root.height / height)
            : Math.min(root.height / width, root.width / height)
        Rectangle {
            x: 32; y: 12; width: 88; height: 88; radius: 16; color: "#faf6ed"
            Image { anchors.fill: parent; anchors.margins: 4; source: "assets/la-calma.svg"; fillMode: Image.PreserveAspectFit }
        }
        Text { x: 146; y: 23; text: "La Calma · keyboard"; color: "#e8d8b6"; font.pixelSize: 32; font.bold: true }
        Text { x: 146; y: 66; text: "EN · DE · ES · עברית · Ελληνικά   |   " + root.backendName; color: "#a5b7c4"; font.pixelSize: 20 }
        Button {
            x: 1000; y: 24; width: 112; height: 62; text: "Keyboard"; font.pixelSize: 19
            focusPolicy: Qt.NoFocus
            onClicked: { search.forceActiveFocus(); keyboardEditor.setTarget(search); panel.opened = true }
        }
        Button { x: 1126; y: 24; width: 122; height: 62; text: "Exit"; onClicked: Qt.quit() }

        Text { x: 32; y: 113; text: "Search text · tap to type"; color: "#a3e4ca"; font.pixelSize: 21 }
        TextField {
            id: search
            objectName: "keyboardSearch"
            x: 32; y: 143; width: 1216; height: 64
            font.pixelSize: 29
            color: "#edf2f5"; selectionColor: "#43675f"; selectedTextColor: "#ffffff"
            placeholderText: "NDR 2 · עושים תוכנה · ελληνικό ραδιόφωνο"
            selectByMouse: true
            maximumLength: 512
            background: Rectangle { radius: 12; color: "#253640"; border.color: search.activeFocus ? "#a3e4ca" : "#405562"; border.width: 2 }
            onActiveFocusChanged: if (activeFocus) { keyboardEditor.setTarget(search); panel.opened = true }
            onAccepted: { root.submitted = text; panel.opened = false }
            TapHandler { onTapped: { search.forceActiveFocus(); keyboardEditor.setTarget(search); panel.opened = true } }
        }
        Text { x: 32; y: 223; text: "Feed URL · second field / symbols test"; color: "#a3e4ca"; font.pixelSize: 21 }
        TextField {
            id: url
            objectName: "keyboardUrl"
            x: 32; y: 253; width: 1216; height: 64
            font.pixelSize: 26
            color: "#edf2f5"; selectionColor: "#43675f"; selectedTextColor: "#ffffff"
            placeholderText: "https://example.org/feed.xml"
            horizontalAlignment: TextInput.AlignLeft
            selectByMouse: true
            maximumLength: 2048
            background: Rectangle { radius: 12; color: "#253640"; border.color: url.activeFocus ? "#a3e4ca" : "#405562"; border.width: 2 }
            onActiveFocusChanged: if (activeFocus) { keyboardEditor.setTarget(url); panel.opened = true }
            onAccepted: { root.submitted = text; panel.opened = false }
            TapHandler { onTapped: { url.forceActiveFocus(); keyboardEditor.setTarget(url); panel.opened = true } }
        }
        Text {
            x: 32; y: 330; width: 1216; height: 30
            text: root.submitted === "" ? "Done hides the keyboard. Inputs stay on this screen only." : "Submitted sample: " + root.submitted
            textFormat: Text.PlainText; elide: Text.ElideRight
            color: "#a5b7c4"; font.pixelSize: 19
        }
        KeyboardPanel { id: panel; x: 16; y: 372; width: 1248; editor: keyboardEditor }
        Text {
            x: 32; y: 440; visible: !panel.opened
            text: "Tap either field to open the keyboard.\nUse Accents for ä ö ü ß, á é í ó ú ñ, ά έ ή ί ό ύ ώ.\nSelect all + Backspace clears a field. Nothing is sent or saved."
            color: "#c7d7df"; font.pixelSize: 25; lineHeight: 1.5
        }
    }
}
