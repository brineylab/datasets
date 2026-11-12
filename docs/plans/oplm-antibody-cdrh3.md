# `oplm-antibody-cdrh3` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `brineylab/oplm-antibody-cdrh3` v1.0.0. It holds a heavy-chain CDR3-identity holdout at 80%, v1's held-out files unchanged, and four screened train sets (AntiRef90, 92, 94 and 96 clusters with AntiRef99 members). Then run briney/oplm#78's four decay branches on it and report.

**Architecture:** Two repositories, then the cluster.
1. **brineylab/datasets.** One recipe, `datasets/oplm-antibody-cdrh3/recipe/build`, copied from `oplm-antibody-sequences` and extended. It is a single `python3 -I` program in `datascience@1.2.0`, cooked by hand on bcr as v1 was.
2. **CoreWeave.** The sweep reuses `~/projects/oplm/mup_redo/overfit.sh`, extended with `AB_SET=antiref90|92|94|96`. Nothing in briney/oplm's source changes.

**Tech Stack:** Python 3.12, DuckDB, pyarrow, polars, ANARCII 2.0.8 (all in `datascience@1.2.0`, nothing new); OPLM `antibody_cdr3` eval at main ≥ f28661e; Slurm on bcr and CoreWeave; W&B project `oplm-170M-overfit`.

**Spec:** `docs/superpowers/specs/2026-11-12-oplm-antibody-cdrh3-design.md` in this worktree (branch `oplm-antibody-cdrh3-design`). Read it first; §5 (steps), §6 (test) and §8 (OPLM) are binding. Also read v1's `datasets/oplm-antibody-sequences/{SKILL.md,recipe/build,recipe/test}`: the new recipe extends them.

## Global Constraints

**Datasets repository** (its `AGENTS.md`, binding):
- Bytes on the Hub, never in git. A recipe never pip-installs.
- Variants are datasets: copy the sibling's directory, change what differs.
- The skill's frontmatter is `name`, `description`, `metadata.version: 1.0.0`, `metadata.tools: datascience@1.2.0`, `metadata.license: cc-by-4.0`.
- The test judges the real output, from footers and samples.
- A commit message is one sentence stating the behavior, ending with the session's attribution line.
- Merge with `gh pr merge --merge` after review by someone other than the builder; then `scripts/promote`.
- Ask the human before every push, PR, Hub upload or promote: these are outward-facing.

**Source:** v1's two Zenodo files with v1's sizes and MD5s (in v1's `SOURCE`). Build on bcr: Zenodo is slow to CoreWeave.

**Parameters** (`params.toml`):
```toml
pulled = "2026-11-09"
seed = 1           # v1's holdout, unchanged
heldout = 5000
cdrh3_seed = 2
cdrh3_heldout = 5000
screen_max = 0.03  # build stops if the screen removes more than this share of AntiRef99 train sequences
shard_rows = 1000000
limit = 0
```

**Definitions** (spec §5.2–5.3, exact):
- `near(a, b)`: `levenshtein(a, b) <= floor(0.2 * max(len(a), len(b)))`.
- Window: `sequence[len(sequence) // 2:]`.
- Anchored candidates: every window substring of 3–40 residues immediately preceded by `C` and immediately followed by a match of `[WF]G.G`.
- A train sequence is screened out if either:
  - one of its anchored candidates is `near` a held-out CDR3; or
  - it has no anchored candidate, and the semi-global edit distance of a held-out CDR3 `q` against its window is at most `floor(0.25 * len(q))`.
- Eval CDR3: residues whose `cdr_mask_aa` digit is `3`.

**v1 files, byte-identical** (sha256 of v1.0.0):
- `eval_singletons.parquet`: `f28027d3b65fc11e1ac790674d5be1885775973c072da9dfd4e4e91899648552`
- `eval_gte2.parquet`: `862f73fe8c1faadcf98c50c5b6c83742dac6e6fc36c1b1331ee4896e6ee28c99`
- `test_singletons.parquet`: `cc6381e9e0fedb8c447925c9d369ef57e219237ab61f60055166b27ed8688758`
- `test_gte2.parquet`: `9456f11b468f016492fc58f03817de55a8b385879a73ded08ee50a92073aa9d5`

**Output:**
- **Held-out files.** v1's four, plus `eval_cdrh3.parquet` and `test_cdrh3.parquet`, each with v1's columns (`sequence_id`, `sequence`, `locus`, `cdr_mask_aa`).
- **Train folders.** `antiref{90,92,94,96}/train/shard-%05d.parquet`, each with columns `sequence_id`, `sequence`, `member_ids`, `member_sequences`:
  - 1,000,000-row shards, row groups of 10,000, zstd;
  - clusters in the order `md5('1:' || <level id>)`;
  - members ordered representative first, then by `md5('1:' || antiref99)`;
  - when the screen removed the representative, the first surviving member leads the row and supplies `sequence_id` and `sequence`.

**OPLM side:**
- Runs use `overfit.sh decay 140000 25` with `AB=1.5`.
- Run with `PATH=~/venvs/oplm-f28661e/bin:$PATH`.
- Four nodes per run.
- `admin_override` only after the PI approves it at launch. Memory `cluster-qos-override.md` covers small jobs only.

## Review Focus

1. **A short or `nan`-bearing CDR3.**
   - The ANARCII CDR3 of a candidate can be under 5 residues; it must be rejected, not held out.
   - Train sequences contain literal lowercase `nan`. The screen must treat them as ordinary characters, and must not crash on lowercase or on a window with no `C`.
   - Pinned by Task 1's self-check cases `anchored("")`, `anchored("nan")` and `near("", "")`.
2. **A cluster whose representative and all members were screened.** The row is dropped, not written with empty lists. OPLM's loader rejects empty member lists. Pinned by Task 3's self-check on `promote()`.
3. **A coarse-level representative that was not screened but is not its own first member.** This means the nesting broke. The build must stop with the IDs, not silently promote. Pinned by Task 3's self-check.
4. **Mutually near CDR3s between `eval_cdrh3` and `test_cdrh3`.** The 80% walk spans both files, so no CDR3 in one file is near a CDR3 in the other. Pinned by the test (Task 4), which checks all pairs across both files.
5. **Proxy rounding.** Coarse folders have few shards, so "1/35 of shards" is not 1/35 of the rows. The proxy must hold `round(rows / 35)` rows exactly, from whole shards plus one sliced shard. Pinned by Task 6's check.

---

### Task 1: The CDR3 matching core (brineylab/datasets)

**Files:**
- Create: `datasets/oplm-antibody-cdrh3/`, by copying `datasets/oplm-antibody-sequences/` (SKILL.md, `recipe/build`, `recipe/test`, `recipe/params.toml`).
- Modify: `datasets/oplm-antibody-cdrh3/recipe/build`: add the matching helpers below and a `selfcheck()` that runs first on every invocation, before any download.
- Modify: `datasets/oplm-antibody-cdrh3/recipe/params.toml`: the Global Constraints values.

**Interfaces:**
- **Produces**, in `recipe/build`:
  - `levenshtein(a: str, b: str) -> int`
  - `near(a: str, b: str) -> bool`
  - `anchored(sequence: str) -> list[str]`: distinct candidates, any order.
  - `semiglobal_within(query: str, window: str, k: int) -> bool`: Sellers' algorithm. True iff some substring of `window` is within `k` edits of `query`.
  - `class PieceIndex`:
    - `add(query: str, qid: int) -> None`: splits `query` into `floor(0.25 * len(query)) + 1` contiguous pieces of near-equal length and indexes each piece to `qid`;
    - `candidates(text: str) -> set[int]`: the qids having any piece as an exact substring of `text`;
    - `match(cand: str) -> int | None`: the smallest qid whose query is `near` `cand`, among `candidates(cand)`.
  - `selfcheck() -> None`
  - `recipe/build --selfcheck` runs `selfcheck()` and exits 0.
- **Pigeonhole guarantee:** if `near(q, c)`, then `c` contains one of `q`'s pieces exactly. `near` allows at most `floor(0.2 * max) <= floor(0.25 * len(q))` edits whenever the lengths are within reach.

- [ ] **Step 1: Write `selfcheck()` first.** It is assert-based and uses v1's `KNOWN` heavy chain, whose CDR3 is `ARSPYSSSWPGYYYYYYGMDV` (21 residues, so the bound is 4):
  ```python
  q = "ARSPYSSSWPGYYYYYYGMDV"
  assert levenshtein("kitten", "sitting") == 3
  assert near(q, q) and near(q, "ARSPYSSSWPGYYYYYYGMDV"[:-1] + "I")
  assert near(q, "GRSPYSASWPGYYAYYYGMDI")          # 4 substitutions
  assert not near(q, "GRSQYSASWQGYYAYYYGMDI")          # 6 substitutions
  assert not near("ARDYYYYYGMDV", "ARGGGSDYYYYYGMDVTT")
  assert near("", "") and anchored("") == [] and anchored("nan") == []
  assert q in anchored(KNOWN[0])
  w = KNOWN[0][len(KNOWN[0]) // 2:]
  assert semiglobal_within(q, w, 5) and not semiglobal_within("WWWWWWWWWW", w, 2)
  idx = PieceIndex(); idx.add(q, 7)
  assert idx.match(q) == 7 and idx.match("GRSPYSASWPGYYAYYYGMDI") == 7
  assert idx.match("ARDYYYYYGMDV") is None
  ```
  Every assertion must hold by the definitions; recheck each edit count by hand before running. Correct a wrong case, never the definition.
- [ ] **Step 2: Run it and see it fail.**
  - Run: `podman run --rm -v "$PWD":/w -w /w ghcr.io/brineylab/toolshed/datascience:1.2.0 datasets/oplm-antibody-cdrh3/recipe/build --selfcheck`
  - Expected: `NameError` on `levenshtein`.
- [ ] **Step 3: Implement the helpers.**
  - `levenshtein`: plain DP.
  - `anchored`: `re.finditer("C", window)` start positions × `re.finditer("(?=[WF]G.G)", window)` end positions, keeping lengths 3–40.
  - `PieceIndex`: a `dict[str, set[int]]` plus the set of piece lengths, so `candidates` enumerates only substrings of those lengths.
- [ ] **Step 4: Run it again and see it pass.**
  - Same command. Expected: exit 0, no output.
- [ ] **Step 5: Commit.**
  - `git commit -m "oplm-antibody-cdrh3 starts from oplm-antibody-sequences and matches CDR3s at 80% identity by a pigeonhole index, with a self-check"`

### Task 2: The heavy CDR3 holdout and the screen

**Files:**
- Modify: `datasets/oplm-antibody-cdrh3/recipe/build`.

**Interfaces:**
- **Consumes:** Task 1's helpers, and v1's `stage`, `cdr_mask`, `heldout_sets`, `order`, `connect` (unchanged).
- **Produces:**
  - `cdrh3_heldout(work: Path, seed: int, n: int) -> dict[str, list[dict]]`, keyed `eval_cdrh3` and `test_cdrh3`, with rows in v1's held-out schema.
  - `.work/heldout.parquet`: one `antiref90` column holding v1's 20,000 IDs plus the new 10,000.
  - `screen(work: Path, queries: list[str], cap: float) -> None`: writes `.work/screened.parquet` with columns `antiref99` (string) and `qid` (int32), and prints:
    - `screen removed: <n> of <total> (<pct>%)`
    - `screen cdr3s over 1000: <n>`
    - `screen largest: <n>`

    If `n / total > cap`, it exits 1 with `screen removed <pct>% > <cap*100>%`.

- [ ] **Step 1: Write `cdrh3_heldout`.**
  - Candidates are AntiRef90 representatives not in v1's held-out set, both strata together, walked in `md5('<cdrh3_seed>:' || antiref90)` order.
  - Number them in pools of 12,000 with the `Anarcii` instance v1 uses.
  - Keep a candidate when:
    - `chain_type == "H"`;
    - `cdr_mask` is not `None`;
    - its CDR3 has at least 5 residues;
    - `PieceIndex.match(cdr3)` against the CDR3s kept so far is `None`. Add each kept CDR3 to the index.
  - The first `n` kept are eval, the next `n` test, with `locus = "IGH"`.
  - Print `cdrh3 candidates tried: <n>` and `cdrh3 rejected near: <n>`.
  - If candidates run out, exit 1 as v1 does.
- [ ] **Step 2: Write `screen`.**
  - Input: the distinct `antiref99` of manifest rows outside every held-out AntiRef90 cluster, joined to their sequences. Have DuckDB write them as `cpus` parquet parts under `.work/screen_in/`.
  - Run a `multiprocessing.Pool(cpus)` over the parts. Each worker:
    - builds one `PieceIndex` over the queries;
    - for each sequence, takes `anchored(seq)` and matches each candidate; or, with none, runs `semiglobal_within(q, window, len(q) // 4)` for each `q` in `idx.candidates(window)`;
    - writes its `(antiref99, qid)` hits.
  - Concatenate the hits into `screened.parquet`, then print the counts and enforce the cap.
- [ ] **Step 3: Wire them into the main flow after v1's held-out stage,** each skipped when its output exists:
  - write `eval_cdrh3.parquet` and `test_cdrh3.parquet`;
  - extend `heldout.parquet`;
  - `screen(work, [cdr3 of every eval_cdrh3 and test_cdrh3 row], params["screen_max"])`.
- [ ] **Step 4: Dry run of stages 1–3 on bcr.**
  - Locally set `limit = 3000000`, `heldout = 200`, `cdrh3_heldout = 200`, never committed.
  - If v1's `.work/` downloads still exist on bcr, hard-link the two `.gz` files into `<out>/.work/` first; `download()` trusts files of the right size.
  - Run: `sbatch --partition=cpu --cpus-per-task=32 --mem=256G --time=03:00:00 --wrap "srun --container-image=ghcr.io#brineylab/toolshed/datascience:1.2.0 --container-mounts=<repo>,<out> <repo>/datasets/oplm-antibody-cdrh3/recipe/build <out>"`.
  - Expected: the self-check passes, then the `cdrh3` and `screen` lines print, with `screen removed` under 3%. The train stage that follows is still v1's until Task 3 replaces it; ignore its output.
- [ ] **Step 5: Measure screen throughput** from the dry run (sequences per second per CPU) and extrapolate to about 316M sequences on 32 CPUs.
  - If the extrapolation exceeds 3 hours, move the anchored match into DuckDB: explode pieces and candidates, join on equal strings, then `levenshtein()`. Keep the Python path for unanchored sequences.
  - Record the measured rate in the commit message.
- [ ] **Step 6: Commit.**
  - `git commit -m "oplm-antibody-cdrh3 holds out 10,000 heavy chains with mutually distinct CDR3s and screens every AntiRef99 train sequence against them"`

### Task 3: The four train sets

**Files:**
- Modify: `datasets/oplm-antibody-cdrh3/recipe/build`: replace v1's `train()` and `clusters()`; drop the `antiref99/train` output.

**Interfaces:**
- **Consumes:** `.work/heldout.parquet` and `.work/screened.parquet` (Task 2).
- **Produces:**
  - `clusters(reader: pa.RecordBatchReader, level: str) -> Iterator[pa.RecordBatch]`. Input rows are `(<level>, antiref99, sequence, rep_removed: bool)`, sorted by `order(level), level, (antiref99 = level) DESC, order('antiref99')`. It yields v1's train schema.
  - `promote(level_id: str, first_member: str, rep_removed: bool) -> str`: returns the row's `sequence_id`, or exits 1 with `<level> representative <id> is not among its own AntiRef99 members` when `not rep_removed and first_member != level_id`.
  - `train(work: Path, shard_rows: int) -> None`: writes `antiref{90,92,94,96}/train/`, then prints `rows <level>/train: <n>` and `members <level>/train: <total> mean <x.xx>`. It exits 1 if the four member totals differ. The build checks this as it writes, because recounting about 300M member IDs is too slow for the test.

- [ ] **Step 1: Extend `selfcheck()`:**
  ```python
  assert promote("A", "A", False) == "A"
  assert promote("A", "B", True) == "B"
  try: promote("A", "B", False); raise AssertionError("nesting break passed")
  except SystemExit: pass
  ```
- [ ] **Step 2: Run `--selfcheck` and see it fail** (`NameError: promote`).
- [ ] **Step 3: Implement.**
  - Kept rows are manifest rows outside `heldout.parquet` and whose `antiref99` is not in `screened.parquet`.
  - `rep_removed` is `<level> IN (SELECT antiref99 FROM screened)`, plus the v1 held-out exclusion.
  - A cluster with no kept rows produces nothing, so dropped clusters vanish without special-casing.
  - Use one sort and a streaming group per level, as v1's comment requires (an ordered `list()` spilled 90 GB).
- [ ] **Step 4: Run `--selfcheck`;** expect exit 0. Then rerun the Task 2 dry run.
  - Expected: four folders, and four `members` lines with the same total.
- [ ] **Step 5: Commit.**
  - `git commit -m "oplm-antibody-cdrh3 writes AntiRef90, 92, 94 and 96 clusters of the screened AntiRef99 sequences, promoting a surviving member when the screen took the representative"`

### Task 4: The test

**Files:**
- Modify: `datasets/oplm-antibody-cdrh3/recipe/test`.

**Interfaces:**
- **Consumes:** the output layout in Global Constraints. Its `near` and anchored candidates are reimplemented independently here; it must not import the build.
- **Produces:** exit 0 iff the output is a version, printing one line per failure and `ok` last.

- [ ] **Step 1: Extend v1's test** with these checks:
  - `HELDOUT` is v1's four files plus `eval_cdrh3` and `test_cdrh3`, with `cdrh3_heldout` rows each.
  - `TRAIN_COLUMNS` covers the four `antiref{90,92,94,96}` folders, with v1's member checks unchanged. A promoted row's `sequence_id` and `sequence` are its first member's, so `member_ids[0] == sequence_id` still holds.
  - v1's four files match the Global Constraints sha256 values.
  - Every `*_cdrh3` row is `IGH`, with a CDR3 of at least 5 residues.
  - No two CDR3s across `eval_cdrh3` and `test_cdrh3` are near. Check in DuckDB over a table `c(id, cdr3)` of all 10,000:
    ```sql
    SELECT a.id, b.id FROM c a JOIN c b ON a.id < b.id
      AND abs(length(a.cdr3) - length(b.cdr3)) <= greatest(length(a.cdr3), length(b.cdr3)) // 5
    WHERE levenshtein(a.cdr3, b.cdr3) <= greatest(length(a.cdr3), length(b.cdr3)) // 5
    ```
    Expect zero rows. Integer `// 5` is `floor(0.2 * x)`.
  - **The screen holds on a sample.** Take the first 1,000 rows of shard 0 of each folder. For each member, take its anchored candidates (regex in the test), cross-join them in DuckDB with the 10,000 held-out CDR3s, and apply the same `levenshtein` predicate. Expect zero rows. Members with no anchored candidate are checked with a semi-global edit distance (a small Sellers function in the test) within `len(q) // 4`.
  - Train row floors: `FLOOR = {level: 0 ...}` until Task 5 sets them.
- [ ] **Step 2: Run the test on the Task 3 dry-run output.**
  - Expected: `ok`, except the sha256 check. A `limit` dry run holds different v1 files, so the sha256 check is skipped when `params["limit"]` is non-zero; print `skip sha256 (limit)`.
- [ ] **Step 3: Mutation checks**, each restored afterwards:
  - overwrite one `test_cdrh3` row's `sequence` and `cdr_mask_aa` with an `eval_cdrh3` row's; expect the near-pairs check to fail;
  - append a row to shard 0 of `antiref92/train` whose member is the `eval_cdrh3` heavy chain itself; expect the screen check to fail.
- [ ] **Step 4: Commit.**
  - `git commit -m "oplm-antibody-cdrh3's test checks v1's files by hash, the CDR3 holdout's 80% separation, and the screen on sampled members"`

### Task 5: Full build on bcr, skill, record, PR

**Files:**
- Modify: `datasets/oplm-antibody-cdrh3/recipe/test` (`FLOOR`).
- Modify: `datasets/oplm-antibody-cdrh3/SKILL.md`.
- Create: `results/oplm-antibody-cdrh3/1.0.0.txt`.

- [ ] **Step 1: Run the full build by hand on bcr** with the committed `params.toml`, using Task 2's sbatch line with `--time=12:00:00`.
  - Expected: `ok` from the test, except the floors, which are still 0.
  - Record per-stage wall time, `sacct -j <job> -o MaxRSS,Elapsed`, `.work/` disk and output size.
  - If the screen's tripwire fires, stop and bring the `screen` lines to the human. Do not raise `screen_max`.
- [ ] **Step 2: Set `FLOOR`** to `int(0.9 * rows)` per folder from the printed `rows` lines, and rerun the test. Expected: `ok`.
- [ ] **Step 3: Write `SKILL.md`** with v1's sections:
  - **Frontmatter:** as in Global Constraints. `description` says the dataset is a heavy-chain CDR3-identity holdout at 80% plus four AntiRef cluster levels with AntiRef99 members, for OPLM's antibody anneal.
  - **Files:** the six held-out files and four folders. State that a row's `sequence` is AntiRef's representative unless the screen removed it.
  - **Reading it:** always `sample_members: true`.
  - **Recipe:** the spec's §5, with the parameters.
  - **The test.**
  - **Compute:** Step 1's measurements.
  - **Gotchas:**
    - the D3 exception: four levels in one dataset, by the PI's decision of 2026-11-12;
    - light chains are held out by AntiRef90 cluster only;
    - the screen is CDR3-only, so V-gene and framework similarity remain;
    - no screen against uniref70 or deepclust70;
    - the screen over-removes slightly by design.
- [ ] **Step 4: Check.**
  - Run: `python3 -I scripts/check.py datasets/oplm-antibody-cdrh3`. Expected: exit 0.
- [ ] **Step 5: Push, record and commit (ask the human first).**
  - In `datascience:1.2.0` on bcr, push: `python3 -I scripts/push oplm-antibody-cdrh3 <out>`.
  - Write the record: `scripts/record oplm-antibody-cdrh3 <commit> 0 "sbatch --partition=cpu --cpus-per-task=32 --mem=256G --time=12:00:00" bcr.scripps.edu <started> < <build+test+push output>`.
  - `git commit -m "oplm-antibody-cdrh3 1.0.0's record: its candidate passed on bcr"`
- [ ] **Step 6: Open the PR (ask the human first).**
  - The branch carries the design commits, this plan and the dataset. The PR body links briney/oplm#78.
  - A reviewer other than the builder approves; then `gh pr merge --merge`, pull `main`, and `scripts/promote oplm-antibody-cdrh3 1.0.0`.
  - Expected: tag `v1.0.0` on `brineylab/oplm-antibody-cdrh3`.

### Task 6: Proxy data and the standalone baselines (CoreWeave)

**Files** (cluster, not git; back up before editing):
- Create: `~/projects/oplm/mup_redo/ab_proxy.py`
- Modify: `~/projects/oplm/mup_redo/ab_cdr3_eval/cdr3match.py`: take the shard folder and the output prefix as arguments.

**Interfaces:**
- **Produces:**
  - `python ab_proxy.py <src train folder> <dst folder> <divisor>`:
    - symlinks whole shards in order;
    - writes the remainder as one sliced shard, so the destination holds exactly `round(rows / divisor)` rows;
    - prints `rows <n>`, then `residues_per_row <x.x>`. That's the mean over rows of the mean member length, the same quantity as `overfit.sh`'s `115.6`, which v1's shard 0 gave as 115.62.
  - Proxies live at `/mnt/data/briney/oplm-data/proxy-1of35/cdrh3/antiref{90,92,94,96}/train`.

- [ ] **Step 1: Download the dataset.**
  - Run: `snapshot_download("brineylab/oplm-antibody-cdrh3", repo_type="dataset", revision="v1.0.0")` with `~/venvs/oplm-a140e98/bin/python`, into `/mnt/data/briney/oplm-data/hf/oplm-antibody-cdrh3`.
  - Check the file count and sizes against the Hub.
- [ ] **Step 2: Write `ab_proxy.py`** with an assert-based check at the bottom (`if __name__ == "__main__" and sys.argv[1] == "--selfcheck"`): build a 2.5-shard toy folder of 10-row shards in a temp dir, proxy it with divisor 2, and assert 12 rows (`round(25 / 2)`) with every `sequence_id` drawn from the first rows in order.
  - Run `--selfcheck`; expect `ok`. Then build the four proxies and keep the printed `rows` and `residues_per_row`.
- [ ] **Step 3: Score the baselines on `eval_cdrh3` standalone.**
  - Use `ab_cdr3_eval/run_eval_split.py` with `SPLITS=eval_cdrh3` and the data dir set to the new dataset.
  - Checkpoints: `decay140k-u25/output/checkpoint-175000` (protein-only control) and `decay140k-u25-ab1.5/output/checkpoint-175000` (old v1 train set).
  - Run it as a 1-GPU sbatch modelled on `ab_cdr3_seen_unseen.sbatch`. `admin_override` is allowed for this small job under the standing rule.
  - Expected: JSON lines with `loss_heavy`, `accuracy_heavy`.

### Task 7: The sweep (CoreWeave)

**Files:**
- Modify: `~/projects/oplm/mup_redo/overfit.sh` (back up as `overfit.sh.bak-pre-cdrh3`).

**Interfaces:**
- **Consumes:** Task 6's proxy folders and their `residues_per_row`.
- **Produces:** `AB=1.5 AB_SET=antiref90 bash overfit.sh decay 140000 25` creates run `overfit-decay140k-u25-ab1.5-ar90` (`-ar92`, `-ar94`, `-ar96` likewise). Without `AB_SET`, behaviour is byte-for-byte as today.

- [ ] **Step 1: Edit `overfit.sh`:**
  - `ABH3=/mnt/data/briney/oplm-data/hf/oplm-antibody-cdrh3`.
  - In `decay`, when `AB_SET` is set:
    - skip the v1 symlinking;
    - add `-ar${AB_SET#antiref}` to the name;
    - pass the proxy path and its `residues_per_row` to `write_config`.
  - In `write_config`, the antibody source key stays `antiref96`, so W&B keys match the earlier runs:
    - its `path` is the proxy folder;
    - its row weight uses the passed `residues_per_row` in place of `115.6`;
    - when the extra argument is set, add eval `antibody_cdrh3` with `path: $ABH3/eval_cdrh3.parquet`, `type: antibody_cdr3`, `every: {steps: 1000}`, `metrics: [loss_heavy, accuracy_heavy, perplexity_heavy]`.
- [ ] **Step 2: Dry-run all four** with `DRY=1`.
  - Diff each `config.yaml` against `decay140k-u25-ab1.5/config.yaml`. Expected differences, and only these:
    - the antiref96 `path`;
    - the three row fractions, which change slightly with `residues_per_row`;
    - the new eval entry;
    - names.
- [ ] **Step 3: Ask the PI to approve `admin_override`** for four 4-node, about 10-hour runs. Then submit the four and move each to `admin_override` with `sudo -n scontrol update JobId=<id> QOS=admin_override`.
- [ ] **Step 4: Check the start of each run.**
  - Check the first eval at step 141k in W&B: `eval/antibody_cdrh3/loss_heavy` must exist.
  - Grep each log for `Traceback`. Expected: none.

### Task 8: Analysis and report (briney/oplm#78)

- [ ] **Step 1: Pull the step-175k results** for the four runs from W&B: every `eval/*` key and P@L. Put them beside the control and old ab1.5 numbers from Task 6.
- [ ] **Step 2: Seen/unseen split on v1's eval files**, per run.
  - Run `cdr3match.py <proxy folder> <prefix>` for each of the four proxies.
  - Score each run's checkpoint on its own seen and unseen files with `run_eval_split.py`, as one 1-GPU job.
- [ ] **Step 3: Apply the spec's decision rule (§8):**
  - prefer the lowest `eval_cdrh3` heavy loss, provided v1-file unseen loss is no worse;
  - flag any protein CE more than 0.002 off the control rather than choosing it.
- [ ] **Step 4: Post the tables and the recommendation to #78** (`board comment 78`), naming the W&B run IDs, the dataset tag and the jobs. Leave the production choice to the PI.
- [ ] **Step 5: Update memory `antibody-cdr3-eval.md`** with the runs, the result, and the `AB_SET` usage.
