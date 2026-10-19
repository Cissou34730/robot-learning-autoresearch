"""Human-owned campaign runner and protocol enforcement."""

import sys

from runner import paths

if paths.SPLIT:
    sys.path.insert(0, str(paths.ROOT))
