"""Explicit preset management through an owned PHP storage worker."""
import json
from pathlib import Path
from PySide6.QtCore import Slot
from discovery_bridge import DiscoveryBridge


class PresetBridge(DiscoveryBridge):
    def __init__(self, directory, playback, parent=None, *, process_command=None):
        command = process_command or ['php', str(Path(__file__).with_name('backend') / 'presets.php'), str(directory)]
        super().__init__(directory, parent, process_command=command)
        self._playback = playback

    @Slot(str)
    def open(self, source):
        if self._busy or source not in ('fm','dab','internet','podcast'):
            return
        self._source = source
        self._items = []
        self._start({'action':'list','source':source})

    def _start(self, request):
        super()._start(request)
        self._saving = request['action'] == 'delete'
        self._message = 'Removing preset…' if self._saving else 'Loading presets…'
        self.changed.emit()

    @Slot(int, bool)
    def remove(self, index, remove_progress):
        if self._busy or not 0 <= index < len(self._items):
            return
        if self._playback.state not in ('idle','stopped','completed'):
            self._message = 'Stop playback before removing a preset or subscription.'
            self.changed.emit()
            return
        self._start({'action':'delete','source':self._source,'key':self._items[index]['key'],
                     'remove_progress':bool(remove_progress)})

    def _finished(self, code, status):
        if not self._busy:
            return
        self._read()
        if not self._busy:
            return
        self._timer.stop()
        self._busy = self._saving = False
        changed = False
        try:
            msg = json.loads(self._output)
            if code == 0 and msg.get('type') == 'presets':
                items = msg['items']
                if not isinstance(items,list) or len(items)>1000 or any(not isinstance(i,dict)
                    or any(not isinstance(i.get(k),str) for k in ('key','name','detail')) for i in items):
                    raise ValueError()
                self._items = items
                self._message = 'Choose Delete/Unsubscribe, then confirm. Everyday station taps still start playback.'
            elif code == 0 and msg.get('type') == 'deleted' and isinstance(msg.get('key'),str):
                self._items = [i for i in self._items if i['key'] != msg['key']]
                self._message = 'Removed: ' + str(msg.get('name','preset'))
                changed = True
            elif msg.get('type') == 'error' and isinstance(msg.get('message'),str):
                self._message = msg['message']
            else:
                raise ValueError()
        except (ValueError,KeyError,TypeError,UnicodeError):
            self._message = 'Invalid preset response. Reopen Manage presets to check the saved state.'
        self.changed.emit()
        if changed:
            self.saved.emit()
