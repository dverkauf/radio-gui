import QtQuick

Rectangle {
    id: screen
    readonly property var controls: typeof powerBridge === "undefined" ? null : powerBridge
    property int heldPoints: 0
    property bool heldKey: false
    readonly property bool held: heldPoints > 0 || heldKey
    anchors.fill: parent
    color: "black"
    visible: (screen.controls && screen.controls.sleeping) || held || releaseGuard.running
    focus: visible
    onVisibleChanged: if(visible) forceActiveFocus()
    Keys.onPressed: function(event) {screen.heldKey=true;if(screen.controls) screen.controls.wake();event.accepted=true}
    Keys.onReleased: function(event) {releaseGuard.restart();screen.heldKey=false;event.accepted=true}
    Timer { id:releaseGuard; interval:250 }
    Text {
        anchors.centerIn: parent; width:1000
        visible:screen.controls !== null && screen.controls.message !== ""
        text:screen.controls ? screen.controls.message : ""; textFormat:Text.PlainText; wrapMode:Text.WordWrap
        horizontalAlignment:Text.AlignHCenter; color:"#edf2f5"; font.pixelSize:24
    }
    // Keep the overlay through the entire wake touch and a short release guard.
    // That first tap cannot reach a station button beneath it, including over VNC.
    MouseArea { anchors.fill:parent; acceptedButtons:Qt.NoButton; onWheel:function(wheel){wheel.accepted=true} }
    MultiPointTouchArea {
        anchors.fill:parent
        mouseEnabled:true
        minimumTouchPoints:1; maximumTouchPoints:10
        onPressed:function(points){screen.heldPoints+=points.length;if(screen.controls) screen.controls.wake()}
        onReleased:function(points){releaseGuard.restart();screen.heldPoints=Math.max(0,screen.heldPoints-points.length)}
        onCanceled:function(points){releaseGuard.restart();screen.heldPoints=Math.max(0,screen.heldPoints-points.length)}
        onGestureStarted:function(gesture){gesture.grab()}
    }
}
