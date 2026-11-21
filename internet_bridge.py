"""Qt adapter for one owned PHP process; no radio implementation lives here."""
from pathlib import Path
import json

from PySide6.QtCore import QObject, Property, Signal, Slot, QProcess, QTimer


class InternetBridge(QObject):
    changed = Signal()
    volumeTargetChanged = Signal()

    def __init__(self, directory, parent=None, *, process_command=None):
        super().__init__(parent)
        self._stations = []
        self._active_id = None
        self._pending_id = None
        self._selected_id = ''
        self._stop_requested = False
        self._state = 'connecting'
        self._station = ''
        self._text = ''
        self._error = ''
        self._volume = 0.1
        self._initial_volume = 0.1
        self._requested_volume = 0.1
        self._volume_control = False
        self._buffer = b''
        self._diagnostics = b''
        self._closing = False
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.readyReadStandardError.connect(self._read_error)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._process_error)
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(lambda: self._send({'command': 'ping'}))
        command = process_command or ['php', str(Path(__file__).with_name('backend') / 'internet.php'), str(directory)]
        self._process.start(command[0], command[1:])
        self._timer.start()

    stations = Property('QVariantList', lambda self: self._stations, notify=changed)
    selectedId = Property(str, lambda self: self._selected_id, notify=changed)
    state = Property(str, lambda self: self._state, notify=changed)
    station = Property(str, lambda self: self._station, notify=changed)
    broadcastText = Property(str, lambda self: self._text, notify=changed)
    error = Property(str, lambda self: self._error, notify=changed)
    volume = Property(float, lambda self: self._volume, notify=changed)
    requestedVolume = Property(float, lambda self: self._requested_volume, notify=volumeTargetChanged)
    volumeControl = Property(bool, lambda self: self._volume_control, notify=changed)

    def _send(self, message):
        if self._process.state() != QProcess.Running:
            return
        if self._process.bytesToWrite() > 65536:
            self._fail('Playback connection is not accepting commands.')
            return
        self._process.write((json.dumps(message, ensure_ascii=False) + '\n').encode())

    def _read_error(self):
        self._diagnostics = (self._diagnostics + bytes(self._process.readAllStandardError()))[-8192:]

    def _fail(self, message):
        self._pending_id = None
        self._selected_id = ''
        self._error = message
        self._state = 'failed'
        self._volume_control = False
        self.changed.emit()
        self._timer.stop()
        # Closing stdin makes the backend perform its normal session cleanup.
        self._process.closeWriteChannel()

    def _read(self):
        self._buffer += bytes(self._process.readAllStandardOutput())
        if len(self._buffer) > 1048576:
            self._fail('Playback response exceeded its limit.')
            self._buffer = b''
            return
        while b'\n' in self._buffer:
            line, self._buffer = self._buffer.split(b'\n', 1)
            try:
                message = json.loads(line)
                if not isinstance(message, dict):
                    raise ValueError('Expected a protocol object')
                kind = message.get('type')
                if kind == 'ready':
                    if message.get('protocol') != 1 or not isinstance(message.get('stations'), list):
                        raise ValueError('Unsupported playback protocol')
                    stations = message['stations']
                    if any(not isinstance(s, dict) or not isinstance(s.get('id'), str)
                           or not isinstance(s.get('name'), str) for s in stations):
                        raise ValueError('Invalid saved station list')
                    self._stations = stations
                    self._volume = float(message['volume'])
                    self._initial_volume = self._volume
                    self._requested_volume = self._volume
                    self.volumeTargetChanged.emit()
                    self._state = 'idle'
                elif kind == 'state':
                    if message.get('state') not in ('starting', 'playing', 'paused', 'stopping', 'stopped', 'completed', 'failed'):
                        raise ValueError('Invalid playback state')
                    reported = message['state']
                    if reported in ('stopped', 'completed', 'failed'):
                        self._active_id = None
                        self._stop_requested = False
                        if reported == 'failed':
                            self._pending_id = None
                        self._selected_id = self._pending_id or ''
                        self._state = reported
                        if self._pending_id is not None:
                            # Finish consuming the old session's buffered messages first.
                            QTimer.singleShot(0, self._start_pending)
                    else:
                        self._state = 'stopping' if self._stop_requested else reported
                    self._volume_control = bool(message.get('volume_control')) and self._state == 'playing'
                elif kind == 'metadata':
                    if not isinstance(message.get('text'), str):
                        raise ValueError('Invalid metadata')
                    if message.get('kind') == 'station_identity':
                        self._station = message['text']
                    elif message.get('kind') == 'broadcast_text':
                        self._text = message['text']
                elif kind == 'volume':
                    value = float(message['value'])
                    if not 0 <= value <= 1:
                        raise ValueError('Invalid volume')
                    self._volume = value
                elif kind in ('error', 'request_error'):
                    self._error = str(message.get('message', 'Playback failed.'))
                    if kind == 'error':
                        self._pending_id = None
                        self._selected_id = ''
                        self._state = 'failed'
                        self._volume_control = False
                else:
                    raise ValueError('Unknown response')
                self.changed.emit()
            except (ValueError, KeyError, TypeError, UnicodeError):
                self._fail('Invalid response from playback process.')
                return

    def _process_error(self, error):
        if error == QProcess.FailedToStart:
            self._fail('Cannot start PHP. Install PHP 8.4 or later and Composer dependencies.')

    def _finished(self, code, status):
        self._read()
        self._read_error()
        self._timer.stop()
        if not self._closing:
            self._pending_id = None
            self._selected_id = ''
            if not self._error:
                self._error = self._diagnostics.decode('utf-8', errors='replace').strip() or 'Playback process disconnected.'
            self._state = 'failed'
            self._volume_control = False
            self.changed.emit()

    @Slot(str)
    def play(self, identifier):
        if self._closing or self._state in ('connecting', 'failed'):
            return
        if not any(s['id'] == identifier for s in self._stations):
            return
        if identifier == self._active_id and not self._stop_requested:
            return  # A repeated tap must not restart the current stream.
        self._pending_id = identifier
        self._selected_id = identifier
        if self._state in ('idle', 'stopped', 'completed'):
            self._start_pending()
        elif not self._stop_requested:
            self._request_stop()
        else:
            self.changed.emit()  # Latest tap replaces the queued station.

    def _start_pending(self):
        if self._closing or self._pending_id is None or self._state not in ('idle', 'stopped', 'completed'):
            return
        identifier = self._pending_id
        self._pending_id = None
        self._active_id = identifier
        self._error = ''
        self._station = next(s['name'] for s in self._stations if s['id'] == identifier)
        self._text = ''
        self._state = 'starting'
        self._requested_volume = self._initial_volume
        self.volumeTargetChanged.emit()
        self._volume_control = False
        self.changed.emit()
        self._send({'command': 'play', 'id': identifier})

    def _request_stop(self):
        self._stop_requested = True
        self._state = 'stopping'
        self._volume_control = False
        self.changed.emit()
        self._send({'command': 'stop'})

    @Slot()
    def stop(self):
        self._pending_id = None
        self._selected_id = ''
        if self._state in ('starting', 'playing', 'paused') and not self._stop_requested:
            self._request_stop()
        else:
            self.changed.emit()

    @Slot(float)
    def setVolume(self, value):
        if self._volume_control and 0 <= value <= 1:
            self._requested_volume = value
            self.volumeTargetChanged.emit()
            self._send({'command': 'volume', 'value': value})

    @Slot()
    def shutdown(self):
        if self._closing:
            return
        self._closing = True
        self._pending_id = None
        self._timer.stop()
        self._send({'command': 'quit'})
        self._process.closeWriteChannel()
        # On window exit only: allow core's documented bounded cleanup to finish.
        if self._process.state() != QProcess.NotRunning and not self._process.waitForFinished(8000):
            import sys
            print('PHP cleanup exceeded eight seconds; inspect owned playback processes.', file=sys.stderr)
