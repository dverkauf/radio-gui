"""Receiver-aware GUI scan jobs, supervised separately from playback."""
import json
import os
import signal
from pathlib import Path
from PySide6.QtCore import Property, Signal, Slot, QProcess, QTimer
from discovery_bridge import DiscoveryBridge


class ScanBridge(DiscoveryBridge):
    scanChanged = Signal()

    def __init__(self, directory, playback, parent=None, *, process_command=None):
        command = process_command or ['php', str(Path(__file__).with_name('backend') / 'scan.php'), str(directory)]
        super().__init__(directory, parent, process_command=command)
        self.changed.connect(self.scanChanged.emit)
        self._playback = playback
        self._locations = []
        self._location = '__full_band__'
        self._stream = b''
        self._cancelling = False
        self._pending = None
        self._wait_ticks = 0
        self._wait_timer = QTimer(self)
        self._wait_timer.setInterval(50)
        self._wait_timer.timeout.connect(self._wait_for_receiver)
        self._cleanup_timer = QTimer(self)
        self._cleanup_timer.setSingleShot(True)
        self._cleanup_timer.timeout.connect(self._hard_stop)

    locations = Property('QVariantList', lambda self: [
        dict(p, label='Full Band III · location unknown' if p['name'] == '__full_band__' else p['name'])
        for p in self._locations], notify=scanChanged)
    location = Property(str, lambda self: self._location, notify=scanChanged)
    cancelling = Property(bool, lambda self: self._cancelling, notify=scanChanged)

    @Slot(str)
    def open(self, source):
        if self._busy or source not in ('fm', 'dab'):
            return
        self._source = source
        self._items = []
        self._start({'source': source, 'action': 'settings'})

    @Slot(str)
    def setLocation(self, name):
        if not self._busy and any(p['name'] == name for p in self._locations):
            self._location = name
            self.changed.emit()

    @Slot()
    def scan(self):
        if not self._busy:
            self._items = []
            self._start({'source': self._source, 'action': 'scan', 'location': self._location})

    @Slot(int)
    def identify(self, index):
        if not self._busy and self._source == 'fm' and 0 <= index < len(self._items):
            self._start({'source': 'fm', 'action': 'identify', 'key': self._items[index]['key']})

    def _start(self, request):
        self._stream = b''
        self._cancelling = False
        # Before using the receiver, stop the GUI's own RF session and wait for
        # its terminal acknowledgement, emitted only after library cleanup.
        needs_receiver = request['action'] == 'scan' or request['action'] == 'identify'
        if needs_receiver and self._playback.activeSource in ('fm', 'dab') and self._playback.state in ('starting','playing','paused','stopping'):
            self._busy = True
            self._saving = request['action'] == 'save'
            self._pending = request
            self._wait_ticks = 0
            self._message = 'Stopping FM/DAB playback and releasing receiver…'
            self._playback.stop()
            self._wait_timer.start()
            self.changed.emit()
            return
        self._launch(request)

    def _launch(self, request):
        super()._start(request)
        # Full Band III can take 38 * 45 seconds, plus per-block cleanup.
        self._timer.start(2100000 if request['action'] == 'scan' and self._source == 'dab' else 210000)
        self._message = ('Loading reception locations…' if request['action'] == 'settings' else
                         'Identifying FM station via RDS…' if request['action'] == 'identify' else
                         'Saving FM preset…' if request['action'] == 'save' and self._source == 'fm' else
                         'Saving DAB block…' if request['action'] == 'save' else 'Starting scan…')
        self.changed.emit()

    def _wait_for_receiver(self):
        self._wait_ticks += 1
        state = self._playback.state
        if state in ('idle','stopped','completed'):
            self._wait_timer.stop()
            request, self._pending = self._pending, None
            self._launch(request)
        elif state == 'failed' or self._wait_ticks >= 300:
            self._wait_timer.stop()
            self._pending = None
            self._busy = self._saving = False
            self._message = 'Receiver release was not confirmed. Check playback before scanning.'
            self.changed.emit()

    def _read(self):
        data = bytes(self._process.readAllStandardOutput())
        if not self._busy:
            return
        self._stream += data
        if len(self._stream) > 262144:
            self._abort('Scan response exceeded its limit.')
            return
        while b'\n' in self._stream:
            line, self._stream = self._stream.split(b'\n', 1)
            try:
                msg = json.loads(line)
                if not isinstance(msg, dict):
                    raise ValueError()
                if msg.get('type') == 'progress' and isinstance(msg.get('message'), str):
                    if not self._cancelling:
                        self._message = msg['message'][:1000]
                        self.changed.emit()
                else:
                    if self._output:
                        raise ValueError()
                    self._output = line
            except (ValueError, UnicodeError):
                self._abort('Invalid scan response.')
                return

    def _finished(self, code, status):
        self._cleanup_timer.stop()
        if self._cancelling:
            self._cancelling = False
            self._busy = self._saving = False
            self._message += (' Worker exited. Refresh presets before retrying a save.' if code == 0 else
                              ' Worker exited with a cancellation/error result. Check diagnostics if receiver remains busy.')
            self._process.readAllStandardOutput()
            self.changed.emit()
            return
        if not self._busy:
            return
        self._read()
        if self._cancelling or not self._busy:
            return
        try:
            msg = json.loads(self._output)
            if code == 0 and msg.get('type') == 'settings':
                plans = msg['locations']
                if not isinstance(plans, list) or len(plans) > 51 or any(not isinstance(p, dict)
                    or not isinstance(p.get('name'), str) or not isinstance(p.get('channels'), list) for p in plans):
                    raise ValueError()
                self._locations = plans
                self._location = msg['location']
                self._message = ('Scan for candidates, Identify to review RDS information, then Save preset.' if self._source == 'fm'
                    else 'Choose your reception location. Unknown location scans all Band III blocks (up to 32 minutes).')
            elif code == 0 and msg.get('type') == 'results':
                items = msg['items']
                if not isinstance(items, list) or len(items) > 40 or any(not isinstance(i, dict)
                    or any(not isinstance(i.get(k), str) for k in ('key','name','detail')) for i in items):
                    raise ValueError()
                self._items = items
                self._message = f'{len(items)} candidates/ensembles. Nothing saved yet.'
                if msg.get('warning'):
                    self._message += ' Some blocks failed or had no ensemble; see diagnostics.'
            elif code == 0 and msg.get('type') == 'identified':
                item = msg['item']
                if not isinstance(item, dict) or any(not isinstance(item.get(k), str) for k in ('key','name','detail')):
                    raise ValueError()
                if item['key'] != msg.get('key'):
                    raise ValueError()
                self._items = [item if row['key'] == item['key'] else row for row in self._items]
                self._message = msg['message']
            else:
                return super()._finished(code, status)
            self._timer.stop()
            self._busy = self._saving = False
            self.changed.emit()
        except (ValueError, KeyError, TypeError, UnicodeError):
            self._timer.stop()
            self._busy = self._saving = False
            self._message = 'Invalid scan response. Presets were not refreshed.'
            self.changed.emit()

    def _abort(self, message):
        if self._pending is not None:
            self._pending = None
            self._wait_timer.stop()
            self._busy = self._saving = False
            self._message = message
            self.changed.emit()
        elif self._process.state() == QProcess.NotRunning:
            super()._abort(message)
        elif not self._cancelling:
            self._cancelling = True
            self._timer.stop()
            self._message = message + ' Waiting for receiver cleanup…'
            self._cleanup_timer.start(8000)
            self._process.terminate()
            self.changed.emit()

    def _hard_stop(self):
        pid = self._process.processId()
        try:
            if pid and os.getpgid(pid) == pid:
                os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        # Whole group is isolated by scan.php before any scanner starts.
        super()._abort('Scan cleanup exceeded its deadline. Check receiver before retrying.')
        self._cancelling = False

    @Slot()
    def cancel(self):
        if self._busy:
            self._abort('Scan cancelled.')

    @Slot()
    def shutdown(self):
        self._wait_timer.stop()
        self._pending = None
        if self._process.state() != QProcess.NotRunning:
            self._abort('Closing scan.')
            if not self._process.waitForFinished(8000):
                self._hard_stop()
        self._cleanup_timer.stop()
        self._timer.stop()
