"""Paste eval/results/comparison.md into README.md between the RESULTS markers.
Usage: python scripts/fill_results.py [path/to/comparison.md]
"""

from __future__ import annotations

import sys
from pathlib import Path

BEGIN, END = "<!-- RESULTS:BEGIN -->", "<!-- RESULTS:END -->"


def main() -> None:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "eval/results/comparison.md")
    readme = Path("README.md")
    text = readme.read_text(encoding="utf-8")
    a, b = text.index(BEGIN) + len(BEGIN), text.index(END)
    table = src.read_text(encoding="utf-8").strip()
    text = text[:a] + "\n" + table + "\n" + text[b:]
    readme.write_text(text, encoding="utf-8")
    print(f"pasted {src} ({len(table):,} chars) into README.md")


if __name__ == "__main__":
    main()
