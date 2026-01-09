"""
Package entry point for notify_to_cisco_webex.

This module enables running the package with:

    python -m notify_to_cisco_webex

It delegates to the `main` function implemented in
`notify_to_cisco_webex.notify_to_cisco_webex`.

Google-style docstrings are used.
"""

from __future__ import annotations

import sys

from .notify_to_cisco_webex import main


def run() -> int:
    """Run the CLI main function with command-line arguments.

    Returns:
        Exit code returned by the underlying `main` function.
    """
    # Pass argv excluding the program name to the underlying main to allow
    # easier testing and consistent behavior with argparse usage in main().
    return main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(run())
