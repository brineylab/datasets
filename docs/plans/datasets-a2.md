# Datasets, Plan A2: Recipes Are Instructions, `datascience`, and `jaffe-paired`

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The toolshed holds `datascience@1.0.0`; this repository's scripts only file, record, check, and promote; its docs and `CONTRIBUTING.md` say a recipe is instructions any cook runs; and `hello@v1.0.0` and `jaffe-paired@v1.0.0` are on the Hub under `brineylab`, each built, tested, filed, reviewed by a critic, merged, and tagged.

**Architecture:** Replaces plan A's Tasks 5–7 (`docs/plans/datasets-a.md`); Tasks 1–4 stand as built (`1e6f722`), changed only where Task 3 below says. Task 1 is a toolshed contribution through the shed's own flow. Tasks 2–3 are one pull request here. Tasks 4 and 5 are a dataset pull request each, cooked in `datascience@1.0.0` (a laptop with podman for `hello`, coreweave-rtx6000's `hpc-low` partition under `srun` with pyxis for `jaffe-paired`) and filed with `scripts/push` and `scripts/record`.

**Tech Stack:** as plan A, less podman and srun in this repository's scripts and tests; the toolshed's `scripts/` for the image; abstar 0.9.0, mmseqs2, polars, and `huggingface_hub` inside the image for the recipes.

**Spec:** `docs/superpowers/specs/2026-11-05-recipes-tools-and-jaffe-paired-design.md` (the spec; cited below as "the spec §N"). Plan A and `docs/DESIGN.md` give the conventions this plan keeps.

## Global Constraints

- **Plan A's Global Constraints bind**, amended here: the frontmatter's `metadata.tool` is **`metadata.tools`**, one or more `name@MAJOR.MINOR.PATCH` separated by single spaces, as a string (the spec §5.2); the record's header `tool:` is **`tools:`**, the same string; `scripts/build` and `scripts/test` no longer exist; the credential scan runs in `push`, `record`, and `check`.
- **Where the work happens:** Task 1 in `~/git/toolshed` on branch `datascience`, one pull request on `brineylab/toolshed`. Tasks 2–3 in this repository on branch `recipes-are-instructions`, one pull request. Task 4 on branch `hello`, Task 5 on branch `jaffe-paired`, a pull request each. Never commit to `main`.
- **Stops for the PI:** before each `scripts/push` (toolshed: a public GHCR package; here: a public Hub repository), before each merge, and for every command on a CoreWeave login node, which the PI runs (the executor has no CoreWeave login). The executor writes the exact command and waits for its output.
- **Review:** each pull request is reviewed before merge by a fresh critic subagent given the diff, the record, and the review questions of the owning task; a critic counts as the reviewer (the spec §2). Merge with `gh pr merge --merge`.
- **Recipes run in `datascience@1.0.0`** (`ghcr.io/brineylab/toolshed/datascience:1.0.0`) and never pip-install. Compute for `jaffe-paired`: CPU only, coreweave-rtx6000, partition `hpc-low`, at most 32 CPUs and 240G (a GPU node's spare share).
- **Commits:** one sentence stating the behavior, ending with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Before each commit here: `python3 -I -m unittest discover tests` passes and `bash -n` passes on every bash script.

## Review Focus

1. **A push from a recipe with uncommitted or git-ignored changes** names a candidate tree nobody can reproduce: `push` refuses, naming `datasets/<name>`, before anything reaches the Hub. Pinned in Task 3.
2. **A push where `git status` itself fails** (no repository, no git, or git's "dubious ownership" refusal inside a container whose user differs from the checkout's owner): `push` refuses naming why, never proceeds as if clean; and `datascience` sets `safe.directory` so a real checkout works under pyxis and podman. Pinned in Tasks 3 and 1.
3. **A credential in `SKILL.md`**: the card goes public on the Hub at push, before any pull request's `check`, so `push` runs `check.rules` (which scans) first, as `build` did. Pinned in Task 3.
4. **`metadata.tools` with two tools, or a malformed list** (a comma, a double space): `check` validates each entry and checks each against the shed; `record` keeps every tool in its header (bash's `read` would split them). Pinned in Task 3.
5. **An output directory that is missing or holds no data files**: `push` refuses before creating the Hub repository, so an empty candidate never exists. Pinned in Task 3.

---

### Task 1: `datascience@1.0.0`, in the toolshed

**Files (in `~/git/toolshed`, branch `datascience`):**
- Create: `tools/datascience/Containerfile`, `tools/datascience/SKILL.md`, `tools/datascience/test/run.sh`, `tools/datascience/test/pairs.fasta`
- Modify: `docs/DESIGN.md` §1 (the bullet *Weights are in the image*), `AGENTS.md:45`, `CONTRIBUTING.md` (the convention *Weights are fetched at build time*)
- Create, after the test: `results/datascience/1.0.0.txt`

**Interfaces:**
- Produces: `ghcr.io/brineylab/toolshed/datascience:1.0.0`, on whose PATH are `python3` (3.12), `abstar`, `mmseqs`, `diamond`, `git`, and in whose Python are abstar 0.9.0, abutils 0.6.1, numpy, polars, pandas, pyarrow, duckdb, scipy, scikit-learn, biopython, huggingface_hub, datasets, matplotlib, seaborn. `HF_HUB_OFFLINE` unset. Tasks 4 and 5 run in it.

- [ ] **Step 1: The fixture.** abstar splits its input into chunks of 500 sequences (`chunksize: int = 500`, `abstar/core/abstar.py:371`) and runs chunks in a process pool, so the fixture holds 600 contigs: the first 300 barcodes of Jaffe et al.'s sample 1279049 with exactly one heavy and one light contig, taken in file order from `/tmp/claude-1000/-home-bryanbriney-git-datasets/afe7d74b-f169-4083-b5ec-a21ff2a72784/scratchpad/jaffe/filtered_contig.fasta` (if the scratchpad is gone, extract that sample's file from the figshare tarball of Task 5 Step 1). Expected: `grep -c '>' tools/datascience/test/pairs.fasta` prints `600`. The skill credits the source (figshare 19617633 v3, MIT).

- [ ] **Step 2: The test, `test/run.sh`** (bash, `set -euo pipefail`, writes only under `/tmp`, passes with `--network none`). In order, each failing the script on a wrong answer:
  1. `abstar run /toolshed/test/pairs.fasta /tmp/abstar --germline_database human -o parquet`; then `python3 -I -c` with polars reading the parquet: 600 rows; `sequence_vdj_aa` and `fwr1_aa`..`fwr4_aa` present; for every productive row `sequence_vdj_aa == fwr1_aa + cdr1_aa + fwr2_aa + cdr2_aa + fwr3_aa + cdr3_aa + fwr4_aa`; at least 570 rows productive.
  2. The heavy chains' `sequence_vdj_aa` written as FASTA, `mmseqs easy-cluster <fasta> /tmp/mm /tmp/mmtmp --min-seq-id 0.85 -c 0.8 --threads 2`; the number of clusters in `/tmp/mm_cluster.tsv` equals the count pinned after the first local run (write it into the script then; it is this binary's known answer).
  3. `diamond version` prints a line starting `diamond version 2.`.
  4. `python3 -I -c "import abstar, abutils, numpy, polars, pandas, pyarrow, duckdb, scipy, sklearn, Bio, huggingface_hub, datasets, matplotlib, seaborn"`; `abstar.__version__ == "0.9.0"`.
  5. `git config --system --get-all safe.directory` prints `*`; `[ -z "${HF_HUB_OFFLINE:-}" ]` (in the image, not the caller's: the test runs under `--network none` with podman, where the caller's environment does not pass).

- [ ] **Step 3: The `Containerfile`.** `FROM docker.io/library/python:3.12-slim-bookworm@sha256:<digest current at build time>`; `apt-get install --no-install-recommends git ca-certificates wget` then `rm -rf /var/lib/apt/lists/*`; `git config --system --add safe.directory '*'`; `pip install --no-cache-dir abstar==0.9.0 abutils==0.6.1` and the stack, every package `==` its version current at build time; `ln -s "$(python3 -c 'import abutils, os; print(os.path.dirname(abutils.__file__))')/binaries/mmseqs_linux_amd64" /usr/local/bin/mmseqs` (check it is executable); DIAMOND's `diamond-linux64.tar.gz` from its GitHub release at the version current at build time, its binary in `/usr/local/bin`; no `ENV HF_HUB_OFFLINE`, no `NVIDIA_*`; `COPY test /toolshed/test` last. The environment layers first, as the shed's CONTRIBUTING orders.

- [ ] **Step 4: `SKILL.md`**, per the shed's CONTRIBUTING: `name: datascience`, `metadata.version: 1.0.0`, description `"General-purpose data work: the scientific Python stack, abstar and abutils, mmseqs2, and DIAMOND, with network access. Reach for it to annotate, cluster, search, or reshape sequence data, and to run a brineylab/datasets recipe."`. Body: `Image:` line; `## Commands` (full command lines: `abstar run <fasta or dir> <project dir> --germline_database human -o parquet`, `mmseqs easy-cluster <fasta> <prefix> <tmp> --min-seq-id 0.85 -c 0.8`, `diamond blastp -d <db> -q <fasta> -o <tsv>`, `python3 <script>`); `## Inputs and outputs`; `## Compute` (CPU only; the fixture's wall time from the test); `## Running it` (the podman line and `srun --partition=hpc-low --container-image=ghcr.io#brineylab/toolshed/datascience:1.0.0 ...`); `## Gotchas`: a general-purpose image reaches the network and sets no `HF_HUB_OFFLINE`; pyxis passes the caller's environment, so a caller's `HF_HUB_OFFLINE=1` stops a recipe's downloads and its push; `mmseqs` is abutils' bundled binary, the one abstar runs; the fixture crosses abstar's 500-sequence chunk into its process pool, and does not reach `mmseqs_chunksize` (1,000,000).

- [ ] **Step 5: The shed's docs.** `docs/DESIGN.md` §1, after *Weights are in the image*, a bullet: **General-purpose images** (`datascience`, later `deeplearning`) hold an environment for the work between specialized tools, carry no weights, and are built without `HF_HUB_OFFLINE` because their work reaches the network (a dataset recipe downloads and pushes); their version moves when any package does, on a cadence rather than per package release. `AGENTS.md:45` and the CONTRIBUTING convention gain the clause "except a general-purpose image (DESIGN §1), which sets neither".

- [ ] **Step 6: Build and try it locally.** `git add tools/datascience docs AGENTS.md CONTRIBUTING.md && git commit` ("datascience 1.0.0: a general-purpose image for data work, with abstar, mmseqs2, and DIAMOND"); `scripts/build datascience`; `podman run --rm --network none <candidate> bash /toolshed/test/run.sh`. Expected: exit 0. Pin the cluster count (Step 2.2), amend the commit, rebuild, run again: exit 0.

- [ ] **Step 7: Push (stop: the PI confirms).** `scripts/push datascience`. Expected: exit 0, the candidate pullable with no login.

- [ ] **Step 8: Test where it will be used (the PI runs it).** On a coreweave-rtx6000 login node, in a clone of the toolshed on branch `datascience`: `scripts/test datascience srun --partition=hpc-low --cpus-per-task=4 --mem=16G --time=00:30:00`, then `git add results/datascience/1.0.0.txt && git commit -m "datascience 1.0.0's record: its candidate passed on coreweave-rtx6000" && git push`. Expected: `gpu: none`, exit 0, the record committed.

- [ ] **Step 9: Pull request, critic, merge.** `gh pr create --title "datascience 1.0.0"`; `check` passes; the critic answers the shed's review questions (CONTRIBUTING, *The pull request* step 3) and whether the docs change states the exception and its reason; the PI confirms; `gh pr merge --merge`; `promote` publishes. Expected: `podman run --rm ghcr.io/brineylab/toolshed/datascience:1.0.0 abstar --help` prints abstar's usage.

Tasks 2–3 do not need the image; work them while Step 8 waits on the PI.

### Task 2: This repository's docs say a recipe is instructions

**Files:**
- Modify: `docs/VISION.md` (*What it is not*), `docs/DESIGN.md` (§1, §2 the D4 bullet and the frontmatter, §3 layout and *The candidate* and *Guards*, §4, §5 *Building*, §6, §7), `AGENTS.md`, `README.md`, `docs/plans/datasets-a.md` (one line under the header)

**Interfaces:**
- Produces: the docs Tasks 3–5 are checked against.

- [ ] **Step 1: VISION.** Add to *What it is not*: "Not a runner: a recipe is instructions, and whoever cooks it runs it anywhere, as one job or several; this repository holds recipes and records and files results." The CI line stands.

- [ ] **Step 2: DESIGN.** Edit to the spec, paragraph by paragraph: §2's recipe bullet to the spec §2's *shape of a recipe* (one job by default; a split recipe is several programs and prose stating order, tools, compute; `recipe/build` is a single-job recipe's program or a split recipe's first); the example frontmatter's `tool: abstar@1.0.0` to `tools: datascience@1.0.0` and the five-field sentence to `metadata.tools`; §3's layout without `scripts/build` and `scripts/test`, `scripts/push <name> <output dir>`; *The candidate* without `.built` and the skip: the cook runs the recipe and its test anywhere, `push` refuses uncommitted inputs and names the candidate by the committed tree; *Guards*: `push`, `record`, `check` scan; §4 rewritten as "General-purpose tools" (the spec §6, two sentences, pointing at the shed's `datascience`); §5 *Building*: flyloft cooks the recipe as its skill says, then calls `push` and `record`; §6: the deferred multi-job recipe is now allowed, its record format deferred (the spec §5.3); §7: a line "Revised 2026-11-05 by the spec (D4 amended: a recipe names its tools; one job is the default, not the rule)". Status line: the date and the spec's path.

- [ ] **Step 3: AGENTS.md, README.md, plan A.** AGENTS: `docs/plans/datasets-a2.md` beside plan A in *Read before*; layout and commands without `build`/`test`, `push <name> <output dir>`; the rules *A recipe is one program* → the spec's shape rule, *The recipe's tool* → `metadata.tools`, *Never a credential* → `push`, `record`, `check`. README: "CI never builds, tests, or pulls a dataset" → "CI checks records and never pulls a dataset; whoever builds a dataset tests it and files it." Plan A, under its header: "> Tasks 5–7 are replaced by `datasets-a2.md`; Task 8 waits for flyloft's plan B."

- [ ] **Step 4: Commit.** `git checkout -b recipes-are-instructions`, `git add docs AGENTS.md README.md`, commit "The docs say a recipe is instructions any cook runs, naming its tools, and this repository only files, records, checks, and promotes".

### Task 3: The scripts file a result and never run a recipe

**Files:**
- Delete: `scripts/build`, `scripts/test`, `tests/stubs/podman`, `tests/test_scripts.py`
- Create: `tests/test_record.py` (the two record tests from `tests/test_scripts.py`, adapted)
- Modify: `scripts/push`, `scripts/check.py` (`TOOL` use in `rules`, `hub_problems`, the docstring), `scripts/record:17,23`, `tests/test_push_promote.py`, `tests/test_check.py`, `tests/test_check_hub.py`, `tests/fixtures/datasets/tiny/SKILL.md`, `tests/fixtures/results/tiny/1.0.0.txt`

**Interfaces:**
- Consumes: `check.rules(dataset_dir) -> list[str]`, `check.tree_hash(recipe_dir) -> str`, `check.frontmatter(path) -> dict`, `check.hub_org() -> str` (plan A Task 1).
- Produces: `scripts/push <name> <output dir>` (stdout as plan A: `file` lines then `commit:`); `scripts/record` writing header `tools: <the skill's metadata.tools>`; `check.py` reading `metadata.tools` and record `tools`.

- [ ] **Step 1: The fixtures and the failing tests.** `tiny/SKILL.md`: `tools: hello@1.0.1`; the tiny record: `tools: hello@1.0.1`. In `tests/test_push_promote.py` the output is a plain directory `self.out` holding `train.txt`, `eval.txt`, and `.work/source.csv`, no `.built`; push runs as `scripts/push tiny <self.out>`. Tests (exact stderr text):
  - `test_push_creates_the_repo_replaces_the_candidate_and_prints_the_manifest`: as now, with the new argument; uploaded `["eval.txt", "train.txt"]`.
  - `test_push_names_the_candidate_by_the_committed_tree`: the branch created is `candidate-` + `git rev-parse HEAD:datasets/tiny/recipe`.
  - `test_push_refuses_uncommitted_changes`: append a line to `datasets/tiny/recipe/params.toml`; exit 1; stderr has `datasets/tiny has uncommitted changes; commit them first`; the fake Hub recorded no call.
  - `test_push_refuses_an_ignored_file_in_the_recipe`: a committed `.gitignore` of `*.tmp`, then `datasets/tiny/recipe/x.tmp`; exit 1, the same message.
  - `test_push_refuses_when_git_cannot_say_the_inputs_are_committed`: remove the temporary repository's `.git`; exit 1; stderr starts `cannot tell whether datasets/tiny is committed:`; no Hub call.
  - `test_push_refuses_a_skill_holding_a_credential`: commit `hf_` + 34 letters into `SKILL.md`; exit 1; stderr has `SKILL.md holds what looks like a credential (hf_)`; no Hub call.
  - `test_push_refuses_an_output_with_no_files`: an empty directory, and a path that does not exist; exit 1; stderr has `<path> holds no files to push`; no Hub call.
  - Delete `test_push_refuses_an_output_built_with_another_tool` and `test_push_refuses_an_output_that_was_not_built`.
  
  In `tests/test_check.py`: the frontmatter test reads `metadata.tools`; `test_two_tools_separated_by_a_space_pass` (`tools: hello@1.0.1 datascience@1.0.0` → no reasons); `test_a_malformed_tools_list_is_refused` (each of `hello@1.0.1,datascience@1.0.0`, `hello@1.0.1  datascience@1.0.0`, empty → the reason `tools '<value>' is not one or more toolshed tools' name@MAJOR.MINOR.PATCH separated by single spaces`). In `tests/test_check_hub.py`: the record test becomes `the record's tools hello@1.0.0 is not the skill's hello@1.0.1`; `test_a_second_tool_the_shed_lacks_is_refused` (`tools: hello@1.0.1 nothere@1.0.0` → `nothere@1.0.0 is not in the toolshed`, and no line for `hello@1.0.1`). In `tests/test_record.py`: the two record tests, header line `tools: hello@1.0.1`, plus `test_record_keeps_every_tool` (skill `tools: hello@1.0.1 datascience@1.0.0` → header `tools: hello@1.0.1 datascience@1.0.0`).

- [ ] **Step 2: Run them.** `python3 -I -m unittest discover tests`. Expected: the new and changed tests fail (push takes `<outroot>`, `tool` keys), and nothing errors on import.

- [ ] **Step 3: The code.**
  - `scripts/push`: usage `scripts/push <name> <output dir>`; in order: `check.rules(dataset)` non-empty → print each, exit 1; the guard `subprocess.run(["git", "status", "--porcelain", "--ignored", "--", f"datasets/{name}"], cwd=check.ROOT, capture_output=True, text=True)`, where `OSError` or a non-zero exit → `cannot tell whether datasets/<name> is committed: <git's stderr, or the error>`, exit 1, and non-empty stdout → `datasets/<name> has uncommitted changes; commit them first`, exit 1; the output's data files (the existing non-dot filter) empty or the path not a directory → `<path> holds no files to push`, exit 1; then `HF_TOKEN` and the upload as now. Drop `.built` and its tool check; the docstring says the cook ran the recipe into the directory.
  - `scripts/check.py`: `tools = meta.get("tools", "")`; valid iff `tools` and every `t in tools.split(" ")` matches `TOOL`; `hub_problems` loops the catalogue check per tool and compares `rec.get("tools")` with the string.
  - `scripts/record`: print `m['version'], check.hub_org(), m['tools']` and `read -r version org tools`, so `tools` takes the rest of the line; the header line `tools: %s`.
  - Delete the four files; `git rm` them.

- [ ] **Step 4: Run them.** `python3 -I -m unittest discover tests` and `bash -n scripts/record scripts/changed-datasets`. Expected: OK, every test passing; `grep -rn "scripts/build\|scripts/test\|\.built\|'tool'\|\"tool\"" scripts tests .github` prints nothing.

- [ ] **Step 5: Commit, pull request, critic, merge.** Commit "The scripts file a result and never run a recipe: push takes the cook's output directory and refuses uncommitted inputs, and a skill names its tools". Push the branch, `gh pr create --title "Recipes are instructions"`; `check` passes (unit tests; no dataset changed). The critic reviews Tasks 2–3 against the spec §5 and this plan's Review Focus 1–5. The PI confirms; `gh pr merge --merge`.

### Task 4: `hello@1.0.0` and `CONTRIBUTING.md`

**Files:**
- Create: `datasets/hello/SKILL.md`, `datasets/hello/recipe/build`, `datasets/hello/recipe/params.toml`, `datasets/hello/recipe/test`, `CONTRIBUTING.md`
- Create, after the build: `results/hello/1.0.0.txt`

**Interfaces:**
- Consumes: `datascience@1.0.0` (Task 1); `scripts/push <name> <output dir>`, `scripts/record` (Task 3).
- Produces: `brineylab/hello` at `v1.0.0`, as plan A Task 6's Interfaces: three parquet files, columns `pair_id`, `sequence_heavy`, `sequence_light`, 240, 30, 30 rows.

- [ ] **Step 1: The dataset**, as plan A Task 6 Step 1, with `tools: datascience@1.0.0` and `license: mit`. Commit on branch `hello`: "hello: 300 synthetic antibody pairs, the repository's smoke dataset".

- [ ] **Step 2: Cook it on the laptop, test it, file it (stop before the push: the PI confirms).** The PI has signed in once with `hf auth login`; the token is read from its file, never printed:

  ```bash
  img=ghcr.io/brineylab/toolshed/datascience:1.0.0; out=$(mktemp -d); started=$(date -u +%FT%TZ)
  run() { podman run --rm -e HF_TOKEN -v "$PWD":/work -v "$out":/out -w /work "$img" "$@"; }
  run datasets/hello/recipe/build /out
  run datasets/hello/recipe/test /out > "$out.test"; code=$?
  HF_TOKEN=$(< ~/.cache/huggingface/token) run python3 -I scripts/push hello /out > "$out.push"
  cat "$out.test" "$out.push" | scripts/record hello "$(sed -n 's/^commit: //p' "$out.push")" "$code" podman "$(hostname)" "$started"
  git add results/hello/1.0.0.txt && git commit -m "hello 1.0.0's record: its candidate passed on a laptop"
  ```

  Expected: `code` 0; `brineylab/hello` has `candidate-<tree>` with the three files and the card; `python3 -I scripts/check.py --hub datasets/hello` prints nothing and exits 0.

- [ ] **Step 3: `CONTRIBUTING.md`**, the shed's transposed (the spec §5.5): the layout; the conventions with their why; a recipe is instructions and the cook runs it anywhere; choosing its shape (one job by default; split for a long step worth resuming or for steps of different compute; chaining datasets; what a split recipe's prose states); cooking it, as commands not scripts: Step 2's podman lines, and on a cluster `srun --partition=<p> --cpus-per-task=<n> --mem=<m> --time=<t> --container-image=ghcr.io#brineylab/toolshed/<tool>:<version> --container-mounts=<data>:<data> bash -c '<recipe/build> <out> && <recipe/test> <out>'`, then `scripts/push` (in the image, `HF_TOKEN` exported, never `HF_HUB_OFFLINE`) and `scripts/record` on the login node; the record and what it must show; versions; the pull request and the review questions (does the skill describe the files the record lists and state the recipe's inputs; does the record show the test passed where the build ran; is the version new; are the tools the ones the record shows), reviewed by someone other than the builder, a critic agent included. Commit with the record.

- [ ] **Step 4: Pull request, critic, merge, promote.** `gh pr create --title "hello 1.0.0"`; `check` passes; the critic answers the review questions and checks CONTRIBUTING's commands against Step 2 as run; the PI confirms; `gh pr merge --merge`. Expected: `promote` tags `v1.0.0`; the candidate branch is gone.

- [ ] **Step 5: Read it back.** `python3 -c "from huggingface_hub import snapshot_download; import polars as pl; p = snapshot_download('brineylab/hello', repo_type='dataset', revision='v1.0.0'); print(pl.read_parquet(p + '/train.parquet').shape)"`. Expected: `(240, 3)`.

### Task 5: `jaffe-paired@1.0.0`

**Files:**
- Create: `datasets/jaffe-paired/SKILL.md`, `datasets/jaffe-paired/recipe/build`, `datasets/jaffe-paired/recipe/params.toml`, `datasets/jaffe-paired/recipe/test`
- Create, after the build: `results/jaffe-paired/1.0.0.txt`

**Interfaces:**
- Consumes: `datascience@1.0.0`; Task 3's scripts; Task 4's CONTRIBUTING commands.
- Produces: `brineylab/jaffe-paired` at `v1.0.0`: `train.parquet`, `eval.parquet`, `test.parquet`, the columns of the spec §4 *The files*.

- [ ] **Step 1: `params.toml`**, the spec §4's names and values: `pulled = "<the download date>"`, `article = 19617633`, `article_version = 3`, `germline_database = "human"`, `identity = 0.85`, `coverage = 0.8`, `train_identity = 0.95`, `split = [0.96, 0.02, 0.02]`, `seed = 1`; and `limit = 0`, the number of samples for a developer's dry run, 0 for all, as DESIGN §3 allows (the published version has 0; the skill says so). The two source files, by figshare file id, size, and MD5, are constants in `recipe/build`: `34846953`, `11941014666`, `4d87c4da2d407ba95180be2cb1c91044`; `34846938`, `1981`, `3ccae335a8a03b5a771dc0eae97f7af6`.

- [ ] **Step 2: `recipe/build <out>`** (`#!/usr/bin/env -S python3 -I`, polars, subprocess for `tar`, `abstar`, `mmseqs`), the spec §4's steps 1–8, staging under `<out>/.work/` so a rerun resumes a finished stage. Fixed here: the download from `https://figshare.com/ndownloader/files/<id>`, MD5 checked, refusing a mismatch with `<file id>: MD5 <got> is not <expected>`; the FASTA extracted with `tar -xzf <tarball> -C <dir> --wildcards 'test_data/*/outs/per_sample_outs/*/vdj_b/filtered_contig.fasta'`; `abstar run` per sample's FASTA with `--germline_database` and `-o parquet`, `sample` set from its path; the droplet barcode `sequence_id.split("_", 1)[0]`; heavy is `locus == "IGH"`, light `IGK` or `IGL`; the counts printed as `dropped <shape>: <n>` lines (shapes `1H2L`, `2H2L`, `2H1L`, `1H0L`, `0H1L`, others by the same pattern) and `dropped unproductive: <n>`; columns renamed `<field>:0` for heavy and `<field>:1` for light; the joined sequence `sequence_vdj_aa:0 + sequence_vdj_aa:1` written as FASTA named by `pair_id`; clustering `mmseqs easy-cluster <fasta> <prefix> <tmp> --min-seq-id <identity> -c <coverage> --cov-mode 0 --threads <os.cpu_count()>` (the spec §7 leaves the command to the builder; `--cov-mode 0` is coverage of both sequences), the representative read from `<prefix>_cluster.tsv`'s first column; the split: shuffle the sorted 85% representatives with `random.Random(seed)`, assign whole clusters in order to train until its pairs reach `split[0]` of all, then eval to `split[1]`, then test; train re-clustered at `train_identity`, keeping representatives with `cluster_95`; the files written with polars. It prints `pairs: <n>` per split last.

- [ ] **Step 3: `recipe/test <out>`**, the spec §4 *The test*, reading with `polars.scan_parquet` (footers) and samples; the floors as constants, 1 until Step 6 sets them. Its failure lines name the check and the first offending `pair_id`.

- [ ] **Step 4: `SKILL.md`**, the spec §4 *The skill*: `metadata.tools: datascience@1.0.0`, `metadata.license: mit`; the files and columns; `## Reading it` with the `snapshot_download` line at `v1.0.0`; `## Recipe` (the article, its version, the DOI `10.6084/m9.figshare.19617633.v3`, the pull date, every parameter, abstar 0.9.0 and why `sequence_vdj_aa`); `## Compute` from Step 6; `## Gotchas` (barcodes unique only within a sample; the droplet rule drops about 9%; `donor` makes a held-out-donor variant possible as another dataset).

- [ ] **Step 5: A dry run on the laptop.** In a scratch copy of the repository (never committed), `limit = 2`, then Task 4 Step 2's `run` lines for `jaffe-paired`. Expected: the build ends with `pairs:` lines, the test exits 0 (floors still at 1), the `dropped` lines match sample 1279049's shapes in the spec §4. Fix and commit until it does. Commit on branch `jaffe-paired`: "jaffe-paired: paired human antibodies from Jaffe et al. 2022, clustered at 85% and split, train reduced at 95%".

- [ ] **Step 6: The first build on coreweave-rtx6000 (the PI runs it), then the floors.** In a clone on branch `jaffe-paired` under the PI's home, `out` a directory with 100 GB free:

  ```bash
  srun --partition=hpc-low --cpus-per-task=32 --mem=200G --time=12:00:00 \
    --container-image=ghcr.io#brineylab/toolshed/datascience:1.0.0 --container-mounts=/mnt/data:/mnt/data \
    bash -c "datasets/jaffe-paired/recipe/build $out" 2>&1 | tee build-1.log
  ```

  Expected: `pairs:` lines. The PI sends the log, `sacct -j <id> --format=Elapsed,MaxRSS,AllocCPUS`, and `du -sh $out`. Set each split's floor to 90% of its count, rounded down to two significant figures, in `recipe/test`; fill `## Compute`; commit "jaffe-paired's test holds each split to 90% of its first build". The tree changed, so the build is run again.

- [ ] **Step 7: The build of record, its test, the push, the record (the PI runs it; stop before the push).** On the login node, with `HF_TOKEN` exported from the PI's token file:

  ```bash
  started=$(date -u +%FT%TZ)
  srun --partition=hpc-low --cpus-per-task=32 --mem=200G --time=12:00:00 \
    --container-image=ghcr.io#brineylab/toolshed/datascience:1.0.0 --container-mounts=/mnt/data:/mnt/data \
    bash -c "datasets/jaffe-paired/recipe/build $out2 && datasets/jaffe-paired/recipe/test $out2 && python3 -I scripts/push jaffe-paired $out2" > run.out 2>&1
  code=$?   # non-zero: stop and send run.out; a failed build or test is fixed, never filed
  scripts/record jaffe-paired "$(sed -n 's/^commit: //p' run.out)" "$code" "srun --partition=hpc-low --cpus-per-task=32 --mem=200G" "$(hostname -f)" "$started" < run.out
  git add results/jaffe-paired/1.0.0.txt && git commit -m "jaffe-paired 1.0.0's record: its candidate passed on coreweave-rtx6000" && git push
  ```

  Expected: `code` 0, `run.out` ending with the `file` lines and `commit:`; `python3 -I scripts/check.py --hub datasets/jaffe-paired` exits 0.

- [ ] **Step 8: Pull request, critic, merge, promote.** As Task 4 Step 4. The critic also checks the record's `dropped` and `pairs` lines against the skill, `params.toml` against the skill's prose, and that the test asserts every line of the spec §4 *The test*.

- [ ] **Step 9: Read it back.** `snapshot_download("brineylab/jaffe-paired", repo_type="dataset", revision="v1.0.0")`, then each split's `polars.scan_parquet(...).select(pl.len()).collect()`. Expected: the record's `pairs:` counts. Update `docs/DESIGN.md`'s status line with the date and the counts, commit on `main` through a pull request.
