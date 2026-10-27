"""Generate PEP 503 simple index pages for the package index at https://pkgs.agnos.one/simple/.

Usage:
    python scripts/build_index.py project <dir> <name>   # write <dir>/index.html, linking every file in <dir>
    python scripts/build_index.py root <file> <name>...   # write <file>, linking every project in the index

Only the standard library is used, so the script runs on the CI runner's system Python.
"""

import hashlib
import html
import re
import sys
import tarfile
import zipfile
from email.parser import HeaderParser
from pathlib import Path

DIST_SUFFIXES = (".whl", ".tar.gz")


def normalize(name: str) -> str:
    """Return the PEP 503 normalized form of a project name, e.g. `My_Package` -> `my-package`."""
    return re.sub(r"[-_.]+", "-", name).lower()


def read_metadata(path: Path) -> str:
    """Return the core metadata of a wheel (`METADATA`) or sdist (`PKG-INFO`)."""
    if path.name.endswith(".whl"):
        with zipfile.ZipFile(path) as wheel:
            member = next(n for n in wheel.namelist() if re.fullmatch(r"[^/]+\.dist-info/METADATA", n))
            return wheel.read(member).decode()
    with tarfile.open(path) as sdist:
        info = next(m for m in sdist.getmembers() if re.fullmatch(r"[^/]+/PKG-INFO", m.name))
        file = sdist.extractfile(info)
        if file is None:
            raise ValueError(f"{path.name}: PKG-INFO is not a regular file")
        with file:
            return file.read().decode()


def file_link(path: Path) -> str:
    """Return the anchor for a distribution file, with its SHA-256 and `Requires-Python`."""
    with path.open("rb") as f:
        digest = hashlib.file_digest(f, "sha256").hexdigest()
    href = html.escape(f"{path.name}#sha256={digest}")
    requires_python = HeaderParser().parsestr(read_metadata(path)).get("Requires-Python")
    attrs = f' data-requires-python="{html.escape(requires_python)}"' if requires_python else ""
    return f'<a href="{href}"{attrs}>{html.escape(path.name)}</a>'


HTML_TEMPLATE = """<!DOCTYPE html>
<html>
  <head>
    <meta name="pypi:repository-version" content="1.0">
    <title>{title}</title>
  </head>
  <body>
    <h1>{title}</h1>
    {body}
  </body>
</html>
"""


def page(title: str, links: list[str]) -> str:
    body = "\n    ".join(f"{link}<br>" for link in links)
    return HTML_TEMPLATE.format(title=html.escape(title), body=body)


def main(argv: list[str]) -> None:
    match argv:
        case ["project", directory, name]:
            files = sorted(p for p in Path(directory).iterdir() if p.name.endswith(DIST_SUFFIXES))
            if not files:
                raise SystemExit(f"no distribution files in {directory}")
            index = Path(directory) / "index.html"
            index.write_text(page(f"Links for {normalize(name)}", [file_link(p) for p in files]))
        case ["root", file, *names] if names:
            projects = sorted({normalize(n) for n in names})
            links = [f'<a href="{html.escape(p)}/">{html.escape(p)}</a>' for p in projects]
            Path(file).write_text(page("Simple index", links))
        case _:
            raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
