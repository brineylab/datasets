# Adding a dataset

A dataset is built because a question needs it. Before you start, `ls datasets`: a sibling may be one parameter away from what you need, and a variant of it is a copy with that parameter changed and its own name.

## The layout

Copy the nearest sibling's directory to `datasets/<name>/`, where `<name>` is lowercase words joined by hyphens, and change what differs.

- `SKILL.md`: the skill, the dataset's whole description.
- `recipe/build`: the program. It reads `recipe/params.toml` beside it and writes the version's files into the directory it is given.
- `recipe/params.toml`: every parameter the recipe reads.
- `recipe/test`: checks an output directory; exits 0 iff it holds a version of this dataset.

The record, `results/<name>/<version>.txt`, is written by `scripts/record` after you cook and push; it lives outside the dataset's directory so committing it leaves the recipe alone.

## The conventions

- **The bytes are on the Hub, never in git.** Parquet where the data is tabular, sharded when a file would pass a few GB; every file under 200 GB, under 100k files. Anything the recipe stages for itself goes under a directory whose name starts with `.` (`<out>/.work/`), which `scripts/push` leaves out.
- **A recipe is instructions, and whoever cooks it runs it**, anywhere: a laptop, a Slurm job, a flyloft campaign. Nothing in this repository runs, schedules, or orders a recipe; it files, records, checks, and promotes what a cook made.
- **A recipe runs in toolshed images and never pip-installs**, so its tools are pinned and the same images serve every cook. Name them in the skill's `metadata.tools`. Most recipes need only `datascience`, the shed's general-purpose image: the scientific Python stack, abstar, mmseqs2, DIAMOND, `huggingface_hub`, and git, with network access.
- **The identity is the recipe's inputs**: the source and its pull date, every parameter, the tools' versions. The skill states them in prose and the record carries them. A change to any of them is a new version; a change that makes the result incomparable (a threshold, a species) is a new dataset.
- **Never a credential in the repository.** `scripts/push` reads `HF_TOKEN` from the environment and never prints it; `scripts/push`, `scripts/record`, and `check` refuse a file that holds what looks like one.

## The skill

Frontmatter has five fields a machine reads:

```markdown
---
name: <name>
description: "<what it is, and when to reach for it>"
metadata:
  version: 1.0.0
  tools: datascience@1.0.0
  license: <the Hub's license id, e.g. mit or cc-by-4.0>
---
```

`name` is the directory's and the Hub repository's, `description` is the catalogue line, `metadata.version` is the Hub tag (`v` prefixed), `metadata.tools` is one or more `name@version` separated by single spaces (a string: the skill format's `metadata` maps strings to strings), and `metadata.license` goes on the card. Then the body, in this order: `Hub:` (the repository and tag), `## Files` (each file, its rows, its columns), `## Reading it` (the `snapshot_download` line at this version), `## Recipe` (the source, its pull date, every parameter, the tools, what the test checks), `## Compute` (CPUs, memory, hours, disk, measured), `## Gotchas`. The body is also the Hub's card. No declared schemas: prose.

## The recipe's shape

One job is the default: `recipe/build <out>` does everything, in one image, on one node. Split a recipe only when one job is wrong for it:

- **a very long step whose resumption matters** (days of annotation you would not redo because a later step failed), or
- **steps with different compute** (CPU clustering, then GPU embedding).

A split recipe is several programs in `recipe/` (`recipe/build` is the first) and prose in the skill stating their order, each one's tool, and each one's compute. Its record is one record: `metadata.tools` lists every tool its steps use, and the record's body holds each step's output in order. **Chaining datasets** is the other way to split: a recipe may start from another dataset's published version, read with `snapshot_download` at a named tag.

Whatever the shape, a recipe that stages its work under `<out>/.work/` and skips a stage already finished there resumes for free.

A recipe may read a `limit` from `params.toml` for a developer's dry run; the published version has none, or 0.

## The test

`recipe/test <out>` judges the real output: the files are there, each parses, the columns are the skill's, each split has at least the rows the recipe expects (a floor written in the test, about 90% of what the first full build gave), and whatever else the recipe knows (no id in two splits, no unannotated row). It runs in seconds on hundreds of GB, because it reads parquet footers and samples. It is not the recipe on a slice: the build is the real thing and the test judges it.

## Cooking it

Commit the dataset directory first: `scripts/push` names the candidate by the committed recipe's tree and refuses uncommitted or git-ignored changes under `datasets/<name>/`. Cook from a full clone; in a `git worktree`, `.git` points at the main repository, which a container must also mount or `push` cannot tell whether the recipe is committed.

**On a laptop**, for a small dataset, with podman, from the clone's root (`hf auth login` once beforehand; the token is read from its file, never typed or printed):

```bash
img=ghcr.io/brineylab/toolshed/datascience:1.0.0; out=$(mktemp -d); started=$(date -u +%FT%TZ)
run() { podman run --rm --pids-limit=-1 -e HF_TOKEN -v "$PWD":/work -v "$out":/out -w /work "$img" "$@"; }
run datasets/<name>/recipe/build /out
run datasets/<name>/recipe/test /out > "$out.test"; code=$?
if [ "$code" = 0 ]; then
  HF_TOKEN=$(< ~/.cache/huggingface/token) run python3 -I scripts/push <name> /out > "$out.push"
  cat "$out.test" "$out.push" | scripts/record <name> "$(sed -n 's/^commit: //p' "$out.push")" "$code" podman "$(hostname)" "$started"
fi
```

**On a Slurm cluster with pyxis**, from a clone on the login node, with `out` a directory on shared storage with room for the output and its staging. Pyxis passes your environment into the container, so export the token there, and never `HF_HUB_OFFLINE`, which stops the recipe's downloads and the push:

```bash
export HF_TOKEN=$(< ~/.cache/huggingface/token); out=<a directory on shared storage>; mkdir -p "$out"; started=$(date -u +%FT%TZ)
srun --partition=<p> --cpus-per-task=<n> --mem=<m> --time=<t> \
  --container-image=ghcr.io#brineylab/toolshed/datascience:1.0.0 \
  --container-mounts="$PWD":"$PWD","$out":"$out" --container-workdir="$PWD" \
  bash -c "echo host: \$(hostname -f) && datasets/<name>/recipe/build $out && datasets/<name>/recipe/test $out && python3 -I scripts/push <name> $out" > "$out.run" 2> "$out.err"
code=$?
[ "$code" = 0 ] && scripts/record <name> "$(sed -n 's/^commit: //p' "$out.run")" "$code" "srun --partition=<p> --cpus-per-task=<n> --mem=<m>" "$(sed -n 's/^host: //p' "$out.run")" "$started" < "$out.run"
```

On a laptop, `--pids-limit=-1` lifts podman's default of 2048 processes and threads per container, which abstar passes with a dozen worker processes: each starts polars' thread pools, sized to the machine. Mount `$out` and anything else the recipe reads (a shared data directory), or the job writes into the container's own filesystem, which goes with the job. The `host:` line is the compute node's, where the build and test ran. On coreweave-rtx6000, a CPU-only recipe takes `--partition=hpc-low`: a GPU node's spare CPUs, at most 32 CPUs and 240G. A failed build or test is fixed, never filed: when `code` is not 0, read `$out.err`, fix the recipe, commit, and cook again.

`scripts/push` uploads the output to the Hub's candidate branch, `candidate-<tree>` on `<org>/<name>`, replacing an earlier candidate of the same tree, writes the card from the skill, and prints one `file <path> <size> <sha256>` line per file and `commit: <sha>` last. `scripts/record` writes `results/<name>/<version>.txt` from that output. Commit it: `git add results/<name>/<version>.txt`.

## The record

The record's header names the Hub repository, the candidate branch and its head commit, the recipe's tree, the tools, the runner, the host, the start time, and the exit code; its body is the recipe's test output and push's manifest. `check` proves it on every pull request: the exit code is 0, the tree is the committed recipe's, the tools are the skill's, and the Hub's commit holds exactly the record's files with the record's sha256. Nobody can claim a version exists without one.

A change after cooking changes the tree, so cook, push, and record again. A prose-only change to the skill leaves the tree alone, but it still bumps the version: push the same output again (the Hub skips the files it holds, so only the card moves) and record the new version.

## Versions

Any change under `datasets/<name>/` bumps `metadata.version`, prose included. A published tag is never moved, and `check` refuses a pull request whose tag is already on the Hub. Readers always name a version, never `main`, which is a copy of the version last promoted, for the Hub's page.

## The pull request

1. Push your branch and open the pull request, the record committed in it.
2. `check` runs: the dataset's rules, an unpublished version, each tool in the toolshed at its version, and a record of a passing test whose files the Hub holds exactly.
3. Someone other than you reviews it, a critic agent included: does the skill describe the files the record lists and state the recipe's inputs; does the record show the test passed where the build ran; is the version new; are the tools the ones the record shows. They merge with a merge commit (`gh pr merge --merge`).
4. Whoever merged promotes it: pull `main`, then, from the clone's root,

   ```bash
   HF_TOKEN=$(< ~/.cache/huggingface/token) podman run --rm -e HF_TOKEN -v "$PWD":/work -w /work \
     ghcr.io/brineylab/toolshed/datascience:1.0.0 python3 -I scripts/promote <name> <version>
   ```

   It tags the record's commit `v<version>` on the Hub, gives `main` the version's files, and deletes the candidate branch; its last line says what it did. It refuses a record that is not on `origin/main`. Run it from a full clone, not a `git worktree`, whose `.git` points outside the mounted directory. CI holds no Hub token, so nothing is published until someone runs it.
