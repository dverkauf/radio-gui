import QtQuick
import QtQuick.Controls

Rectangle {
    id: menu
    readonly property var controls: typeof powerBridge === "undefined" ? null : powerBridge
    property bool opened: false
    property bool confirmShutdown: false
    function open() { confirmShutdown=false; if(menu.controls) menu.controls.clearMessage(); opened=true }
    anchors.fill: parent
    visible: opened
    color: "#bb000000"
    focus: visible
    onVisibleChanged: if(visible) forceActiveFocus()
    Keys.onPressed: function(event) {
        if(event.key===Qt.Key_Escape && menu.controls && !menu.controls.busy) {
            if(menu.confirmShutdown) menu.confirmShutdown=false
            else menu.opened=false
        }
        event.accepted=true
    }
    MouseArea { anchors.fill: parent }
    Connections { target:menu.controls; function onChanged() { if(menu.controls && menu.controls.sleeping) menu.opened=false } }
    Rectangle {
        anchors.centerIn: parent; width:880; height:420; radius:20; color:"#1c2934"
        border.color:"#405562"; border.width:2
        Text { x:32; y:28; text:menu.confirmShutdown?"Shut down the Pi?":"La Calma · Turn off"; font.pixelSize:30; font.bold:true; color:"#f3ddb1" }
        Text {
            x:32; y:94; width:816; height:190
            text:(menu.controls ? menu.controls.message : "") || (menu.confirmShutdown
                ? "The Pi will shut down completely. Touch will not restart it. Use the Pi’s physical power button to start it again."
                : "Standby stops playback and switches off the display. Touch the screen to wake it.\n\nShut down Pi switches the computer off completely.")
            textFormat:Text.PlainText; wrapMode:Text.WordWrap; font.pixelSize:23; color:"#edf2f5"
        }
        component Choice: Button {
            id: button
            property bool accent:false
            focusPolicy:Qt.NoFocus; font.pixelSize:24; width:256; height:88
            enabled:menu.controls !== null && !menu.controls.busy
            contentItem:Text {
                text:button.text; font:button.font; color:button.accent?"#102521":"#edf2f5"
                horizontalAlignment:Text.AlignHCenter; verticalAlignment:Text.AlignVCenter; wrapMode:Text.Wrap
                opacity:button.enabled?1:0.4
            }
            background:Rectangle { radius:14; color:button.down?"#63bfa7":button.accent?"#a3e4ca":"#283744" }
        }
        Choice { x:32; y:300; text:"Cancel"; onClicked:{if(menu.confirmShutdown){menu.confirmShutdown=false;menu.controls.clearMessage()}else menu.opened=false} }
        Choice { x:312; y:300; text:"Standby"; accent:true; visible:!menu.confirmShutdown; onClicked:menu.controls.standby() }
        Choice {
            x:592; y:300; text:menu.confirmShutdown?"Confirm shutdown":"Shut down Pi"
            onClicked:{if(menu.confirmShutdown)menu.controls.poweroff();else{menu.controls.clearMessage();menu.confirmShutdown=true}}
        }
    }
}
