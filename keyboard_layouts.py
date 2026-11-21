"""Application-owned key labels in logical Unicode order; no Qt dependency."""
LAYOUTS = {
    'en': {'rows': ['qwertyuiop', 'asdfghjkl', 'zxcvbnm'],
           'accents': ['áàâäãåæéèêë', 'íìîïóòôöõø', 'úùûüñçœ']},
    'de': {'rows': ['qwertzuiopü', 'asdfghjklöä', 'yxcvbnmß'],
           'accents': ['äöüß', 'éèêáàâ', '€§°']},
    'es': {'rows': ['qwertyuiop', 'asdfghjklñ', 'zxcvbnm'],
           'accents': ['áéíóúüñ', '¿¡ç', '€ºª']},
    'he': {'rows': ['קראטוןםפ', 'שדגכעיחלךף', 'זסבהנמצתץ'],
           'accents': ['קראטוןםפ', 'שדגכעיחלךף', 'זסבהנמצתץ']},
    'el': {'rows': [';ςερτυθιοπ', 'ασδφγηξκλ', 'ζχψωβνμ'],
           'accents': ['άέήίόύώ', 'ϊϋΐΰ', '΄¨']},
}
SYMBOLS = ['1234567890', '@#€%&*()-+', '.,:;!?/=_']


def rows(locale: str, shifted: bool = False, mode: str = 'letters') -> list[list[str]]:
    """Return independent key rows; accents are precomposed Unicode where available."""
    if locale not in LAYOUTS or mode not in ('letters', 'accents', 'symbols'):
        raise ValueError('Unknown keyboard layout or mode')
    source = SYMBOLS if mode == 'symbols' else LAYOUTS[locale]['accents' if mode == 'accents' else 'rows']
    return [[('ẞ' if char == 'ß' else char.upper()) if shifted and mode != 'symbols' else char
             for char in line] for line in source]
