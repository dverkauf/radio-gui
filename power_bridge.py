"""Logo power menu: acknowledged playback stop, backlight standby, explicit shutdown."""
from pathlib import Path
import subprocess
import time
from PySide6.QtCore import QObject, Property, Signal, Slot, QProcess, QTimer

HELPER = Path('/usr/local/libexec/la-calma-power-helper.py')
COMMAND = ['/usr/bin/sudo', '-n', '/usr/bin/python3', '-I', str(HELPER)]


class PowerBridge(QObject):
    changed = Signal()

    def __init__(self, playback, workers, parent=None, *, platform='offscreen', command=None):
        super().__init__(parent)
        self._playback = playback
        self._workers = workers
        self._command = list(command or COMMAND)
        self._custom_command = command is not None
        self._enabled = self._custom_command or platform in ('eglfs', 'wayland', 'xcb')
        self._state = 'awake'
        self._message = ''
        self._action = ''
        self._job = ''
        self._output = b''
        self._closing = False
        self._was_asleep = False
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.MergedChannels)
        self._process.readyReadStandardOutput.connect(self._read)
        self._process.finished.connect(self._finished)
        self._process.errorOccurred.connect(self._error)
        self._poll = QTimer(self)
        self._poll.setInterval(50)
        self._poll.timeout.connect(self._check_stopped)
        self._deadline = QTimer(self)
        self._deadline.setSingleShot(True)
        self._deadline.timeout.connect(self._timeout)
        # Recover a backlight left off by an earlier crashed GUI, never in offscreen tests.
        if self._enabled and not self._custom_command and HELPER.is_file():
            QTimer.singleShot(0, self._restore_startup)

    busy = Property(bool, lambda self: self._state in ('stopping', 'entering', 'waking', 'powering-off'), notify=changed)
    sleeping = Property(bool, lambda self: self._state in ('entering', 'asleep', 'waking'), notify=changed)
    message = Property(str, lambda self: self._message, notify=changed)

    def _ready(self):
        if not self._enabled:
            self._message = 'Power controls are disabled in offscreen tests.'
        elif not self._custom_command and not HELPER.is_file():
            self._message = 'Run ./setup_power_controls once from SSH, then try again.'
        else:
            return True
        self.changed.emit()
        return False

    @Slot()
    def clearMessage(self):
        if not self.busy:
            self._message = ''
            self.changed.emit()

    @Slot()
    def standby(self):
        self._request('standby')

    @Slot()
    def poweroff(self):
        self._request('poweroff')

    def _request(self, action):
        if self._closing or self.busy or self.sleeping or not self._ready():
            return
        if any(worker.busy for worker in self._workers):
            self._message = 'Wait for scanning or saving to finish before turning off.'
            self.changed.emit()
            return
        self._action = action
        self._state = 'stopping'
        self._message = 'Stopping playback and releasing the receiver…'
        self._stop_by = time.monotonic() + 20
        self._playback.stop()  # Also cancels any queued station switch.
        self.changed.emit()
        self._poll.start()
        self._check_stopped()

    def _check_stopped(self):
        if self._state != 'stopping':
            self._poll.stop()
            return
        if self._playback.state in ('idle', 'stopped', 'completed'):
            self._poll.stop()
            self._run(self._action)
        elif self._playback.state == 'failed' or time.monotonic() >= self._stop_by:
            self._poll.stop()
            self._state = 'awake'
            self._message = 'Playback cleanup was not confirmed. Restart the GUI before trying again.'
            self.changed.emit()

    def _run(self, action):
        self._was_asleep = self._state == 'asleep'
        self._job = action
        self._output = b''
        self._state = {'standby': 'entering', 'wake': 'waking', 'poweroff': 'powering-off'}[action]
        self._message = {'standby': 'Entering standby…', 'wake': 'Waking display…',
                         'poweroff': 'Shutting down the Pi. Use its power button to start it again.'}[action]
        self.changed.emit()
        self._deadline.start(15000)
        self._process.start(self._command[0], self._command[1:] + [action])

    @Slot()
    def wake(self):
        if not self._closing and self._state == 'asleep' and self._ready():
            self._run('wake')

    def _restore_startup(self):
        if not self._closing and self._state == 'awake':
            self._run('wake')

    def _read(self):
        self._output = (self._output + bytes(self._process.readAllStandardOutput()))[-4096:]

    def _finished(self, code, status):
        if not self._job:
            return
        self._read()
        self._deadline.stop()
        action, self._job = self._job, ''
        if code == 0 and status == QProcess.NormalExit:
            self._state = {'standby': 'asleep', 'wake': 'awake', 'poweroff': 'powering-off'}[action]
            self._message = '' if action != 'poweroff' else 'Shutting down the Pi. Use its power button to start it again.'
        else:
            self._state = 'asleep' if action == 'wake' and self._was_asleep else 'awake'
            detail = self._output.decode('utf-8', errors='replace').strip()[-600:]
            self._message = 'Power control failed. ' + (detail or 'Check ./setup_power_controls from SSH.')
        self.changed.emit()

    def _error(self, error):
        if error == QProcess.FailedToStart and self._job:
            action, self._job = self._job, ''
            self._deadline.stop()
            self._state = 'asleep' if action == 'wake' and self._was_asleep else 'awake'
            self._message = 'Cannot start power helper. Run ./setup_power_controls from SSH.'
            self.changed.emit()

    def _timeout(self):
        action, self._job = self._job, ''
        self._process.kill()
        self._process.waitForFinished(1000)
        self._state = 'asleep' if action == 'wake' and self._was_asleep else 'awake'
        self._message = 'Power request timed out; its outcome is uncertain. Check from SSH.'
        self.changed.emit()

    def shutdown(self):
        self._closing = True
        self._poll.stop()
        self._deadline.stop()
        restore = self.sleeping and self._action != 'poweroff'
        if self._process.state() != QProcess.NotRunning:
            self._process.waitForFinished(2000)
        if restore:
            try:
                subprocess.run(self._command + ['wake'], timeout=6, check=True,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.SubprocessError):
                import sys
                print('Display restore failed; run ./wake_display from SSH.', file=sys.stderr)
