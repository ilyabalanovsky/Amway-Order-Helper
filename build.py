from __future__ import annotations

from pathlib import Path
import sys

import PyInstaller.__main__


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    spec_path = project_dir / "order_helper.spec"
    PyInstaller.__main__.run(
        [
            "--noconfirm",
            "--clean",
            str(spec_path),
        ]
    )


if __name__ == "__main__":
    main()
