"""A dataset directory's rules, its recipe tree, its record, and whether its version is published.

    python3 -I scripts/check.py datasets/<name>              the directory's rules; exit 1, one line per reason, on any
    python3 -I scripts/check.py --hub datasets/<name>        the rules, then the version, the tool, and the record against the Hub
    python3 -I scripts/check.py --tree datasets/<name>       prints git's tree hash of datasets/<name>/recipe/
    python3 -I scripts/check.py --candidate datasets/<name>  prints candidate-<tree>, the Hub branch a build is pushed to
    python3 -I scripts/check.py --scan FILE                  exits 1, naming each shape, when FILE holds what looks like a credential

The org and the toolshed come from hub.toml beside scripts/. Runs on Python 3.8 or later with the
standard library alone, since flyloft's host and a cluster's login node run it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
TOOL = re.compile(r"^[a-z0-9-]+@\d+\.\d+\.\d+$")
# What a credential looks like, by the prefix it is named for.
SECRETS = [(what, re.compile(rx)) for what, rx in [
    ("hf_", r"\bhf_[A-Za-z0-9]{30,}"),
    ("ghp_", r"\bghp_[A-Za-z0-9]{30,}"),
    ("gho_", r"\bgho_[A-Za-z0-9]{30,}"),
    ("AKIA", r"\bAKIA[0-9A-Z]{16}\b"),
    ("-----BEGIN", r"-----BEGIN"),
    ("xox", r"\bxox[bp]-"),
]]


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def frontmatter(path: Path) -> dict:
    return frontmatter_of(path.read_text(encoding="utf-8-sig", errors="replace"))


def frontmatter_of(text: str) -> dict:
    """The first `---` block: `key: value` lines, and `key:` opening a dict of two-space-indented lines.

    One pair of matching quotes around a value is removed. {} when there is no block.
    """
    lines = text.lstrip("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    out, nested = {}, None
    for line in lines[1:]:
        if line.strip() == "---":
            return out
        if not line.strip():
            continue
        if line.startswith("  ") and nested is not None:
            key, _, value = line.strip().partition(":")
            nested[key.strip()] = unquote(value)
            continue
        key, _, value = line.partition(":")
        if value.strip():
            out[key.strip()], nested = unquote(value), None
        else:
            nested = out[key.strip()] = {}
    return {}  # no closing ---


def read_toml(text: str, minimal: bool = False) -> dict:
    """tomllib's reading on 3.11+; before it, flat `key = value` lines whose values are JSON-shaped
    (strings, numbers, booleans, arrays), which is every shape a recipe's params.toml holds."""
    if not minimal:
        try:
            import tomllib
            return tomllib.loads(text)
        except ImportError:
            pass
    out = {}
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, eq, value = line.partition("=")
        value = re.sub(r"\s+#[^\"\]]*$", "", value.strip())  # a trailing comment
        try:
            if not eq:
                raise ValueError("no =")
            out[unquote(key)] = json.loads(value)
        except ValueError as e:
            raise ValueError(f"line {n}: {e}") from None
    return out


def hub_toml() -> dict:
    return read_toml((ROOT / "hub.toml").read_text())


def hub_org() -> str:
    return hub_toml()["org"]


def toolshed_registry() -> str:
    return hub_toml()["toolshed"]


def scan(text: str) -> list[str]:
    """The credential shapes found in text, each once, in SECRETS' order."""
    return [what for what, rx in SECRETS if rx.search(text)]


def _object(kind: str, data: bytes) -> bytes:
    return hashlib.sha1(f"{kind} {len(data)}\0".encode() + data).digest()


def _tree(d: Path) -> bytes | None:
    """git's tree object id for d, or None when d holds no file (git does not keep an empty directory)."""
    entries = []
    for p in d.iterdir():
        if p.is_dir():
            sub = _tree(p)
            if sub is not None:
                entries.append((p.name + "/", b"40000 " + p.name.encode() + b"\0" + sub))
        else:
            mode = b"100755" if os.access(p, os.X_OK) else b"100644"
            entries.append((p.name, mode + b" " + p.name.encode() + b"\0" + _object("blob", p.read_bytes())))
    if not entries:
        return None
    # git sorts a tree's entries by name, a directory's as if it ended in "/"
    return _object("tree", b"".join(e for _, e in sorted(entries, key=lambda e: e[0].encode())))


def tree_hash(recipe_dir: Path) -> str:
    """git's tree hash of recipe_dir, from the files: `git rev-parse HEAD:<recipe_dir>` once committed."""
    return (_tree(recipe_dir) or _object("tree", b"")).hex()


def rules(dataset_dir: Path) -> list[str]:
    """The reasons this dataset directory breaks the rules; empty when it passes."""
    name, reasons = dataset_dir.name, []
    skill = dataset_dir / "SKILL.md"
    fm = frontmatter(skill) if skill.is_file() else None
    meta = fm.get("metadata") if fm else None
    if fm is None:
        reasons.append("SKILL.md is missing")
    elif not isinstance(meta, dict):
        reasons.append("SKILL.md has no frontmatter block (--- ... ---) with metadata")
    else:
        if fm.get("name") != name:
            reasons.append(f"name {fm.get('name')!r} is not the directory's {name!r}")
        if not fm.get("description"):
            reasons.append("description is empty")
        if not VERSION.match(meta.get("version", "")):
            reasons.append(f"version {meta.get('version')!r} is not MAJOR.MINOR.PATCH")
        if not TOOL.match(meta.get("tool", "")):
            reasons.append(f"tool {meta.get('tool')!r} is not a toolshed tool's name@MAJOR.MINOR.PATCH")
        if not meta.get("license"):
            reasons.append("license is empty")
    for script in ("recipe/build", "recipe/test"):
        p = dataset_dir / script
        if not p.is_file():
            reasons.append(f"{script} is missing")
        elif not os.access(p, os.X_OK):
            reasons.append(f"{script} is not executable")
    params = dataset_dir / "recipe" / "params.toml"
    if not params.is_file():
        reasons.append("recipe/params.toml is missing")
    else:
        try:
            read_toml(params.read_text(encoding="utf-8"))
        except ValueError as e:
            reasons.append(f"recipe/params.toml does not parse: {e}")
    for p in sorted(p for p in dataset_dir.rglob("*") if p.is_file()):
        found = scan(p.read_text(encoding="utf-8", errors="replace"))
        if found:
            reasons.append(f"{p.relative_to(dataset_dir)} holds what looks like a credential ({', '.join(found)})")
    return reasons


def fetch(url: str) -> bytes | None:
    """The body of a public GET, with no credential; None when the server answers 401 or 404, which is
    how the Hub answers a missing repository and a missing revision."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "datasets-check"})) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in (401, 404):
            return None
        raise


def hub_get(url: str) -> object:
    body = fetch(url)
    return None if body is None else json.loads(body)


def shed_catalogue() -> set[str]:
    """name@version of every tool on the toolshed's main, the shed being hub.toml's registry path."""
    shed = toolshed_registry().split("/", 1)[1]
    tools = hub_get(f"https://api.github.com/repos/{shed}/contents/tools") or []
    out = set()
    for t in tools:
        if t.get("type") != "dir":
            continue
        skill = fetch(f"https://raw.githubusercontent.com/{shed}/main/tools/{t['name']}/SKILL.md")
        meta = frontmatter_of(skill.decode("utf-8", "replace")) if skill else {}
        version = meta.get("metadata", {}).get("version") if isinstance(meta.get("metadata"), dict) else None
        if version:
            out.add(f"{t['name']}@{version}")
    return out


FILE = re.compile(r"^file (\S+) (\d+) ([0-9a-f]{64})$")


def parse_record(path: Path) -> dict:
    """The record's header fields, `exit` as an int, and `files`: (path, size, sha256) of each `file` line, in order."""
    text = path.read_text(encoding="utf-8", errors="replace")
    rec = frontmatter_of(text)
    rec["exit"] = int(rec["exit"]) if rec.get("exit", "").isdigit() else rec.get("exit")
    body = text.split("\n---\n", 1)[1] if "\n---\n" in text else ""
    rec["files"] = [(m.group(1), int(m.group(2)), m.group(3)) for m in map(FILE.match, body.splitlines()) if m]
    return rec


def hub_problems(dataset_dir: Path, results_dir: Path) -> list[str]:
    """The reasons this dataset's version cannot be published: its tag exists, its tool is not in the shed,
    or its record is missing, failed, of another recipe, or names files the Hub does not hold exactly."""
    name = dataset_dir.name
    meta = frontmatter(dataset_dir / "SKILL.md")["metadata"]
    version, tool, repo = meta["version"], meta["tool"], f"{hub_org()}/{name}"
    api, problems = f"https://huggingface.co/api/datasets/{repo}", []
    refs = hub_get(f"{api}/refs") or {}
    if f"v{version}" in {t["name"] for t in refs.get("tags", [])}:
        problems.append(f"v{version} is already on the Hub")
    if tool not in shed_catalogue():
        problems.append(f"{tool} is not in the toolshed")
    rel = f"results/{name}/{version}.txt"
    path = results_dir / name / f"{version}.txt"
    if not path.is_file():
        return problems + [f"{rel} is missing"]
    found = scan(path.read_text(encoding="utf-8", errors="replace"))
    if found:
        problems.append(f"{rel} holds what looks like a credential ({', '.join(found)})")
    rec = parse_record(path)
    if rec["exit"] != 0:
        problems.append(f"the record's exit is {rec['exit']}")
    if rec.get("tool") != tool:
        problems.append(f"the record's tool {rec.get('tool')} is not the skill's {tool}")
    tree = tree_hash(dataset_dir / "recipe")
    if rec.get("tree") != tree:
        problems.append(f"the record's tree {rec.get('tree')} is not the recipe's {tree}; build and test the committed recipe")
    commit = rec.get("commit", "")
    # ponytail: one page of the tree (1000 files); a longer listing reads as files missing, add the Link header's pages then
    listing = hub_get(f"{api}/tree/{commit}?recursive=true") if re.match(r"^[0-9a-f]{40}$", commit) else None
    if listing is None:
        return problems + [f"the record's commit {commit} is not on {repo}"]
    hub = {f["path"]: (f["size"], f.get("lfs", {}).get("oid")) for f in listing
           if f.get("type") == "file" and f["path"] not in ("README.md", ".gitattributes")}  # the card and the Hub's own
    recorded = {p: (size, sha) for p, size, sha in rec["files"]}
    for p in sorted(set(hub) | set(recorded)):
        if p not in hub:
            problems.append(f"{p} is not on the Hub")
        elif p not in recorded:
            problems.append(f"{p} is not in the record")
        elif hub[p][1] is None:
            problems.append(f"{p} is not in LFS on the Hub, so its sha256 cannot be checked")
        elif hub[p] != recorded[p]:
            problems.append(f"{p} differs from the Hub")
    return problems


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    one = p.add_mutually_exclusive_group(required=True)
    one.add_argument("dataset", nargs="?", type=Path)
    one.add_argument("--hub", type=Path, metavar="DATASET_DIR")
    one.add_argument("--tree", type=Path, metavar="DATASET_DIR")
    one.add_argument("--candidate", type=Path, metavar="DATASET_DIR")
    one.add_argument("--scan", type=Path, metavar="FILE")
    args = p.parse_args()
    if args.scan:
        found = scan(args.scan.read_text(encoding="utf-8", errors="replace"))
        if found:
            print(f"{args.scan} holds what looks like a credential ({', '.join(found)})", file=sys.stderr)
        return 1 if found else 0
    if args.tree or args.candidate:
        tree = tree_hash((args.tree or args.candidate) / "recipe")
        print(tree if args.tree else f"candidate-{tree}")
        return 0
    d = args.dataset or args.hub
    reasons = rules(d)
    if args.hub and not reasons:  # the shed and the Hub are asked only about a directory that keeps the rules
        reasons = hub_problems(d, d.resolve().parents[1] / "results")
    for reason in reasons:
        print(f"datasets/{d.name}: {reason}")
    return 1 if reasons else 0


if __name__ == "__main__":
    sys.exit(main())
