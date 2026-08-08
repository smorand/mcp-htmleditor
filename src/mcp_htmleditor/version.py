"""Application version.

The committed value is a placeholder; "make build" and "make docker-build"
overwrite it from the git tag (git describe --tags --always --dirty).
"""

from __future__ import annotations

__version__: str = "dev"
