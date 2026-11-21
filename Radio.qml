import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: root
    property bool windowed: false
    property int contentRotation: 0
    property string backendName: "unknown"
    readonly property bool podcastBrowser: radioBridge.source === "podcast"
    readonly property bool episodeBrowser: podcastBrowser && radioBridge.episodeFeed !== ""
    readonly property bool podcastPlaying: radioBridge.activeSource === "podcast"
    function formatTime(seconds) {
        if (seconds < 0) return "unavailable"
        var value = Math.floor(seconds)
        return String(Math.floor(value / 3600)).padStart(2, "0") + ":"
            + String(Math.floor(value / 60) % 60).padStart(2, "0") + ":"
            + String(value % 60).padStart(2, "0")
    }
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
            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
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
                model: [{key: "fm", title: "FM"}, {key: "dab", title: "DAB+"}, {key: "internet", title: "Internet"}, {key: "podcast", title: "Podcasts"}]
                delegate: TouchButton {
                    required property var modelData
                    width: 280; height: 60; text: modelData.title
                    accent: radioBridge.source === modelData.key
                    onClicked: radioBridge.setSource(modelData.key)
                }
            }
        }
        Item {
            x: 32; y: 186; width: 1216; height: 44; visible: root.episodeBrowser
            TouchButton { width: 144; height: 44; text: "Back"; onClicked: radioBridge.backToSubscriptions() }
            Text {
                x: 160; width: 650; height: 44; verticalAlignment: Text.AlignVCenter
                text: radioBridge.episodeFeedName + " · " + (radioBridge.episodePage + 1)
                    + "/" + Math.max(1, Math.ceil(radioBridge.episodeTotal / radioBridge.episodePageSize))
                color: "#edf2f5"; textFormat: Text.PlainText; elide: Text.ElideRight
            }
            TouchButton {
                x: 832; width: 176; height: 44; text: "Previous"
                enabled: !radioBridge.episodesLoading && radioBridge.episodePage > 0
                onClicked: radioBridge.episodePageTo(radioBridge.episodePage - 1)
            }
            TouchButton {
                x: 1024; width: 192; height: 44; text: "Next"
                enabled: !radioBridge.episodesLoading && (radioBridge.episodePage + 1) * radioBridge.episodePageSize < radioBridge.episodeTotal
                onClicked: radioBridge.episodePageTo(radioBridge.episodePage + 1)
            }
        }
        ListView {
            id: stations
            x: 32; y: root.episodeBrowser ? 238 : 198
            width: 1216; height: root.episodeBrowser ? 194 : 234; spacing: 12; clip: true
            model: root.podcastBrowser ? (root.episodeBrowser ? radioBridge.episodes : radioBridge.subscriptions) : radioBridge.stations
            delegate: TouchButton {
                required property var modelData
                width: stations.width; height: 76
                text: modelData.name + (modelData.detail ? " · " + modelData.detail : ""); accent: radioBridge.selectedId === modelData.id
                font.pixelSize: root.podcastBrowser ? 21 : 23
                enabled: radioBridge.state !== "connecting" && radioBridge.state !== "failed"
                onClicked: root.podcastBrowser && !root.episodeBrowser ? radioBridge.openPodcast(modelData.id) : radioBridge.play(modelData.id)
            }
            ScrollBar.vertical: ScrollBar {}
        }
        Text {
            x: 48; y: 275; width: 1184
            visible: radioBridge.state !== "connecting" && stations.count === 0
            text: root.episodeBrowser ? (radioBridge.episodesLoading ? "Loading saved episodes…"
                    : radioBridge.episodeError || "No saved episodes.")
                : radioBridge.catalogueError !== "" ? "Cannot read saved catalogue: " + radioBridge.catalogueError
                : root.podcastBrowser ? "No saved podcasts. Subscribe with radio-cli, then reopen this screen."
                : "No saved " + radioBridge.source.toUpperCase() + " stations. Use radio-cli to scan or save stations, then reopen this screen."
            textFormat: Text.PlainText
            color: "#aabcc9"; wrapMode: Text.WordWrap
        }
        Text { x: 32; y: 447; width: 1216; text: radioBridge.station; textFormat: Text.PlainText; color: "#edf2f5"; font.pixelSize: 28; elide: Text.ElideRight }
        Text { x: 32; y: 491; width: 1216; height: 60; text: radioBridge.broadcastText; textFormat: Text.PlainText; color: "#a3e4ca"; wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight }
        Text {
            x: 32; y: 552; width: 1216; height: 32; visible: root.podcastPlaying
            text: radioBridge.seekTarget >= 0 ? "Seeking: " + root.formatTime(radioBridge.seekTarget)
                : "Position (source estimate): " + root.formatTime(radioBridge.position)
            color: "#aabcc9"; textFormat: Text.PlainText
        }
        Text { x: 32; y: 588; width: 1216; height: 24; text: radioBridge.error; textFormat: Text.PlainText; color: "#ffbdad"; font.pixelSize: 18; elide: Text.ElideRight }
        TouchButton { x: 32; y: 620; width: root.podcastPlaying ? 144 : 336; height: 72; text: "Stop"; enabled: ["starting", "playing", "paused", "stopping"].indexOf(radioBridge.state) >= 0; onClicked: radioBridge.stop() }
        TouchButton {
            x: 188; y: 620; width: 160; height: 72; visible: root.podcastPlaying
            text: radioBridge.state === "paused" ? "Resume" : "Pause"
            enabled: radioBridge.canPause && !radioBridge.pausePending
            onClicked: radioBridge.togglePause()
        }
        TouchButton {
            x: 360; y: 620; width: 144; height: 72; text: "−15 s"; visible: root.podcastPlaying
            enabled: radioBridge.canSeek && !radioBridge.pausePending && (radioBridge.position >= 0 || radioBridge.seekTarget >= 0)
            onClicked: radioBridge.seekBy(-15)
        }
        TouchButton {
            x: 516; y: 620; width: 144; height: 72; text: "+15 s"; visible: root.podcastPlaying
            enabled: radioBridge.canSeek && !radioBridge.pausePending && (radioBridge.position >= 0 || radioBridge.seekTarget >= 0)
            onClicked: radioBridge.seekBy(15)
        }
        Text { x: 688; y: 612; font.pixelSize: 18; text: "Volume: " + Math.round(radioBridge.volume * 100) + "%"
            + (Math.abs(radioBridge.requestedVolume - radioBridge.volume) > 0.001
                ? " · requested " + Math.round(radioBridge.requestedVolume * 100) + "%" : ""); color: "#edf2f5" }
        Slider {
            x: 680; y: 643; width: 568; height: 48
            from: 0; to: 1; stepSize: 0.05; value: radioBridge.requestedVolume
            enabled: radioBridge.volumeControl
            onMoved: radioBridge.setVolume(value)
        }
    }
}
