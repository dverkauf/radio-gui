import QtQuick
import QtQuick.Controls

Rectangle {
    id: keyboard
    property var editor
    property bool opened: false
    property string language: "en"
    property bool shifted: false
    property string mode: "letters"
    readonly property var languages: [
        {code: "en", label: "EN"}, {code: "de", label: "DE"},
        {code: "es", label: "ES"}, {code: "he", label: "עברית"},
        {code: "el", label: "Ελληνικά"}
    ]
    readonly property var keyRows: editor ? editor.rows(language, shifted, mode) : []
    visible: opened
    height: 336
    radius: 16
    color: "#1c2934"
    border.color: "#405562"

    component KeyButton: Button {
        id: key
        property bool accent: false
        height: 54
        focusPolicy: Qt.NoFocus
        font.pixelSize: 25
        contentItem: Text {
            text: key.text; font: key.font; textFormat: Text.PlainText
            color: key.accent ? "#102521" : "#edf2f5"
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: 10
            color: key.down ? "#63bfa7" : key.accent ? "#a3e4ca" : "#344753"
        }
    }

    Row {
        x: 12; y: 10; spacing: 7
        Repeater {
            model: keyboard.languages
            KeyButton {
                required property var modelData
                width: modelData.code === "el" ? 134 : modelData.code === "he" ? 106 : 80
                height: 44
                text: modelData.label
                font.pixelSize: 21
                accent: keyboard.language === modelData.code
                onClicked: {
                    keyboard.language = modelData.code
                    keyboard.shifted = false
                    keyboard.mode = "letters"
                }
            }
        }
        KeyButton {
            width: 136; height: 44
            text: keyboard.mode === "accents" ? "ABC" : "Accents"
            font.pixelSize: 21
            enabled: keyboard.language !== "he"
            accent: keyboard.mode === "accents"
            onClicked: keyboard.mode = keyboard.mode === "accents" ? "letters" : "accents"
        }
        KeyButton {
            width: 112; height: 44; text: keyboard.mode === "symbols" ? "ABC" : "123 / #"
            font.pixelSize: 21; accent: keyboard.mode === "symbols"
            onClicked: keyboard.mode = keyboard.mode === "symbols" ? "letters" : "symbols"
        }
        KeyButton {
            width: 112; height: 44; text: "Hide"; font.pixelSize: 21
            onClicked: keyboard.opened = false
        }
    }

    Column {
        x: 12; y: 63; width: parent.width - 24; spacing: 6
        Repeater {
            model: keyboard.keyRows
            Row {
                id: keyRow
                required property var modelData
                readonly property var letters: modelData
                width: implicitWidth
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: 6
                Repeater {
                    model: keyRow.letters
                    KeyButton {
                        required property string modelData
                        width: Math.min(110, (keyboard.width - 24 - (keyRow.letters.length - 1) * 6) / keyRow.letters.length)
                        text: modelData
                        onClicked: {
                            keyboard.editor.commit(modelData)
                            if (keyboard.shifted) keyboard.shifted = false
                        }
                    }
                }
            }
        }
    }

    Row {
        x: 12; y: 249; spacing: 7
        KeyButton {
            width: 112; text: "Shift"; accent: keyboard.shifted
            enabled: keyboard.language !== "he" && keyboard.mode !== "symbols"
            onClicked: keyboard.shifted = !keyboard.shifted
        }
        KeyButton { width: 70; text: "←"; onClicked: keyboard.editor.command("left") }
        KeyButton { width: 70; text: "→"; onClicked: keyboard.editor.command("right") }
        KeyButton { width: 144; text: "Select all"; font.pixelSize: 21; onClicked: keyboard.editor.command("select_all") }
        KeyButton { width: 456; text: "Space"; onClicked: keyboard.editor.commit(" ") }
        KeyButton {
            width: 180; text: "Backspace"; font.pixelSize: 22
            autoRepeat: true; autoRepeatDelay: 450; autoRepeatInterval: 70
            onClicked: keyboard.editor.command("backspace")
        }
        KeyButton { width: 150; text: "Done"; accent: true; onClicked: keyboard.editor.command("enter") }
    }
}
