#!/usr/bin/env python3
"""Release helper used by .github/workflows/release.yml (stdlib only, py>=3.11).

    release_bump.py bump {none|patch|minor|major} [--dry-run]
        Compute the next version from pyproject.toml ("none" keeps the current
        one), rewrite pyproject.toml, the _api_version() fallback literal in
        uav_api/api_app.py and the Unreleased section of CHANGELOG.md, and
        print the resulting version to stdout.

    release_bump.py notes <version>
        Print the CHANGELOG.md body of an already-released version, for use
        as GitHub release notes.
"""

import argparse
import datetime
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = ROOT / "pyproject.toml"
API_APP = ROOT / "uav_api" / "api_app.py"
CHANGELOG = ROOT / "CHANGELOG.md"
COMPARE_URL = "https://github.com/Project-GrADyS/uav_api/compare"

LINK_LINE = re.compile(r"^\[(\d+\.\d+\.\d+)\]: ", re.MULTILINE)


def fail(message: str) -> None:
    print(f"release_bump: {message}", file=sys.stderr)
    sys.exit(1)


def read(path: Path) -> str:
    # newline="" keeps any \r\n intact so files are written back byte-for-byte
    # outside the edited lines (pyproject.toml is CRLF in the repo).
    return path.read_text(newline="")


def write(path: Path, text: str) -> None:
    with path.open("w", newline="") as f:
        f.write(text)


def current_version() -> str:
    with PYPROJECT.open("rb") as f:
        version = tomllib.load(f)["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        fail(f"pyproject.toml version {version!r} is not X.Y.Z")
    return version


def next_version(current: str, bump: str) -> str:
    major, minor, patch = (int(p) for p in current.split("."))
    if bump == "none":
        return current
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    return f"{major + 1}.0.0"


def replace_once(path: Path, pattern: str, replacement: str, text: str) -> str:
    new_text, count = re.subn(pattern, replacement, text, flags=re.MULTILINE)
    if count != 1:
        fail(f"expected exactly one match for {pattern!r} in {path}, found {count}")
    return new_text


def bumped_pyproject(old: str, new: str) -> str:
    text = read(PYPROJECT)
    return replace_once(
        PYPROJECT, rf'^version = "{re.escape(old)}"(\r?)$', rf'version = "{new}"\1', text
    )


def bumped_api_app(old: str, new: str) -> str:
    # The fallback literal in _api_version() must equal the pyproject version;
    # a zero-match failure here means the two files have drifted apart.
    text = read(API_APP)
    return replace_once(
        API_APP, rf'^        return "{re.escape(old)}"(\r?)$', rf'        return "{new}"\1', text
    )


def bumped_changelog(new: str) -> str:
    text = read(CHANGELOG)
    if f"## [{new}]" in text:
        fail(f"CHANGELOG.md already has a [{new}] section")
    eol = "\r\n" if "\r\n" in text else "\n"

    heading_match = re.search(r"^## \[Unreleased\]\r?$", text, re.MULTILINE)
    if heading_match is None:
        fail("CHANGELOG.md has no '## [Unreleased]' heading")
    section_start = heading_match.end()
    next_heading = re.search(r"^(?:## \[|\[\d)", text[section_start:], re.MULTILINE)
    section_end = section_start + next_heading.start() if next_heading else len(text)
    if not text[section_start:section_end].strip():
        fail("the Unreleased section is empty; nothing to release")

    today = datetime.date.today().isoformat()
    text = replace_once(
        CHANGELOG,
        r"^## \[Unreleased\](\r?)$",
        f"## [Unreleased]{eol}{eol}## [{new}] - {today}\\1",
        text,
    )

    first_link = LINK_LINE.search(text)
    if first_link is None:
        fail("CHANGELOG.md has no version-compare link block")
    previous = first_link.group(1)
    compare = f"[{new}]: {COMPARE_URL}/v{previous}...v{new}{eol}"
    return text[: first_link.start()] + compare + text[first_link.start() :]


def notes(version: str) -> str:
    text = read(CHANGELOG)
    heading = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n", text, re.MULTILINE)
    if heading is None:
        fail(f"CHANGELOG.md has no [{version}] section")
    body = text[heading.end() :]
    end = re.search(r"^(?:## \[|\[\d)", body, re.MULTILINE)
    if end:
        body = body[: end.start()]
    if not body.strip():
        fail(f"the [{version}] section of CHANGELOG.md is empty")
    return body.strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    bump = sub.add_parser("bump", help="bump the version and rewrite the release files")
    bump.add_argument("kind", choices=["none", "patch", "minor", "major"])
    bump.add_argument("--dry-run", action="store_true", help="print the version without writing")
    notes_cmd = sub.add_parser("notes", help="print a released version's changelog body")
    notes_cmd.add_argument("version")
    args = parser.parse_args()

    if args.command == "notes":
        sys.stdout.write(notes(args.version))
        return

    old = current_version()
    new = next_version(old, args.kind)
    # Compute every edit before writing any file, so a failed check (empty
    # changelog, drifted fallback literal) leaves the working tree untouched.
    edits = [(CHANGELOG, bumped_changelog(new))]
    if new != old:
        edits.append((PYPROJECT, bumped_pyproject(old, new)))
        edits.append((API_APP, bumped_api_app(old, new)))
    if not args.dry_run:
        for path, text in edits:
            write(path, text)
    print(new)


if __name__ == "__main__":
    main()
