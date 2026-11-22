"""Isolated native Qt menu/wake input checks; fake power object only."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT=Path(__file__).resolve().parent


class PowerQmlTest(unittest.TestCase):
    def run_scene(self, scene, actions):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            qml=root/'test.qml'
            qml.write_text('import QtQuick\nimport "'+ROOT.as_uri()+'"\nRectangle {width:1280;height:720;property int hits:0;'+scene+'}\n')
            script=root/'check.py'
            script.write_text(textwrap.dedent('''
                import os
                from PySide6.QtCore import QObject,Property,Signal,Slot,QUrl,Qt,QPoint,QPointF,QEvent
                from PySide6.QtGui import QGuiApplication,QMouseEvent
                from PySide6.QtQuick import QQuickView
                import time
                class Input:
                    @staticmethod
                    def qWait(milliseconds):
                        deadline=time.monotonic()+milliseconds/1000
                        while time.monotonic()<deadline:
                            QGuiApplication.processEvents();time.sleep(.002)
                    @staticmethod
                    def send(view,kind,button,buttons,modifiers,pos):
                        event=QMouseEvent(kind,QPointF(pos),QPointF(pos),button,buttons,modifiers)
                        event.setTimestamp(int(time.monotonic()*1000))
                        QGuiApplication.sendEvent(view,event)
                        QGuiApplication.processEvents()
                    @staticmethod
                    def mousePress(view,button,modifiers,pos):
                        Input.send(view,QEvent.MouseButtonPress,button,button,modifiers,pos)
                    @staticmethod
                    def mouseRelease(view,button,modifiers,pos):
                        Input.send(view,QEvent.MouseButtonRelease,button,Qt.NoButton,modifiers,pos)
                    @staticmethod
                    def mouseClick(view,button,modifiers,pos):
                        Input.mousePress(view,button,modifiers,pos)
                        Input.mouseRelease(view,button,modifiers,pos)
                class Power(QObject):
                    changed=Signal()
                    def __init__(self):
                        super().__init__();self.asleep=False;self.standbys=0;self.shutdowns=0
                    busy=Property(bool,lambda self:False,notify=changed)
                    sleeping=Property(bool,lambda self:self.asleep,notify=changed)
                    message=Property(str,lambda self:'',notify=changed)
                    @Slot()
                    def clearMessage(self):pass
                    @Slot()
                    def standby(self):self.standbys+=1
                    @Slot()
                    def poweroff(self):self.shutdowns+=1
                    @Slot()
                    def wake(self):self.asleep=False;self.changed.emit()
                app=QGuiApplication([])
                power=Power();view=QQuickView()
                view.rootContext().setContextProperty('powerBridge',power)
            ''')+'\nview.setSource(QUrl.fromLocalFile('+repr(str(qml))+'))\n'
                +'assert view.status()==QQuickView.Ready, str(view.errors())\nview.show();Input.qWait(100)\nroot=view.rootObject()\n'+actions+'\nview.rootContext().setContextProperty(\"powerBridge\",None)\nInput.qWait(20)\nview.setSource(QUrl())\nview.close()\napp.processEvents()\n')
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
            result=subprocess.run([sys.executable,str(script)],env=env,text=True,capture_output=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertNotIn('TypeError:',result.stderr)
            self.assertNotIn('ReferenceError:',result.stderr)

    def test_shutdown_needs_confirmation_and_cancel_returns_to_options(self):
        self.run_scene('PowerMenu {opened:true}', '''
Input.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(920,494))
assert power.shutdowns==0
Input.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(360,494))
assert power.shutdowns==0
Input.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(640,494))
assert power.standbys==1
Input.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(920,494))
assert power.shutdowns==0
Input.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(920,494))
assert power.shutdowns==1
''')

    def test_first_wake_press_and_release_never_reach_station(self):
        self.run_scene('MouseArea {anchors.fill:parent;onClicked:parent.hits+=1}\nStandbyScreen {}', '''
power.asleep=True;power.changed.emit();Input.qWait(20)
Input.mousePress(view,Qt.LeftButton,Qt.NoModifier,QPoint(500,300))
Input.qWait(100)
assert root.property('hits')==0
Input.mouseRelease(view,Qt.LeftButton,Qt.NoModifier,QPoint(500,300))
Input.qWait(300)
assert root.property('hits')==0
Input.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(500,300))
assert root.property('hits')==1
''')
