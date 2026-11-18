#!/usr/bin/env python3
"""Check docs/references.bib against Crossref (DOIs) and arXiv (eprints).

For every entry with a DOI the script asks Crossref for the record and compares the title, the
year and the first author's family name with the entry. For every entry with an arXiv eprint it
asks the arXiv API and compares the same three fields. Entries with neither are listed as
skipped: they were checked by hand and the method is written in docs/references.md.

Standard library only. Run it from the repository root:

    uv run python scripts/check_references.py
    uv run python scripts/check_references.py --bib docs/references.bib --delay 1.0

Exit codes: 0 every checked entry matches; 1 at least one mismatch or an unreadable bib file;
2 at least one entry could not be checked because the network or the service failed (a failed
check is never reported as a pass). The script prints no traceback for network failures.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_AGENT = "factordesk-reference-check/1.0 (+https://github.com/lbsm2017/factordesk)"
CROSSREF = "https://api.crossref.org/works/"
ARXIV = "https://export.arxiv.org/api/query?id_list="
ATOM = "{http://www.w3.org/2005/Atom}"

EXIT_OK, EXIT_MISMATCH, EXIT_NETWORK = 0, 1, 2


class NetworkError(Exception):
    """The service could not be reached or answered with an error status."""


class NotFound(Exception):
    """The service answered that the identifier does not exist."""


# ---------------------------------------------------------------------------
# BibTeX reading (enough of the format for this repository's file)
# ---------------------------------------------------------------------------


def _read_braced(text: str, start: int) -> tuple[str, int]:
    """Return the text inside the brace group that opens at text[start], and the next index."""
    depth = 0
    i = start
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : i], i + 1
        i += 1
    raise ValueError("unbalanced braces in the bib file")


def parse_bib(text: str) -> list[dict[str, str]]:
    """Parse entries into dicts with the keys `_type`, `_key` and the lower-cased field names."""
    entries: list[dict[str, str]] = []
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("%")]
    text = "\n".join(lines)
    pos = 0
    while True:
        at = text.find("@", pos)
        if at < 0:
            break
        m = re.match(r"@(\w+)\s*\{", text[at:])
        if not m:
            pos = at + 1
            continue
        body, nxt = _read_braced(text, at + m.end() - 1)
        pos = nxt
        key, _, rest = body.partition(",")
        entry: dict[str, str] = {"_type": m.group(1).lower(), "_key": key.strip()}
        i = 0
        while i < len(rest):
            fm = re.match(r"\s*([A-Za-z][\w-]*)\s*=\s*", rest[i:])
            if not fm:
                i += 1
                continue
            i += fm.end()
            if i < len(rest) and rest[i] == "{":
                value, i = _read_braced(rest, i)
            elif i < len(rest) and rest[i] == '"':
                j = rest.find('"', i + 1)
                value, i = rest[i + 1 : j], j + 1
            else:
                vm = re.match(r"[^,\n]*", rest[i:])
                value = vm.group(0).strip() if vm else ""
                i += len(vm.group(0)) if vm else 0
            entry[fm.group(1).lower()] = re.sub(r"\s+", " ", value).strip()
        entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

_LATEX_ACCENTS = {
    r"\"": "",
    r"\'": "",
    r"\`": "",
    r"\^": "",
    r"\~": "",
    r"\c": "",
    r"\v": "",
}


def _ascii(text: str) -> str:
    for macro, repl in _LATEX_ACCENTS.items():
        text = text.replace(macro, repl)
    text = text.replace(r"\o", "o").replace(r"\O", "O").replace("{\\o}", "o")
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def norm_title(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&amp;", "and").replace(r"\&", "and").replace("&", "and")
    text = _ascii(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_name(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _ascii(text).lower())


def first_family(authors: str) -> str:
    """Family name of the first author of a BibTeX `author` field."""
    first = re.split(r"\s+and\s+", authors.strip(), maxsplit=1)[0].strip()
    first = first.strip("{}")
    if "," in first:
        return first.split(",", 1)[0]
    return first.split()[-1] if first.split() else ""


# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------


def fetch(url: str, timeout: float, delay: float, retries: int = 4) -> bytes:
    """GET a URL with a polite pause, retrying on rate limits and server errors."""
    last = "no attempt"
    for attempt in range(retries):
        time.sleep(delay if attempt == 0 else delay + 3.0 * attempt)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                raise NotFound(url) from exc
            last = f"HTTP {exc.code}"
            if exc.code not in (429, 500, 502, 503, 504):
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"
    raise NetworkError(last)


def crossref_record(doi: str, timeout: float, delay: float) -> dict:
    url = CROSSREF + urllib.parse.quote(doi, safe="()/:;<>")
    try:
        return json.loads(fetch(url, timeout, delay))["message"]
    except (ValueError, KeyError) as exc:
        raise NetworkError("unreadable Crossref answer") from exc


def arxiv_record(eprint: str, timeout: float, delay: float) -> dict:
    raw = fetch(ARXIV + urllib.parse.quote(eprint), timeout, delay)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise NetworkError("unreadable arXiv answer") from exc
    entry = root.find(ATOM + "entry")
    if entry is None or entry.find(ATOM + "title") is None:
        raise NotFound(eprint)
    names = [(a.findtext(ATOM + "name") or "").strip() for a in entry.findall(ATOM + "author")]
    published = (entry.findtext(ATOM + "published") or "")[:4]
    return {
        "title": [re.sub(r"\s+", " ", entry.findtext(ATOM + "title") or "").strip()],
        "years": {published} if published else set(),
        "first_family": norm_name(names[0].split()[-1]) if names else "",
    }


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


def compare_title(bib_title: str, remote_titles: list[str]) -> tuple[bool, str]:
    mine = norm_title(bib_title)
    for rt in remote_titles:
        theirs = norm_title(rt)
        if mine == theirs:
            return True, ""
        if mine.startswith(theirs) or theirs.startswith(mine):
            return True, "title differs only by a suffix"
    return False, f"title: bib {bib_title!r} vs record {remote_titles[0]!r}"


def crossref_fields(msg: dict) -> dict:
    titles = list(msg.get("title") or [])
    subtitles = list(msg.get("subtitle") or [])
    if titles and subtitles:
        titles.append(f"{titles[0]}: {subtitles[0]}")
    years: set[str] = set()
    for key in ("issued", "published-print", "published-online", "published"):
        parts = (msg.get(key) or {}).get("date-parts") or [[None]]
        if parts and parts[0] and parts[0][0]:
            years.add(str(parts[0][0]))
    authors = msg.get("author") or []
    family = norm_name(authors[0].get("family", authors[0].get("name", ""))) if authors else ""
    return {"title": titles or [""], "years": years, "first_family": family}


def check_entry(entry: dict[str, str], remote: dict) -> tuple[list[str], list[str]]:
    """Return (problems, notes) from comparing one entry with the remote fields."""
    problems: list[str] = []
    notes: list[str] = []
    ok, why = compare_title(entry.get("title", ""), remote["title"])
    if not ok:
        problems.append(why)
    elif why:
        notes.append(why)
    year = entry.get("year", "")
    if remote["years"] and year not in remote["years"]:
        problems.append(f"year: bib {year} vs record {sorted(remote['years'])}")
    elif not remote["years"]:
        notes.append("record has no year")
    mine = norm_name(first_family(entry.get("author", "")))
    if not remote["first_family"]:
        notes.append("record lists no author; first author not compared")
    elif mine != remote["first_family"]:
        problems.append(f"first author: bib {mine!r} vs record {remote['first_family']!r}")
    return problems, notes


def say(text: str) -> None:
    print(text.encode("ascii", "replace").decode("ascii"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Check docs/references.bib against Crossref and arXiv."
    )
    ap.add_argument("--bib", default="docs/references.bib", help="path to the bib file")
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
    ap.add_argument("--timeout", type=float, default=30.0, help="seconds per request")
    args = ap.parse_args(argv)

    path = Path(args.bib)
    try:
        entries = parse_bib(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        say(f"cannot read {path}: {exc}")
        return EXIT_MISMATCH
    if not entries:
        say(f"no entries found in {path}")
        return EXIT_MISMATCH

    say(f"Checking {len(entries)} entries in {path} (Crossref for DOIs, arXiv for eprints)")
    n_ok = n_bad = n_net = n_skip = 0
    for entry in entries:
        key = entry["_key"]
        doi = entry.get("doi", "")
        is_arxiv = entry.get("archiveprefix", "").lower() == "arxiv"
        eprint = entry.get("eprint", "") if is_arxiv else ""
        if not doi and not eprint:
            n_skip += 1
            say(f"SKIP  {key}: no DOI or arXiv id (checked by hand, see docs/references.md)")
            continue
        try:
            if doi:
                remote = crossref_fields(crossref_record(doi, args.timeout, args.delay))
                source = f"doi:{doi}"
            else:
                remote = arxiv_record(eprint, args.timeout, args.delay)
                source = f"arXiv:{eprint}"
        except NotFound:
            n_bad += 1
            say(f"FAIL  {key}: {doi or eprint} does not exist in {'Crossref' if doi else 'arXiv'}")
            continue
        except NetworkError as exc:
            n_net += 1
            say(f"ERROR {key}: could not check {doi or eprint} ({exc})")
            continue
        problems, notes = check_entry(entry, remote)
        if problems:
            n_bad += 1
            say(f"FAIL  {key} ({source}): " + "; ".join(problems))
        else:
            n_ok += 1
            extra = f" [{'; '.join(notes)}]" if notes else ""
            say(f"OK    {key} ({source}){extra}")

    say(
        f"Summary: {n_ok} match, {n_bad} mismatch, {n_net} not checked (network or service), "
        f"{n_skip} skipped (no DOI or arXiv id)"
    )
    if n_net:
        say("Some entries could not be checked; run again when the network is available.")
        return EXIT_NETWORK
    return EXIT_MISMATCH if n_bad else EXIT_OK


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        say("interrupted")
        sys.exit(EXIT_NETWORK)
