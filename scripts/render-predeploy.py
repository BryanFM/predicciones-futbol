#!/usr/bin/env python3
"""Migraciones y seed antes del arranque en Render (preDeployCommand)."""

from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def main() -> int:
    os.environ.setdefault("ENVIRONMENT", "production")
    from app.main import _database_bootstrap

    _database_bootstrap()
    print("→ preDeploy: BD lista")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
