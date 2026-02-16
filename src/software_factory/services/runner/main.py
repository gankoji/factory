"""Minimal runner service entrypoint."""

from __future__ import annotations

import time


def main() -> None:
    """Keep runner process alive for local compose bring-up."""

    while True:
        time.sleep(30)


if __name__ == "__main__":
    main()
