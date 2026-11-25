# CI-generated `CATALOG.md`: Design

Status: draft 2026-11-25, for brineylab/datasets#29. Small change. Calls left to the builder are marked **(call)**.

## Why

Agents (flyloft turns, laptop agents, notebooks) currently have to read or inline every `datasets/*/SKILL.md` frontmatter to learn what datasets exist. A single compact, always-current `CATALOG.md` at the repository root lets any agent discover every published dataset via a local clone or one raw GitHub URL fetch without installing a CLI or MCP server.

## Goals, non-goals, anti-goals

- **Goals:** Generate `CATALOG.md` at repo root from `datasets/*/SKILL.md` frontmatter and `results/<name>/<version>.txt` via GitHub Actions on push to `main` (plus `workflow_dispatch`), and point `README.md`, `AGENTS.md`, and `CONTRIBUTING.md` to it.
- **Non-goals:** Adding new frontmatter fields (e.g. `metadata.summary`), listing superseded versions, modifying `docs/VISION.md` or `docs/DESIGN.md`, or changing PR checks in `.github/workflows/datasets.yml`.
- **Anti-goals:** Editing or enforcing `CATALOG.md` in dataset PRs (causes merge conflicts across concurrent PRs), granting `contents: write` to PR workflows, or hardcoding `brineylab` in `scripts/` or `.github/`.

## Constraints

- `scripts/catalog.py` runs on Python 3.8+ with the standard library alone (`python3 -I`) and reads the Hub org from `hub.toml` via `check.hub_org()`.
- `.github/workflows/datasets.yml` stays `permissions: contents: read`.
- `main` currently has no branch protection or rulesets and defaults to read-only workflow tokens, so `.github/workflows/catalog.yml` declares `permissions: contents: write` to push with `GITHUB_TOKEN` (no PAT needed; would need a bypass or PR step if `main` later requires PRs).
- Table cells escape `|` and collapse newlines so prose cannot break Markdown tables.

## Approaches

1. **Standalone `scripts/catalog.py` + dedicated `.github/workflows/catalog.yml` (picked):** Reuses `check.frontmatter`, `check.parse_record`, and `check.hub_org`. Keeps `datasets.yml` strictly read-only for untrusted PRs, keeps `scripts/check.py` single-purpose (flyloft copies `check.py` onto its host), and lets `unittest discover tests` test generation directly.
2. **`--catalog` mode in `scripts/check.py` + second job in `.github/workflows/datasets.yml`:** Fewer files, but mixes PR validation with `main` write permissions in one workflow and expands `check.py` beyond validation.
3. **Inline Python inside `.github/workflows/catalog.yml`:** No new script in `scripts/`, but cannot be unit-tested or run locally and duplicates `check.py`'s parsers.

## Decided

- Use `SKILL.md`'s `description` frontmatter as-is (lossless, no extra metadata to maintain, avoids brittle sentence-splitting).
- Render a compact 7-column Markdown table: `Dataset`, `Version`, `Entries`, `Size`, `License`, `Tools`, `Description`, with `Dataset` linking to `datasets/<name>/SKILL.md` and `Version` linking to `https://huggingface.co/datasets/<org>/<name>/tree/v<version>`.
- Build with Approach 1 (`scripts/catalog.py` + `.github/workflows/catalog.yml`).

## Builder calls

- **Published filter (call):** Include a dataset iff `datasets/<name>/SKILL.md` parses with a `metadata.version` and `results/<name>/<version>.txt` exists with `exit == 0`, sorted alphabetically by name.
- **Formatting (call):** `Entries` formats `metadata.count` + `metadata.unit` to 3 significant digits (`300 pairs`, `22.9k structures`, `542k structures`, `1.19M pairs`, or `—` when absent); `Size` sums byte sizes from `file` lines in `results/<name>/<version>.txt` in decimal SI (`B`, `KB`, `MB`, `GB`, `TB`, or `—` if no `file` lines).
- **CLI (call):** `python3 -I scripts/catalog.py` writes Markdown to stdout; `--write` writes `CATALOG.md` at `check.ROOT`.
- **Workflow (call):** Triggers on `push` to `main` (paths: `datasets/*/SKILL.md`, `results/*/*.txt`, `hub.toml`, `scripts/catalog.py`, `scripts/check.py`, `.github/workflows/catalog.yml`) and `workflow_dispatch`; `concurrency: { group: catalog, cancel-in-progress: false }`; commits as `github-actions[bot]` (`Update CATALOG.md`) only when `CATALOG.md` changes.
- **Initial file (call):** Commit the initial generated `CATALOG.md` in this PR so reviewers see the rendered output immediately; future dataset PRs never touch it.
- **Docs (call):** Update `README.md` (`Finding a dataset` with `CATALOG.md` and raw GitHub URL), `AGENTS.md` (Layout and Commands), and `CONTRIBUTING.md` (note that `CATALOG.md` is CI-generated on `main`).
