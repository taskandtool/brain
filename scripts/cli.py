"""The one argument and error helper the scripts here share, so wording and
exit codes cannot drift between them."""
import argparse
import json
import os
import sys

# the app root: this file is <root>/scripts/cli.py
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MAX_LISTED = 15                   # findings a command lists before "--all for the rest"


class Misuse(Exception):
    """argparse's complaint, raised instead of printed so it gets a Try: line."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Misuse(message)


def fail(at, msg, lines=(), try_cmd=None, as_json=False):
    """An error on stderr: `<at>: <msg>`, indented lines, then Try:; or one
    JSON object under --json."""
    if as_json:
        print(json.dumps({"error": f"{at}: {msg}", "try": try_cmd}), file=sys.stderr)
        return
    print("\n".join([f"{at}: {msg}", *("  " + x for x in lines),
                     *([f"  Try: {try_cmd}"] if try_cmd else [])]), file=sys.stderr)
