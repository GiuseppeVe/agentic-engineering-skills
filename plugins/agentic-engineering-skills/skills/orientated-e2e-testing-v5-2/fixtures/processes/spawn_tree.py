from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    pid_path = Path(sys.argv[1])
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid_path.write_text(str(child.pid), encoding="ascii")
    if len(sys.argv) > 2 and sys.argv[2] == "exit-parent":
        return 7
    time.sleep(120)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
