#!/usr/bin/env python3
"""Display-only Qt Quick prototype. No receiver, audio, backend or user-data I/O."""
from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnose', action='store_true', help='Read environment facts without starting Qt')
    parser.add_argument('--windowed', action='store_true', help='Use a normal window for desktop testing')
    parser.add_argument('--platform', choices=['eglfs', 'wayland', 'xcb', 'offscreen'], help='Explicit Qt platform')
    parser.add_argument('--timeout', type=int, default=0, help='Automatically exit after this many seconds (0 disables)')
    parser.add_argument('--rotation', type=int, choices=[0, 90, 180, 270], default=0,
                        help='Rotate the Qt Quick scene for a physically mounted panel')
    parser.add_argument('--keyboard-test', action='store_true', help='Open the multilingual text-entry test')
    args = parser.parse_args()
    if args.diagnose:
        from check_environment import report
        import json
        print(json.dumps(report(), indent=2, ensure_ascii=False))
        return 0
    if args.timeout < 0 or args.timeout > 3600:
        parser.error('--timeout must be between 0 and 3600 seconds')
    try:
        from PySide6.QtCore import QTimer, QUrl, qVersion
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtQuickControls2 import QQuickStyle
    except (ImportError, OSError) as error:
        print(f'Qt is not ready: {error}\nRun python3 main.py --diagnose first.', file=sys.stderr)
        return 1

    argv = [sys.argv[0]]
    if args.platform:
        argv += ['-platform', args.platform]
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication(argv)
    app.setApplicationName('Radio display prototype')
    app.setOrganizationName('Radio')
    engine = QQmlApplicationEngine()
    if args.keyboard_test:
        from keyboard_editor import KeyboardEditor
        editor = KeyboardEditor(app)
        engine.rootContext().setContextProperty('keyboardEditor', editor)
    engine.setInitialProperties({'windowed': args.windowed, 'backendName': app.platformName(),
                                 'contentRotation': args.rotation})
    scene = 'KeyboardTest.qml' if args.keyboard_test else 'Main.qml'
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name(scene).resolve())))
    if not engine.rootObjects():
        return 1
    engine.quit.connect(app.quit)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    # Allow Python signal delivery even while Qt has no pending UI events.
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(100)
    if args.timeout:
        QTimer.singleShot(args.timeout * 1000, app.quit)
    print(f'Qt {qVersion()}; platform {app.platformName()}; display-only, no audio.', flush=True)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
