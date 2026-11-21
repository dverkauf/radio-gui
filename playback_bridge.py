"""Qt adapter for one owned PHP process; no radio implementation lives here."""
from pathlib import Path
import json

from PySide6.QtCore import QObject, Property, Signal, Slot, QProcess, QTimer


class PlaybackBridge(QObject):
    changed = Signal()
    volumeTargetChanged = Signal()
    catalogueChanged = Signal()
    episodesChanged = Signal()

    def __init__(self, directory, parent=None, *, process_command=None):
        super().__init__(parent)
        self._subscriptions = []
        self._episodes = []
        self._episode_feed = ''
        self._episode_page = 0
        self._episode_total = 0
        self._episode_page_size = 40
        self._episodes_loading = False
        self._episode_error = ''
        self._browse_request = 0
        self._pending_entry = None
        self._position = -1.0
        self._duration = -1.0
        self._can_pause = False
        self._can_seek = False
        self._pause_pending = False
        self._pause_target = ''
        self._seek_target = -1.0
        self._seek_sequence = 0
        self._stations = []
        self._source = 'internet'
        self._active_source = ''
        self._catalogue_errors = {}
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
        command = process_command or ['php', str(Path(__file__).with_name('backend') / 'radio.php'), str(directory)]
        self._process.start(command[0], command[1:])
        self._timer.start()

    stations = Property('QVariantList', lambda self: [s for s in self._stations if s['source'] == self._source], notify=catalogueChanged)
    source = Property(str, lambda self: self._source, notify=catalogueChanged)
    activeSource = Property(str, lambda self: self._active_source, notify=changed)
    catalogueError = Property(str, lambda self: self._catalogue_errors.get(self._source, ''), notify=catalogueChanged)

    @Slot(str)
    def setSource(self, source):
        if source in ('fm', 'dab', 'internet', 'podcast') and source != self._source:
            self._source = source
            self.catalogueChanged.emit()
            self.changed.emit()

    subscriptions = Property('QVariantList', lambda self: self._subscriptions, notify=catalogueChanged)
    episodes = Property('QVariantList', lambda self: self._episodes, notify=episodesChanged)
    episodeFeed = Property(str, lambda self: self._episode_feed, notify=episodesChanged)
    episodeFeedName = Property(str, lambda self: next((s['name'] for s in self._subscriptions if s['id'] == self._episode_feed), ''), notify=episodesChanged)
    episodePage = Property(int, lambda self: self._episode_page, notify=episodesChanged)
    episodeTotal = Property(int, lambda self: self._episode_total, notify=episodesChanged)
    episodePageSize = Property(int, lambda self: self._episode_page_size, notify=episodesChanged)
    episodesLoading = Property(bool, lambda self: self._episodes_loading, notify=episodesChanged)
    episodeError = Property(str, lambda self: self._episode_error, notify=episodesChanged)
    position = Property(float, lambda self: self._position, notify=changed)
    duration = Property(float, lambda self: self._duration, notify=changed)
    seekTarget = Property(float, lambda self: self._seek_target, notify=changed)
    canPause = Property(bool, lambda self: self._can_pause and self._state in ('playing', 'paused'), notify=changed)
    canSeek = Property(bool, lambda self: self._can_seek and self._state in ('playing', 'paused'), notify=changed)
    pausePending = Property(bool, lambda self: self._pause_pending, notify=changed)

    @Slot(str)
    def openPodcast(self, feed):
        if not self._closing and any(s['id'] == feed for s in self._subscriptions):
            self._request_episodes(feed, 0)

    @Slot()
    def backToSubscriptions(self):
        self._browse_request += 1
        self._episode_feed = ''
        self._episodes = []
        self._episodes_loading = False
        self._episode_error = ''
        self.episodesChanged.emit()
        self.changed.emit()

    @Slot(int)
    def episodePageTo(self, page):
        if self._episode_feed and 0 <= page <= max(0, (self._episode_total - 1) // self._episode_page_size):
            self._request_episodes(self._episode_feed, page)

    def _request_episodes(self, feed, page):
        self._browse_request += 1
        if self._episode_feed != feed:
            self._episode_total = 0
        self._episode_feed = feed
        self._episode_page = page
        self._episodes = []
        self._episodes_loading = True
        self._episode_error = ''
        self.episodesChanged.emit()
        self.changed.emit()
        self._send({'command': 'episodes', 'feed': feed, 'page': page, 'request_id': self._browse_request})

    def _clear_timeline(self):
        self._can_pause = self._can_seek = self._pause_pending = False
        self._pause_target = ''
        self._position = self._duration = self._seek_target = -1.0
        self._seek_sequence = 0

    @Slot()
    def togglePause(self):
        if self.canPause and not self._pause_pending:
            self._pause_pending = True
            self._pause_target = 'playing' if self._state == 'paused' else 'paused'
            self.changed.emit()
            self._send({'command': 'resume' if self._state == 'paused' else 'pause'})

    @Slot(float)
    def seekBy(self, delta):
        import math
        base = self._seek_target if self._seek_target >= 0 else self._position
        if not self.canSeek or self._pause_pending or not math.isfinite(delta) or base < 0:
            return
        target = max(0.0, base + delta)
        if self._duration >= 0:
            target = min(target, self._duration)
        self._seek_target = target
        self._seek_sequence += 1
        self.changed.emit()
        self._send({'command': 'seek', 'seconds': target, 'request_id': self._seek_sequence})

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
                    if any(s.get('source', 'internet') not in ('fm', 'dab', 'internet', 'podcast') for s in stations):
                        raise ValueError('Invalid station source')
                    if len({s['id'] for s in stations}) != len(stations):
                        raise ValueError('Duplicate station identity')
                    errors = message.get('catalogue_errors', {})
                    if not isinstance(errors, dict) or any(not isinstance(v, str) for v in errors.values()):
                        raise ValueError('Invalid catalogue diagnostics')
                    subscriptions = message.get('subscriptions', [])
                    if not isinstance(subscriptions, list) or any(not isinstance(s, dict)
                        or not isinstance(s.get('id'), str) or not isinstance(s.get('name'), str) for s in subscriptions):
                        raise ValueError('Invalid podcast subscriptions')
                    self._subscriptions = subscriptions
                    self._catalogue_errors = errors
                    self._stations = [dict(s, source=s.get('source', 'internet')) for s in stations]
                    self._volume = float(message['volume'])
                    self._initial_volume = self._volume
                    self._requested_volume = self._volume
                    self.volumeTargetChanged.emit()
                    self._state = 'idle'
                    self.catalogueChanged.emit()
                elif kind == 'episodes':
                    if message.get('request_id') != self._browse_request or message.get('feed') != self._episode_feed:
                        continue  # A late page must not replace the current browser.
                    items = message.get('items')
                    if not isinstance(items, list) or len(items) > 40 or any(not isinstance(s, dict)
                        or not isinstance(s.get('id'), str) or not isinstance(s.get('name'), str)
                        or s.get('source') != 'podcast' for s in items):
                        raise ValueError('Invalid podcast page')
                    page, total, size = message['page'], message['total'], message['page_size']
                    if type(page) is not int or type(total) is not int or size != 40 or page < 0 or total < 0:
                        raise ValueError('Invalid podcast page bounds')
                    self._episodes = items
                    self._episode_page, self._episode_total, self._episode_page_size = page, total, size
                    self._episodes_loading = False
                    self.episodesChanged.emit()
                elif kind == 'timeline':
                    import math
                    values = [message.get('position'), message.get('duration')]
                    if any(v is not None and (type(v) not in (int, float) or not math.isfinite(v) or v < 0) for v in values):
                        raise ValueError('Invalid media position')
                    self._position, self._duration = [float(v) if v is not None else -1.0 for v in values]
                    self._can_pause = bool(message.get('can_pause'))
                    self._can_seek = bool(message.get('can_seek'))
                    if self._seek_target >= 0 and self._position >= 0 and message.get('seek_request') == self._seek_sequence:
                        self._seek_target = -1.0
                elif kind == 'state':
                    if message.get('state') not in ('starting', 'playing', 'paused', 'stopping', 'stopped', 'completed', 'failed'):
                        raise ValueError('Invalid playback state')
                    reported = message['state']
                    if reported == self._pause_target:
                        self._pause_pending = False
                        self._pause_target = ''
                    if reported in ('stopped', 'completed', 'failed'):
                        self._clear_timeline()
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
                    self._volume_control = bool(message.get('volume_control')) and self._state in ('playing', 'paused')
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
                elif kind in ('error', 'request_error', 'session_error'):
                    if kind == 'request_error' and message.get('command') == 'episodes':
                        if message.get('request_id') == self._browse_request:
                            self._episode_error = str(message.get('message', 'Cannot read episodes.'))
                            self._episodes_loading = False
                            self.episodesChanged.emit()
                        self.changed.emit()
                        continue
                    self._error = str(message.get('message', 'Playback failed.'))
                    if kind == 'request_error':
                        if message.get('command') in ('pause', 'resume'):
                            self._pause_pending = False
                            self._pause_target = ''
                        if message.get('command') == 'seek' and message.get('request_id') == self._seek_sequence:
                            self._seek_target = -1.0
                        if message.get('command') == 'play':
                            self._active_id = None
                            self._pending_id = None
                            self._pending_entry = None
                            self._selected_id = ''
                            self._state = 'stopped'
                            self._clear_timeline()
                    if kind == 'session_error':
                        self._pending_id = None
                        self._selected_id = ''
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
        entry = next((s for s in self._stations + self._episodes if s['id'] == identifier), None)
        if entry is None:
            return
        if identifier == self._active_id and not self._stop_requested:
            return  # A repeated tap must not restart the current stream.
        self._pending_id = identifier
        self._pending_entry = dict(entry)
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
        selected = self._pending_entry
        self._pending_id = None
        self._pending_entry = None
        self._active_id = identifier
        self._error = ''
        self._station = selected['name']
        self._active_source = selected['source']
        self._text = ''
        self._clear_timeline()
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
        if self._process.state() != QProcess.NotRunning and not self._process.waitForFinished(10000):
            import sys
            print('PHP cleanup exceeded ten seconds; inspect owned playback processes.', file=sys.stderr)
