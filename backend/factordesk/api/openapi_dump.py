"""Write the OpenAPI document for frontend type generation.

Usage: ``uv run python -m factordesk.api.openapi_dump frontend/src/api/openapi.json``
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from factordesk.api.deps import default_deps
from factordesk.api.main import create_app


def openapi_text() -> str:
    """The OpenAPI document as stable, indented JSON ending in a newline."""
    document = create_app(default_deps(None)).openapi()
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: python -m factordesk.api.openapi_dump OUTPUT.json", file=sys.stderr)
        return 2
    out = Path(args[0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(openapi_text(), encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
