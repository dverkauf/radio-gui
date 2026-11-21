import unittest
from keyboard_layouts import rows


class LayoutTest(unittest.TestCase):
    def test_all_layouts_provide_three_independent_rows(self):
        for locale in ['en', 'de', 'es', 'he', 'el']:
            result = rows(locale)
            self.assertEqual(len(result), 3)
            result[0].clear()
            self.assertTrue(rows(locale)[0])

    def test_german_letters_and_uppercase_eszett(self):
        self.assertTrue(set('äöüß') <= set(sum(rows('de'), [])))
        self.assertIn('ẞ', sum(rows('de', True), []))

    def test_spanish_accents_and_punctuation(self):
        self.assertTrue(set('áéíóúüñ¿¡') <= set(sum(rows('es', mode='accents'), [])))

    def test_hebrew_includes_standard_and_final_letters(self):
        self.assertTrue(set('אבגדהוזחטיכלמנסעפצקרשתךםןףץ') <= set(sum(rows('he'), [])))
        self.assertEqual(rows('he'), rows('he', True))

    def test_greek_accents_and_final_sigma(self):
        self.assertTrue(set('άέήίόύώϊϋΐΰ') <= set(sum(rows('el', mode='accents'), [])))
        self.assertTrue(set('σς') <= set(sum(rows('el'), [])))

    def test_symbols_include_url_characters(self):
        self.assertTrue(set('1234567890:/.-_?=@') <= set(sum(rows('en', mode='symbols'), [])))

    def test_unknown_layout_is_rejected(self):
        with self.assertRaises(ValueError): rows('unknown')


if __name__ == '__main__': unittest.main()
