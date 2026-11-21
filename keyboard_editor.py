"""Deliver commits and editing keys to the explicitly focused application text field."""
from PySide6.QtCore import QObject, Slot, QCoreApplication, QEvent, Qt
from PySide6.QtGui import QInputMethodEvent, QKeyEvent
from shiboken6 import isValid
from keyboard_layouts import rows


class KeyboardEditor(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._target = None

    @Slot(QObject)
    def setTarget(self, target):
        self._target = target

    def _editable(self):
        target = self._target
        return (target is not None and isValid(target)
                and bool(target.property('activeFocus'))
                and not bool(target.property('readOnly'))
                and isinstance(target.property('text'), str)
                and isinstance(target.property('cursorPosition'), int))

    @Slot(str, bool, str, result='QVariantList')
    def rows(self, locale, shifted, mode):
        return rows(locale, shifted, mode)

    @Slot(str, result=bool)
    def commit(self, text):
        if not self._editable() or not text or len(text) > 16:
            return False
        event = QInputMethodEvent()
        event.setCommitString(text)
        QCoreApplication.sendEvent(self._target, event)
        return True

    @Slot(str, result=bool)
    def command(self, command):
        if not self._editable():
            return False
        keys = {'backspace': Qt.Key.Key_Backspace, 'left': Qt.Key.Key_Left,
                'right': Qt.Key.Key_Right, 'enter': Qt.Key.Key_Return,
                'select_all': Qt.Key.Key_A}
        if command not in keys:
            return False
        modifiers = Qt.KeyboardModifier.ControlModifier if command == 'select_all' else Qt.KeyboardModifier.NoModifier
        target = self._target
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QCoreApplication.sendEvent(target, QKeyEvent(kind, keys[command], modifiers))
        return True
