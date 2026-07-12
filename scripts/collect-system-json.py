#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from qingluo_console.collectors.system import collect_system_resources


def main() -> None:
    snapshot = collect_system_resources()
    print(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
