from __future__ import annotations

import compileall
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ok = compileall.compile_dir(root / "app", quiet=1)
    ok = compileall.compile_dir(root / "tests", quiet=1) and ok
    if not ok:
        raise SystemExit("Syntax compilation failed")
    print("Volume 2 syntax compilation passed")


if __name__ == "__main__":
    main()
