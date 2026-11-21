"""Native Qt editing checks, using an offscreen window and no real user data."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_QUICK_BACKEND'] = 'software'
import unittest
from PySide6.QtCore import QObject
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from keyboard_editor import KeyboardEditor

QML = b'''import QtQuick
import QtQuick.Controls
import QtQuick.Window
Window {
    width: 600; height: 300; visible: true
    TextField { objectName: "first"; width: 500; height: 60; focus: true }
    TextField { objectName: "second"; y: 100; width: 500; height: 60 }
}'''


class EditingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle('Basic')
        cls.app = QGuiApplication.instance() or QGuiApplication(['keyboard-edit-test'])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.engine = QQmlApplicationEngine()
        self.engine.loadData(QML)
        self.assertTrue(self.engine.rootObjects(), 'Qt test scene did not load')
        self.window = self.engine.rootObjects()[0]
        self.window.requestActivate()
        self.first = self.window.findChild(QObject, 'first')
        self.second = self.window.findChild(QObject, 'second')
        self.first.setProperty('focus', True)
        self.app.processEvents()
        self.assertTrue(self.first.property('activeFocus'))
        self.editor = KeyboardEditor()
        self.editor.setTarget(self.first)

    def tearDown(self):
        self.window.close()
        self.engine.deleteLater()
        self.app.processEvents()

    def test_unicode_commit_preserves_logical_text(self):
        for text in ['radio', 'größer', 'mañana', 'עברית', 'Ελληνικά']:
            self.assertTrue(self.editor.command('select_all'))
            self.assertTrue(self.editor.commit(text))
            self.assertEqual(self.first.property('text'), text)

    def test_selection_replacement_and_hebrew_backspace(self):
        self.editor.commit('abc')
        self.editor.command('select_all')
        self.editor.commit('אבג')
        self.assertEqual(self.first.property('text'), 'אבג')
        self.editor.command('backspace')
        self.assertEqual(self.first.property('text'), 'אב')

    def test_cursor_key_inserts_inside_latin_text(self):
        self.editor.commit('ab')
        self.editor.command('left')
        self.editor.commit('é')
        self.assertEqual(self.first.property('text'), 'aéb')

    def test_readonly_and_unfocused_fields_are_not_modified(self):
        self.first.setProperty('readOnly', True)
        self.assertFalse(self.editor.commit('x'))
        self.first.setProperty('readOnly', False)
        self.second.setProperty('focus', True)
        self.app.processEvents()
        self.assertFalse(self.editor.commit('x'))
        self.editor.setTarget(self.second)
        self.assertTrue(self.editor.commit('λ'))
        self.assertEqual(self.second.property('text'), 'λ')
        self.assertEqual(self.first.property('text'), '')


if __name__ == '__main__': unittest.main()
