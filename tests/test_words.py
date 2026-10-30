"""Every line of the scripts, the skills and AGENTS.md, through the tropes skill's scan."""
import os
import subprocess
import unittest

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Words(unittest.TestCase):
    def test_no_tells_of_ai_written_text(self):
        r = subprocess.run(
            ["node", ".claude/skills/tropes/tropes.mjs", "--scan", "scripts", "tests", "viewer", ".claude", "AGENTS.md"],
            cwd=APP, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
