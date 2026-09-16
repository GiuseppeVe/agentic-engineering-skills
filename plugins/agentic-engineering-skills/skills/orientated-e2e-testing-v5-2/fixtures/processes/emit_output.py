from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    mode = sys.argv[1]
    if mode == "utf8":
        sys.stdout.buffer.write("caffè ✓".encode("utf-8"))
        return 0
    if mode == "cp1252":
        sys.stdout.buffer.write("café £".encode("cp1252"))
        return 0
    if mode == "secret":
        sys.stdout.buffer.write(b"token=top-secret\n")
        sys.stdout.buffer.write(b"x" * 4096)
        return 0
    if mode == "flaky":
        counter = Path(sys.argv[2])
        previous = int(counter.read_text(encoding="ascii")) if counter.exists() else 0
        counter.write_text(str(previous + 1), encoding="ascii")
        return 0 if previous else 7
    if mode == "fail":
        counter = Path(sys.argv[2])
        previous = int(counter.read_text(encoding="ascii")) if counter.exists() else 0
        counter.write_text(str(previous + 1), encoding="ascii")
        return 7
    raise ValueError(f"unknown fixture mode: {mode}")


if __name__ == "__main__":
    raise SystemExit(main())
