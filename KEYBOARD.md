# Multilingual application keyboard prototype

Open the separate text-entry page, leaving the sample radio page available:

```bash
/usr/bin/python3 preview_wayland.py --keyboard-test
```

Tap either field. The keyboard follows the focused editor. Language buttons select
English QWERTY, German QWERTZ, Spanish, Hebrew or Greek; existing text is retained.
Shift applies to the next letter. Accents opens direct language-specific alternate
characters; the symbols page includes numbers, URL punctuation and currency signs.
Greek includes tonos/dialytika and final sigma; Hebrew includes final letter forms.

Select all, Backspace, cursor arrows, Space and Done use Qt text editing. Holding
Backspace repeats. Done submits only a local demonstration value and hides the
keyboard; Hide leaves the editor focused. Tap the field or Keyboard to show it again.
Escape hides the keyboard first, then exits; Exit/Ctrl+Q close the prototype.
No text is transmitted, persisted in ~/.radio, or printed by the keyboard bridge.
The second field tests targeting and URL punctuation; it does not fetch a feed.

The keyboard is a QML item inside the rotated scene, not a separate native window.
It does not require Qt Virtual Keyboard packages or change OS keyboard layouts.
Characters are committed as logical Unicode through QInputMethodEvent; editing
commands use Qt key events. Qt performs text shaping, bidirectional layout and
selection/cursor behavior. No string reversal or manual UTF-16 cursor arithmetic
is used. Keyboard buttons do not take editor focus.

This is an application-specific prototype, not a system input method. It does not
provide prediction, spellchecking, handwriting, niqqud, a full polytonic Greek
layout or a physical-keyboard layout switcher. Accents are explicit buttons rather
than long-press/dead-key composition. Shift is one-shot, not Caps Lock. Those limits
must not be confused with the supported five language layouts.

Native tests:

```bash
/usr/bin/python3 -m unittest -v test_keyboard_layouts.py test_keyboard_editor.py
QT_QUICK_BACKEND=software /usr/bin/python3 main.py --platform offscreen --keyboard-test --timeout 3
```

After the Wayland visual check, repeat EGLFS from SSH, closing unsaved desktop work
because this temporarily ends that session:

```bash
/usr/bin/python3 test_eglfs.py --rotation 90 --seconds 120 --keyboard-test
```

The existing test launcher restores the desktop after exit/timeout/handled failure.
Check accurate taps on keys at screen edges, unchanged logical Hebrew order, mixed
Latin/Hebrew text, Greek accents, selection replacement, backspace and switching
between the search and URL fields. Automated offscreen editing tests do not qualify
physical touch geometry or every possible Unicode editing sequence.
