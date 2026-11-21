"""Read-only Pi display inventory; never opens DRM/input devices or changes services."""
from __future__ import annotations

import ctypes.util
import glob
import importlib.util
import os
import platform
from pathlib import Path


def read(path: Path) -> str | None:
    try:
        return path.read_text(errors='replace').strip()[:2048]
    except OSError:
        return None


def report() -> dict:
    data = {
        'python': platform.python_version(), 'architecture': platform.machine(),
        'kernel': platform.release(), 'os': read(Path('/etc/os-release')),
        'session': {key: os.environ.get(key) for key in (
            'DISPLAY', 'WAYLAND_DISPLAY', 'XDG_SESSION_TYPE', 'QT_QPA_PLATFORM',
            'QT_QUICK_BACKEND', 'QSG_RHI_BACKEND')},
        'devices': [], 'connectors': [],
        'libraries': {name: ctypes.util.find_library(name) for name in ('EGL', 'gbm', 'GLESv2')},
    }
    for pattern in ('/dev/dri/card*', '/dev/dri/renderD*', '/dev/input/event*'):
        for name in sorted(glob.glob(pattern)):
            path = Path(name)
            try:
                stat = path.stat()
                data['devices'].append({'path': name, 'readable': os.access(path, os.R_OK),
                    'writable': os.access(path, os.W_OK), 'group_id': stat.st_gid})
            except OSError:
                pass
    for status in sorted(Path('/sys/class/drm').glob('card*-*/status')):
        data['connectors'].append({'connector': status.parent.name, 'status': read(status),
            'modes': read(status.parent / 'modes')})
    if importlib.util.find_spec('PySide6') is None:
        data['qt'] = {'available': False, 'reason': 'PySide6 is not installed in this interpreter'}
    else:
        try:
            import PySide6
            from PySide6.QtCore import QLibraryInfo, qVersion
            plugins = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))
            data['qt'] = {'available': True, 'pyside_version': getattr(PySide6, '__version__', 'unknown'),
                'qt_version': qVersion(), 'plugins_path': str(plugins),
                'platform_plugins': sorted(p.name for p in (plugins / 'platforms').glob('*.so')),
                'egl_integrations': sorted(p.name for p in (plugins / 'egldeviceintegrations').glob('*.so'))}
        except Exception as error:
            data['qt'] = {'available': False, 'reason': str(error)}
    data['limits'] = 'File/library availability only; no graphics, touch mapping or EGLFS startup has been tested.'
    return data
