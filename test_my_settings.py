import os
import shutil
import tempfile
import unittest

from my_settings import DEFAULTS_FILE, MissingSettings, load_settings


class LoadSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, 'settings.toml')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, text):
        with open(self.path, 'w') as f:
            f.write(text)

    def test_missing_file_says_to_copy_the_defaults(self):
        with self.assertRaises(MissingSettings) as raised:
            load_settings('/repo', self.path)
        self.assertIn(DEFAULTS_FILE, str(raised.exception))

    def test_fills_in_root_and_repository_at_every_level(self):
        self.write('root = "/r"\n'
                   '[a]\nx = "{root}/x"\ny = "{repository}/y"\n'
                   '[[a.items]]\nz = "{root}"\n')
        settings = load_settings('/repo', self.path)
        self.assertEqual(settings['a']['x'], '/r/x')
        self.assertEqual(settings['a']['y'], '/repo/y')
        self.assertEqual(settings['a']['items'], [{'z': '/r'}])

    def test_leaves_other_values_alone(self):
        self.write('root = "/r"\ncount = 3\nflag = true\nplain = "no placeholders"\n')
        settings = load_settings('/repo', self.path)
        self.assertEqual((settings['count'], settings['flag'], settings['plain']),
                         (3, True, 'no placeholders'))

    def test_defaults_file_loads(self):
        settings = load_settings('/repo', DEFAULTS_FILE)
        self.assertEqual(settings['xc']['folder'], '/path/to/repositories/example-sdk')


if __name__ == '__main__':
    unittest.main()
