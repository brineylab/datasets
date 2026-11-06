# AGENTS.md

The lab's datasets: a recipe per dataset, versions on the Hugging Face Hub, one prose skill per dataset. A dataset is a Hub dataset repository whose files a recipe wrote and whose versions are tags; this repository holds the recipe, the skill, and the record of each version, never the bytes. The same `snapshot_download` line reads a dataset from a notebook, a laptop, a Slurm job, and a flyloft campaign.

Read before changing anything:

- `docs/VISION.md`: what the repository is for and what it is not.
- `docs/DESIGN.md`: what a dataset is, the repository, the workflow, review; and what flyloft needs from here.
- `docs/plans/datasets-a.md`: the plan that built the repository, and `docs/plans/datasets-a2.md`, which revises it. Work them task by task; their Global Constraints are binding.
- `CONTRIBUTING.md`, once it exists: how to add a dataset, step by step. The rules below are the binding summary.

`docs/VISION.md` and `docs/DESIGN.md` are approved by the lab. Do not edit them unless asked to. If the work shows the design is wrong, stop and say so.

This repository mirrors the toolshed ([brineylab/toolshed](https://github.com/brineylab/toolshed)): the layout, the scripts' names and style, the record, the check-and-promote workflow, the review. When this file or the design says "as the toolshed's", read the shed's `AGENTS.md`, `CONTRIBUTING.md`, and `scripts/` and do the same thing here, with the Hub in place of the registry.

## Layout

```
datasets/<name>/SKILL.md          the skill: what the dataset is, its files, the line that loads it, its recipe, its compute
datasets/<name>/recipe/build      the recipe's program (a split recipe's first): reads params.toml beside it, writes the version's files into its argument
datasets/<name>/recipe/params.toml
datasets/<name>/recipe/test       checks an output directory is a version; exit 0 iff it is
results/<name>/<version>.txt      the record of a candidate's test
hub.toml                          the Hub org this repository publishes to
scripts/check.py                  a dataset directory's rules, its record, and whether its version is published
scripts/push <name> <output dir>          upload the cook's output and the card to the Hub's candidate branch; prints the manifest and `commit:`
scripts/record <name> <commit> <exit> <runner> <host> <started> < output   write a record from the test's and push's output
scripts/promote <name> <version>          tag the record's commit on the Hub, never moving a tag; delete the candidate branch
tests/                            unit tests of the scripts, with the Hub stubbed
.github/workflows/datasets.yml    check and promote, on hosted runners
```

## Commands

```bash
python3 -I -m unittest discover tests                 # the scripts' unit tests: the only tests this repository has
python3 -I scripts/check.py datasets/<name>           # a dataset's rules; add --hub to check its version, candidate, and record against the Hub
datasets/<name>/recipe/build <out> && datasets/<name>/recipe/test <out> && python3 -I scripts/push <name> <out>   # inside the recipe's tool image, as CONTRIBUTING.md writes out
```

## Rules a dataset must keep

- **The bytes are on the Hub, never in git.** A version is a tag `v<version>` on `<org>/<name>`; its files are parquet (sharded when large), under 200 GB each, under 100k files.
- **A recipe is instructions; the cook runs it.** `recipe/build` reads `recipe/params.toml` and writes a version's files into one directory. One job is the default; a split recipe is several programs in `recipe/` and prose stating their order, each one's tool, and each one's compute. It names no runtime: it runs inside its tools' images, under `srun` on a cluster or `podman run` on a laptop. Nothing here runs, schedules, or orders a recipe.
- **The recipe's tools are toolshed tools**, named in the skill's `metadata.tools` as one or more `name@version` separated by single spaces; the one that pushes is built without `HF_HUB_OFFLINE` and holds `huggingface_hub` and python3 (the shed's `datascience`). A recipe never pip-installs.
- **The identity is the recipe's inputs.** The skill states the source, its pull date, every parameter, and the tools' versions in prose; the record carries them. A change to any of them is a new version; a change that makes the result incomparable (a threshold, a species) is a new dataset.
- **Variants are datasets, versions are time.** Copy the sibling's directory, change what differs, give it its own name.
- **Any change under `datasets/<name>/` bumps `metadata.version`**, prose included. A published tag is never moved; readers always name a version.
- **The skill's frontmatter is `name`, `description`, `metadata.version`, `metadata.tools`, `metadata.license`.** Everything else is prose. No declared schemas.
- **The test judges the real output**, in seconds, from footers and samples: the files, the schema, row counts above the recipe's floor, the recipe's own checks. It is not the recipe on a slice.
- **Never a credential in the repository**: `scripts/push` reads `HF_TOKEN` and never prints it; `scripts/push`, `scripts/record`, and `check` refuse what looks like one.

## Rules the repository keeps

- `scripts/check.py` and `scripts/record` run with the Python standard library alone (`python3 -I`): flyloft's host runs them, and so do login nodes. `scripts/push` and `scripts/promote` need `huggingface_hub`, which `datascience` and CI have.
- Nothing in `scripts/` or `.github/` names the lab: the org comes from `hub.toml`, so a fork with its own org is its own catalogue and store.
- CI runs on hosted runners and never runs a recipe or pulls a dataset. Whoever cooks a dataset tests its output where it was built, files it with `scripts/push`, and commits the record; nobody can claim a version exists without one.
- Every dataset is reviewed by someone other than its builder before it merges.

## What not to build

A dataset exists because a question needed it. Do not add datasets, parameters, or scripts speculatively. Not here: loaders, feature stores, streaming, analysis helpers, a `datasets` command. The items in `docs/DESIGN.md` §6 are deferred until their stated trigger; do not build them early.

## Commits and pull requests

A commit message is one sentence stating the behavior. A dataset arrives as a pull request whose record is committed with it. Merge with a merge commit (`gh pr merge --merge`): `promote` runs on the merge commit, and flyloft watches that check.
