#!/usr/bin/env python3
"""Qt Quick radio UI with supervised PHP radio playback."""
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
    parser.add_argument('--radio', action='store_true', help='Browse and play saved radio stations and podcast episodes')
    parser.add_argument('--internet', action='store_true', help='Play saved internet stations through the PHP library')
    parser.add_argument('--config-dir', type=Path, default=Path.home() / '.radio', help='Existing shared radio data directory')
    parser.add_argument('--ready-file', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if (args.internet or args.radio) and args.keyboard_test:
        parser.error('Playback and --keyboard-test cannot be combined')
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
    app.setApplicationName('La Calma Radio')
    app.setOrganizationName('Radio')
    engine = QQmlApplicationEngine()
    if args.keyboard_test or args.radio:
        from keyboard_editor import KeyboardEditor
        editor = KeyboardEditor(app)
        engine.rootContext().setContextProperty('keyboardEditor', editor)
    bridge = None
    if args.internet or args.radio:
        from playback_bridge import PlaybackBridge
        bridge = PlaybackBridge(args.config_dir.resolve(), app)
        engine.rootContext().setContextProperty('internetBridge', bridge)
        engine.rootContext().setContextProperty('radioBridge', bridge)
        app.aboutToQuit.connect(bridge.shutdown)
        if args.radio:
            from discovery_bridge import DiscoveryBridge
            discovery = DiscoveryBridge(args.config_dir.resolve(), app)
            engine.rootContext().setContextProperty('discoveryBridge', discovery)
            discovery.saved.connect(bridge.refreshCatalogue)
            app.aboutToQuit.connect(discovery.shutdown)
            from scan_bridge import ScanBridge
            scans = ScanBridge(args.config_dir.resolve(), bridge, app)
            engine.rootContext().setContextProperty('scanBridge', scans)
            scans.saved.connect(bridge.refreshCatalogue)
            app.aboutToQuit.connect(scans.shutdown)
            from preset_bridge import PresetBridge
            presets = PresetBridge(args.config_dir.resolve(), bridge, app)
            engine.rootContext().setContextProperty('presetBridge', presets)
            presets.saved.connect(bridge.refreshCatalogue)
            app.aboutToQuit.connect(presets.shutdown)
            from location_bridge import LocationBridge
            locations = LocationBridge(args.config_dir.resolve(), app)
            engine.rootContext().setContextProperty('locationBridge', locations)
            locations.saved.connect(scans.refreshLocations)
            app.aboutToQuit.connect(locations.shutdown)
            from power_bridge import PowerBridge
            power = PowerBridge(bridge, [discovery, scans, presets, locations], app,
                                platform=app.platformName())
            engine.rootContext().setContextProperty('powerBridge', power)
            app.aboutToQuit.connect(power.shutdown)
    engine.setInitialProperties({'windowed': args.windowed, 'backendName': app.platformName(),
                                 'contentRotation': args.rotation})
    scene = 'Radio.qml' if args.radio else 'Internet.qml' if args.internet else 'KeyboardTest.qml' if args.keyboard_test else 'Main.qml'
    engine.load(QUrl.fromLocalFile(str(Path(__file__).with_name(scene).resolve())))
    if not engine.rootObjects():
        if bridge is not None:
            bridge.shutdown()
        return 1
    if args.ready_file:
        import json
        import os
        def announce_ready():
            temporary = args.ready_file.with_suffix('.tmp')
            temporary.write_text(json.dumps({'pid': os.getpid()}))
            temporary.replace(args.ready_file)
        QTimer.singleShot(0, announce_ready)
    engine.quit.connect(app.quit)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    # Allow Python signal delivery even while Qt has no pending UI events.
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(100)
    if args.timeout:
        QTimer.singleShot(args.timeout * 1000, app.quit)
    mode = 'radio playback via PHP' if (args.internet or args.radio) else 'display-only, no audio'
    print(f'Qt {qVersion()}; platform {app.platformName()}; {mode}.', flush=True)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
