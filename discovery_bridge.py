"""Owned, bounded discovery jobs, isolated from the playback process."""
import json
from pathlib import Path
from PySide6.QtCore import QObject, Property, Signal, Slot, QProcess, QTimer


class DiscoveryBridge(QObject):
    changed = Signal()
    saved = Signal()

    def __init__(self, directory, parent=None, *, process_command=None):
        super().__init__(parent)
        self._command = process_command or ['php', str(Path(__file__).with_name('backend') / 'discovery.php'), str(directory)]
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.SeparateChannels)
        self._process.started.connect(self._started)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.readyReadStandardError.connect(self._read_error)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._error)
        self._request = b''
        self._items = []
        self._source = 'internet'
        self._busy = False
        self._saving = False
        self._message = ''
        self._output = b''
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._timeout)

    items = Property('QVariantList', lambda self: self._items, notify=changed)
    source = Property(str, lambda self: self._source, notify=changed)
    busy = Property(bool, lambda self: self._busy, notify=changed)
    saving = Property(bool, lambda self: self._saving, notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)

    @Slot(str)
    def open(self, source):
        if source not in ('internet', 'podcast') or self._saving:
            return
        self.cancel()
        self._source = source
        self._items = []
        self._message = 'Search by name. Results are saved only when you choose Save or Subscribe.'
        self.changed.emit()

    @Slot(str)
    def search(self, query):
        if self._busy:
            return
        if not query.strip() or len(query.encode('utf-8')) > 200:
            self._message = 'Enter a name of at most 200 UTF-8 bytes.'
            self.changed.emit()
            return
        self._items = []
        self._start({'action': 'search', 'source': self._source, 'query': query})

    @Slot(int)
    def save(self, index):
        if not self._busy and 0 <= index < len(self._items):
            self._start({'action': 'save', 'source': self._source, 'key': self._items[index]['key']})

    def _start(self, request):
        self._saving = request['action'] == 'save'
        self._busy = True
        self._message = 'Saving…' if self._saving else 'Searching…'
        self._output = b''
        self._request = json.dumps(request, ensure_ascii=False).encode()
        self._timer.start(30000)
        self._process.start(self._command[0], self._command[1:])
        self.changed.emit()

    def _started(self):
        if self._busy:
            self._process.write(self._request)
            self._process.closeWriteChannel()

    def _read_error(self):
        self._process.readAllStandardError()

    def _read(self):
        data = bytes(self._process.readAllStandardOutput())
        if not self._busy:
            return
        self._output += data
        if len(self._output) > 262144:
            self._abort('Discovery response exceeded its limit.')

    def _error(self, error):
        if self._busy and error == QProcess.FailedToStart:
            self._abort('Cannot start PHP discovery. Check PHP and Composer installation.')

    def _finished(self, code, status):
        if not self._busy:
            return
        self._read()
        if not self._busy:
            return
        self._timer.stop()
        self._busy = False
        was_saving = self._saving
        self._saving = False
        success = False
        try:
            response = json.loads(self._output)
            if not isinstance(response, dict):
                raise ValueError()
            kind = response.get('type')
            if kind == 'error' and isinstance(response.get('message'), str):
                self._message = response['message'][:1000]
            elif code == 0 and kind == 'results' and not was_saving:
                items = response['items']
                if not isinstance(items, list) or len(items) > 20 or any(
                    not isinstance(i, dict) or any(not isinstance(i.get(k), str) for k in ('key', 'name', 'detail'))
                    or not i['key'] or len(i['key']) > 2048 for i in items
                ):
                    raise ValueError()
                self._items = items
                self._message = f'{len(items)} results. Choose Save or Subscribe to add a preset.' if items else 'No results. Try another name.'
            elif code == 0 and kind == 'saved' and was_saving and isinstance(response.get('name'), str):
                self._message = 'Saved: ' + response['name'] + '. Return to Presets to play.'
                success = True
            else:
                raise ValueError()
        except (ValueError, KeyError, TypeError, UnicodeError):
            self._message = 'Invalid discovery response.'
            if was_saving:
                self._message += ' A save may have completed; refresh Presets before retrying.'
        self.changed.emit()
        if success:
            self.saved.emit()

    def _timeout(self):
        self._abort('Discovery timed out.' + (' A save may have completed; refresh Presets before retrying.' if self._saving else ' Try again.'))

    def _abort(self, message):
        self._timer.stop()
        # Mark inactive before kill/wait, which can synchronously deliver finished.
        self._busy = self._saving = False
        self._message = message
        if self._process.state() != QProcess.NotRunning:
            self._process.kill()
            self._process.waitForFinished(1000)
        self._process.readAllStandardOutput()
        self._process.readAllStandardError()
        self._output = b''
        self.changed.emit()

    @Slot()
    def cancel(self):
        if self._busy and not self._saving:
            self._abort('Search cancelled.')

    @Slot()
    def shutdown(self):
        if self._busy or self._process.state() != QProcess.NotRunning:
            self._abort('Discovery closed.')
