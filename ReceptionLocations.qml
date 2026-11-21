import QtQuick
import QtQuick.Controls

Rectangle {
    id: panel
    property bool opened: false
    property string original: ""
    property var blocks: []
    property bool confirmDelete: false
    property string pendingAction: ""
    readonly property var allBlocks: ["5A","5B","5C","5D","6A","6B","6C","6D","7A","7B","7C","7D","8A","8B","8C","8D","9A","9B","9C","9D","10A","10B","10C","10D","11A","11B","11C","11D","12A","12B","12C","12D","13A","13B","13C","13D","13E","13F"]
    visible: opened; color: "#111922"
    function newPlan() { original=""; name.text=""; blocks=[]; confirmDelete=false; keyboard.opened=false }
    function open() { newPlan(); locationBridge.open(); opened=true }
    MouseArea { anchors.fill: parent }
    component Action: Button {
        id: button
        property bool accent: false
        focusPolicy: Qt.NoFocus; font.pixelSize: 21
        contentItem: Text {
            text: button.text; font: button.font; textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: button.accent ? "#102521" : "#edf2f5"
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            opacity: button.enabled ? 1 : 0.4
        }
        background: Rectangle { radius: 10; color: button.down ? "#63bfa7" : button.accent ? "#a3e4ca" : "#283744" }
    }
    Text { x:32; y:22; text:"Reception locations"; color:"#f3ddb1"; font.pixelSize:30; font.bold:true }
    Action {
        x:1008; y:16; width:240; height:60; text:"Back to Scan"; enabled:!locationBridge.busy
        onClicked: { keyboard.opened=false; panel.opened=false; scanBridge.refreshLocations() }
    }
    ComboBox {
        id: plans
        x:32; y:94; width:660; height:58; model:locationBridge.items; textRole:"name"; currentIndex:-1
        enabled:!locationBridge.busy
        displayText: currentIndex < 0 ? "Choose a saved location to edit" : currentText
        onActivated: {
            var row=locationBridge.items[currentIndex]
            panel.original=row.key; name.text=row.name; panel.blocks=row.channels.slice()
            panel.confirmDelete=false; keyboard.opened=false
        }
        font.pixelSize:22
    }
    Action { x:708; y:94; width:220; height:58; text:"New location"; enabled:!locationBridge.busy; onClicked:{ plans.currentIndex=-1; panel.newPlan() } }
    Action { x:944; y:94; width:304; height:58; text:"Use full Band III"; enabled:!locationBridge.busy; onClicked:{panel.pendingAction="";locationBridge.selectPlan("__full_band__")} }
    Text { x:32; y:164; width:1216; text:"Selected for scanning: " + (locationBridge.selected === "__full_band__" ? "Full Band III" : locationBridge.selected); textFormat:Text.PlainText; color:"#aabcc9"; font.pixelSize:19 }
    TextField {
        id:name; objectName:"receptionLocationName"
        x:32; y:198; width:720; height:58; color:"#edf2f5"; font.pixelSize:25; maximumLength:100
        placeholderText:"Location name · Hannover · Palekastro"
        readOnly:panel.original!=="" || locationBridge.busy
        background:Rectangle { radius:10; color:"#253640"; border.color:name.activeFocus?"#a3e4ca":"#405562"; border.width:2 }
        onActiveFocusChanged:if(activeFocus && !readOnly){keyboardEditor.setTarget(name);keyboard.opened=true}
        onAccepted:keyboard.opened=false
        TapHandler { onTapped:if(!name.readOnly){name.forceActiveFocus();keyboardEditor.setTarget(name);keyboard.opened=true} }
    }
    Action { x:768; y:198; width:224; height:58; text:"Select all blocks"; enabled:!locationBridge.busy; onClicked:{panel.blocks=panel.allBlocks.slice();keyboard.opened=false} }
    Action { x:1008; y:198; width:240; height:58; text:"Clear blocks"; enabled:!locationBridge.busy; onClicked:{panel.blocks=[];keyboard.opened=false} }
    Grid {
        x:32; y:274; columns:10; spacing:8; visible:!keyboard.opened
        Repeater {
            model:panel.allBlocks
            Action {
                required property string modelData
                width:114; height:52; text:modelData; accent:panel.blocks.indexOf(modelData)>=0
                enabled:!locationBridge.busy
                onClicked:{var selected=panel.blocks.slice();var i=selected.indexOf(modelData);if(i>=0)selected.splice(i,1);else selected.push(modelData);panel.blocks=selected;panel.confirmDelete=false}
            }
        }
    }
    Text {
        x:32; y:516; width:1216; height:60; visible:!keyboard.opened
        text:panel.confirmDelete ? "Delete location plan “"+panel.original+"”? Saved stations will be kept. Tap Confirm delete or Cancel."
             : locationBridge.message
        textFormat:Text.PlainText; wrapMode:Text.WordWrap; color:"#a3e4ca"; font.pixelSize:19
    }
    Row {
        x:32; y:606; spacing:16; visible:!keyboard.opened
        Action { width:280; height:72; text:"Save and select"; enabled:!locationBridge.busy && name.text.trim().length>0 && panel.blocks.length>0; onClicked:{panel.pendingAction="save";locationBridge.savePlan(name.text,panel.blocks,panel.original)} }
        Action { width:280; height:72; text:"Use saved location"; enabled:!locationBridge.busy && panel.original!==""; onClicked:{panel.pendingAction="";locationBridge.selectPlan(panel.original)} }
        Action { width:280; height:72; text:panel.confirmDelete?"Confirm delete":"Delete location"; enabled:!locationBridge.busy && panel.original!==""; onClicked:{if(panel.confirmDelete){panel.pendingAction="delete";locationBridge.deletePlan(panel.original)}else panel.confirmDelete=true} }
        Action { width:200; height:72; text:"Cancel"; visible:panel.confirmDelete; enabled:!locationBridge.busy; onClicked:panel.confirmDelete=false }
    }
    Connections {
        target: locationBridge
        function onSaved() {
            if (panel.pendingAction === "save") panel.original=name.text.trim()
            if (panel.pendingAction === "delete") { panel.newPlan(); plans.currentIndex=-1 }
            panel.pendingAction=""; panel.confirmDelete=false
        }
    }
    KeyboardPanel { id:keyboard; x:16; y:360; width:1248; editor:keyboardEditor }
}
