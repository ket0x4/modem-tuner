"""Allow running the app straight from the source tree."""

import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
