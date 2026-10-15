import sys
import unittest

from sdlc.storage import command


class CommandTests(unittest.TestCase):
    def test_bounds_and_timeout_fail_explicitly(self):
        with self.assertRaisesRegex(ValueError, "output limit"):
            command([sys.executable, "-c", "print('a'*10000)"], max_bytes=100)
        with self.assertRaisesRegex(ValueError, "timed out"):
            command([sys.executable, "-c", "import time; time.sleep(10)"], timeout=0.05)

    def test_provider_stderr_is_not_exposed(self):
        with self.assertRaises(ValueError) as caught:
            command([sys.executable, "-c", "import sys; print('secret',file=sys.stderr); sys.exit(3)"])
        self.assertNotIn("secret", str(caught.exception))
        self.assertIn("exit code 3", str(caught.exception))
