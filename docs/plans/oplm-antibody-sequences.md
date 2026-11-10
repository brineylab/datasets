# `oplm-antibody-sequences` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `brineylab/oplm-antibody-sequences` v1.0.0, a pilot dataset for OPLM's anneal built from AntiRef v2022.12.14. It has two train sets and four CDR-masked eval and test files.

**Architecture:** Two repositories, in order.
1. **brineylab/toolshed.** `datascience` 1.2.0 adds ANARCII 2.0.8 and CPU torch to 1.1.0. It is built, tested, and promoted by the shed's own workflow.
2. **brineylab/datasets.** One recipe, `datasets/oplm-antibody-sequences/recipe/build`, a single `python3 -I` program like jaffe-paired's:
   - downloads two Zenodo files;
   - stages them as parquet;
   - picks held-out AntiRef90 clusters (numbering their representatives with ANARCII);
   - writes the train shards with DuckDB and pyarrow.

   flyloft cooks it in a campaign: build, test, push, record, PR, critic, merge, promote.

**Tech Stack:** Python 3.12, DuckDB 2.0.0, pyarrow 26.0.1, ANARCII 2.0.8, torch (CPU wheel), podman, Hugging Face Hub, flyloft.

**Spec:** `docs/superpowers/specs/2026-11-09-oplm-antibody-sequences-design.md` (brineylab/datasets, branch `oplm-antibody-sequences`). Read it first. Its §5 (the files) and §6 (the steps) are binding.

## Global Constraints

**Toolshed** (its `AGENTS.md`):
- Every package and base image is pinned.
- The Containerfile ends with `COPY test /toolshed/test`.
- Any change under `tools/datascience/` bumps `metadata.version`, to `1.2.0`.
- No `HF_HUB_OFFLINE` in this general-purpose image.
- The test passes with `--network none`.
- The contributor builds with `scripts/build` from committed source. CI never builds.
- The tool merges with its record, after review by someone other than its builder, via `gh pr merge --merge`.

**Datasets** (its `AGENTS.md`):
- The bytes are on the Hub, never in git. Files are parquet, under 200 GB each, under 100k files.
- `recipe/build <out>` reads `recipe/params.toml` beside it and writes the version's files into `<out>`.
- A recipe never pip-installs.
- The skill's frontmatter is exactly `name`, `description`, `metadata.version` (`1.0.0`), `metadata.tools` (`datascience@1.2.0`), and `metadata.license` (`cc-by-4.0`).
- The test judges the real output in seconds, from footers and samples.
- Commit messages are one sentence stating the behavior, ending with the session's attribution lines.

**Source** (spec §4):
- `antiref_cluster-manifest.csv.gz` from record 7474336: 14,054,641,207 bytes, MD5 `18fcf6376702a2d23e2acdc32f1fd40a`.
- `antiref100.fasta.gz` from record 7474658: 18,496,427,276 bytes, MD5 `4a82d4be0c493377668fac9730aca866`.
- Both download from `https://zenodo.org/api/records/<record>/files/<file>/content`.

**Output** (spec §5):
- **Folders:** `antiref96/train/` and `antiref99/train/`, each holding `shard-%05d.parquet` files of 1,000,000 rows (the last fewer), row groups of 10,000, zstd.
- **Held-out files:** `eval_singletons.parquet`, `eval_gte2.parquet`, `test_singletons.parquet`, `test_gte2.parquet`, with `heldout` rows each (5,000 in the published version).
- **Columns:**
  - train96: `sequence_id`, `sequence`, `member_ids`, `member_sequences`, with the representative first in both lists;
  - train99: `sequence_id`, `sequence`;
  - eval/test: `sequence_id`, `sequence`, `locus`, `cdr_mask_aa`.
- **Values:**
  - `locus` is `IGH`, `IGK`, or `IGL`.
  - `cdr_mask_aa` is one digit per residue: `0` framework, `1` CDR1 (IMGT 27–38), `2` CDR2 (56–65), `3` CDR3 (105–117). An insertion takes its base position's region.
- **Seeded order:** `md5('<seed>:<id>')`, for the AntiRef90 walk and for both train sets.

**flyloft:** one tool per recipe. The build, test, and push run as one CPU run within the campaign's time limit. A resubmission cooks again from scratch.

## Review Focus

1. **ANARCII leaves residues unnumbered or extra** (a truncated FWR1, or a tail past FWR4). The candidate must be rejected, never given a mask of the wrong length. Pinned by Task 3's mask check and the test's length check.
2. **CDR3 insertions** (IMGT 111A, 112A …, common in long HCDR3s). They must be `3`, not dropped. Pinned by Task 3's known-answer sequence, which has a 21-residue CDR3 with insertions.
3. **A manifest ID with no sequence in the FASTA, or the reverse.** The build fails and names the count, rather than silently writing short clusters. Pinned in Task 3, step 4.
4. **A partial or corrupt download.** The MD5 refuses it, and a rerun downloads again instead of trusting the stage. Pinned in Task 3, step 4.
5. **A dry run with `limit`**, where a stratum has fewer candidates than `heldout`. The build fails with a message naming the stratum and the count, rather than writing short files the test then rejects for an unclear reason. Pinned in Task 3, step 5.

---

### Task 1: `datascience` 1.2.0 with ANARCII (brineylab/toolshed)

**Files:**
- Modify: `tools/datascience/Containerfile`: after the `pip install` line, add a CPU torch and ANARCII layer.
- Modify: `tools/datascience/test/run.sh`: add the ANARCII check before the import line.
- Modify: `tools/datascience/SKILL.md`: `metadata.version: 1.2.0`, the image tag `1.2.0` everywhere, ANARCII in the contents paragraph, one Commands example, and the Inputs and outputs line.

**Interfaces:**
- Produces: `ghcr.io/brineylab/toolshed/datascience:1.2.0`, in which `python3 -I -c "from anarcii import Anarcii"` works. `Anarcii(seq_type="antibody", mode="accuracy", cpu=True, ncpu=<n>).number({id: seq})` returns `{id: {"numbering": [((pos, ins), aa), ...], "chain_type": "H"|"K"|"L"|"F", ...}}`, with gaps as `"-"`.

- [ ] **Step 1: Write the failing test.** In `test/run.sh`, after the abstar block (which writes `$d/heavy.fasta`), add a Python heredoc that:
  - reads the abstar parquet again and takes the productive rows' `sequence_id`, `sequence_vdj_aa`, `locus`, and `cdr3_aa`;
  - numbers every `sequence_vdj_aa` with `Anarcii(seq_type="antibody", mode="accuracy", cpu=True, ncpu=2)`;
  - asserts each `chain_type` maps to the row's `locus` (`H`→`IGH`, `K`→`IGK`, `L`→`IGL`);
  - asserts the residues at IMGT 105–117, insertions included, joined in order, equal `cdr3_aa`.

  Print `anarcii: <agree> of <n> CDR3s agree with abstar`. Then pin the counts as `[[ ... ]]` known answers, as the mmseqs line pins 39. Run Step 2 once to read them.
- [ ] **Step 2: Run the test against 1.1.0 to see it fail.**
  - Run: `podman run --rm --network none ghcr.io/brineylab/toolshed/datascience:1.1.0 bash /toolshed/test/run.sh`. This uses the old image's test, so first copy the new `run.sh` in with `-v "$PWD/tools/datascience/test":/toolshed/test:ro`.
  - Expected: FAIL with `ModuleNotFoundError: No module named 'anarcii'`.
- [ ] **Step 3: Add the layer to the Containerfile.**

  ```
  RUN pip install --no-cache-dir torch==<pin> --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir anarcii==2.0.8 gemmi==<pin> msgpack==<pin> psutil==<pin> sortedcontainers==<pin>
  ```

  - Pin torch to the newest CPU wheel for cp312 on that index at build time. Pin ANARCII's other dependencies to what pip resolves.
  - Keep `numpy==2.5.4` unchanged; if torch's wheel refuses it, stop and report.
  - Add `anarcii` and `torch` to the test's final import line, with `assert anarcii.__version__ == '2.0.8'`.
- [ ] **Step 4: Build and run the test until it passes.**
  - Run: `scripts/build datascience`, then `podman run --rm --network none <candidate> bash /toolshed/test/run.sh`.
  - Expected: `anarcii: N of N CDR3s agree with abstar` and `ok`. If some CDR3s disagree, read them before pinning: a disagreement on an insertion means the IMGT handling is wrong, and the dataset's mask would inherit it.
- [ ] **Step 5: Update `SKILL.md`.**
  - Frontmatter: `metadata.version: 1.2.0`. Add ANARCII to `description`.
  - Image lines: `datascience:1.2.0`.
  - Contents paragraph: "ANARCII 2.0.8 (IMGT numbering of amino-acid antibody sequences; model weights inside the package) with CPU torch".
  - Commands: `python3 -I -c "from anarcii import Anarcii; print(Anarcii(seq_type='antibody', cpu=True).number({'q': 'QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYAMYWVRQAPGQRLEWMGWINARNGNTKYSQKFQGRVTITRDTSASTAYMELSSLRSEDTAVYYCARSPYSSSWPGYYYYYYGMDVWGQGTTVTVSS'})['q']['chain_type'])"`.
  - Inputs and outputs: one line describing ANARCII's return value, as in Interfaces above.
- [ ] **Step 6: Check and commit.**
  - Run: `python3 -I scripts/check.py tools/datascience`. Expected: exit 0.
  - `git commit -m "datascience 1.2.0 numbers amino-acid antibody sequences with ANARCII 2.0.8 on CPU torch"`

### Task 2: Publish `datascience` 1.2.0 (brineylab/toolshed)

Follow the shed's `CONTRIBUTING.md`. Ask the human before each push and before the PR: these are outward-facing.

- [ ] **Step 1:** `scripts/build datascience && scripts/push datascience`.
- [ ] **Step 2:** `scripts/test datascience srun --partition=hpc-low --cpus-per-task=4 --mem=16G --time=00:30:00` on coreweave-rtx6000's login node. This writes `results/datascience/1.2.0.txt`. Expected: the record ends with exit 0.
- [ ] **Step 3:** Commit the record, open a PR (`Refs brineylab/flyloft#224`), and have someone other than the builder review it.
- [ ] **Step 4:** After review, `gh pr merge --merge`. Then confirm `promote` passed and that `skopeo inspect docker://ghcr.io/brineylab/toolshed/datascience:1.2.0` answers.

### Task 3: The recipe and its test (brineylab/datasets, branch `oplm-antibody-sequences`)

**Files:**
- Create: `datasets/oplm-antibody-sequences/recipe/params.toml`
- Create: `datasets/oplm-antibody-sequences/recipe/build` (executable, `#!/usr/bin/env -S python3 -I`)
- Create: `datasets/oplm-antibody-sequences/recipe/test` (executable)

**Interfaces:**
- Consumes: Task 1's `Anarcii`; DuckDB and pyarrow, as in `datascience`.
- Produces: the layout in Global Constraints. The build prints these lines, which the record carries:
  - `held out failed numbering <stratum>: <n>`
  - `rows <file or folder>: <n>`
  - `locus <file> <IGH|IGK|IGL>: <n>`

  The test exits 0 if and only if the output is a version.

- [ ] **Step 1: `params.toml`.**

  ```toml
  pulled = "2026-11-09"
  seed = 1
  heldout = 5000
  shard_rows = 1000000
  limit = 0  # manifest rows, for a developer's dry run; 0 is all, and the published version has 0
  ```

  For a dry run, a developer edits `limit` and `heldout` (for example 2000000 and 200) and never commits that edit. jaffe-paired does the same.
- [ ] **Step 2: Write `recipe/test <out>` first.** It is stdlib, plus pyarrow for footers and samples. It reads `heldout` from `params.toml` beside it. It checks:
  - the four held-out files have exactly `heldout` rows each and the §5 columns;
  - each train folder has shards named `shard-%05d.parquet`, contiguous from 0, and every shard but the last has `shard_rows` rows (read from footers);
  - each train folder's total rows are at least a floor: `FLOOR = {"antiref96": 0, "antiref99": 0}` until step 9 sets 90% of the full build's counts;
  - no `sequence_id` appears in two held-out files, or in a held-out file and train shards 0 and last of either folder;
  - every `cdr_mask_aa` is `len(sequence)` long, matches `^[0-3]+$`, and has exactly one contiguous run of `3`s;
  - every `locus` is in `{IGH, IGK, IGL}`;
  - in train96 shard 0 and the last shard, `member_ids[0] == sequence_id` and `member_sequences[0] == sequence`, and both lists are the same length.

  Print `ok` last.
- [ ] **Step 3: Run the test on an empty directory to see it fail.**
  - Run: `datasets/oplm-antibody-sequences/recipe/test /tmp/empty`
  - Expected: exit 1, naming the first missing file.
- [ ] **Step 4: Write `recipe/build` stages 1–2: download and stage.** Stages live under `<out>/.work/`, each skipped when its output exists, as jaffe-paired's are.
  - `download(dest: Path) -> None`:
    - Stream each file to `<name>.part`, then check its MD5 against the Global Constraints value.
    - On a match, rename it into place. On a mismatch, delete it and exit 1 with `MD5 <got> != <want> for <name>`.
    - An existing final file is trusted only if its size matches.
  - `stage(work: Path, limit: int) -> None`:
    - Write `manifest.parquet` with the seven columns from DuckDB's `read_csv` of the gz. With `limit`, keep only the first `limit` rows.
    - Write `sequences.parquet` (`sequence_id`, `sequence`) by streaming the FASTA in pyarrow batches. With `limit`, keep only IDs in the staged manifest's `antiref100`.
    - Then assert that every manifest `antiref100` has a sequence, and, without `limit`, that every sequence has a manifest row. Otherwise exit 1 with `<n> manifest ids lack a sequence` (or the reverse).
- [ ] **Step 5: Write stage 3: hold out.**
  - `cdr_mask(numbering: list[tuple[tuple[int, str], str]], sequence: str) -> str | None` returns the mask, or `None` if the non-gap residues don't join to `sequence` or no residue is in 105–117.
  - At start-up, before anything else in this stage, number `QVQLVQSGAEVKKPGASVKVSCKASGYTFTSYAMYWVRQAPGQRLEWMGWINARNGNTKYSQKFQGRVTITRDTSASTAYMELSSLRSEDTAVYYCARSPYSSSWPGYYYYYYGMDVWGQGTTVTVSS` and assert its mask is exactly

    `00000000000000000000000001111111100000000000000000222222220000000000000000000000000000000000000033333333333333333333300000000000`

    and its chain type is `H`. This is the known answer (IMGT: FWR1 25, CDR1 8, FWR2 17, CDR2 8, FWR3 38, CDR3 21, FWR4 11). If it disagrees, stop and report rather than adjusting it.
  - `heldout_sets(work: Path, seed: int, n: int) -> dict[str, list[dict]]`, keyed by `eval_singletons`, `test_singletons`, `eval_gte2`, `test_gte2`:
    - AntiRef90 cluster size is its count of manifest rows (1 is a singleton).
    - Walk each stratum in `md5('<seed>:<antiref90>')` order, in pools of `int(2.4 * n)`, numbering each pool in one `Anarcii(...).number` call.
    - Keep a candidate whose `chain_type` is H, K, or L and whose `cdr_mask` is not `None`. The first `n` kept are eval, the next `n` test. Count the rest as failed.
    - If a stratum runs out of candidates before `2n` are kept, exit 1 with `stratum <s>: <kept> of <2n> after <tried> candidates`.
  - Write the four files, and `heldout.parquet` (the 4n AntiRef90 IDs) under `.work/`.
- [ ] **Step 6: Write stage 4: train.** It runs in DuckDB, with `temp_directory` under `.work/` and `threads` set to `len(os.sched_getaffinity(0))`.
  - Remove manifest rows whose `antiref90` is in `heldout.parquet`.
  - **train99:** the distinct `antiref99`, joined to `sequences`.
  - **train96:** group by `antiref96`:
    - `member_ids` is the list of distinct `antiref99`, ordered by `antiref99 = antiref96 DESC, md5(...)`;
    - `member_sequences` is aligned with `member_ids`;
    - `sequence` is the representative's own.
  - Order each set by `md5('<seed>:' || sequence_id)`. Write shards with pyarrow from `fetch_record_batch(shard_rows)`: one `pq.write_table(..., row_group_size=10_000, compression="zstd")` per shard, named `shard-%05d.parquet`.
  - Print the `rows` and `locus` lines last.
- [ ] **Step 7: Dry run, then the test.**
  - Set `limit = 2000000` and `heldout = 200` locally.
  - Run in `datascience:1.2.0` on a CPU node (`srun --partition=hpc-low --cpus-per-task=16 --mem=128G --container-image=ghcr.io#brineylab/toolshed/datascience:1.2.0 ...`): `recipe/build /tmp/oab && recipe/test /tmp/oab`.
  - Expected: `ok`. The dry run still downloads both files, about 32.5 GB.
- [ ] **Step 8: Mutation check.**
  - Copy `eval_gte2.parquet`, rewrite one row's `cdr_mask_aa` one character shorter, and run the test.
  - Expected: exit 1, naming the row. Restore the file.
- [ ] **Step 9: A full build by hand,** with the published `params.toml`, on the same kind of node. This measures what flyloft's single run must fit: wall time per stage, peak memory (`sacct -j <job> -o MaxRSS,Elapsed`), `.work/` disk, and output size. It also gives the train row counts, so the floors are set before flyloft cooks; a floor changed after would cook again from scratch.
  - Run: `recipe/build /mnt/data/<user>/oab-full && recipe/test /mnt/data/<user>/oab-full`. Expected: `ok`.
  - Set `FLOOR` in `recipe/test` to `int(0.9 * rows)` for each train folder, from the printed `rows` lines, then rerun the test. Expected: `ok`.
  - Keep the numbers for Task 4's Compute section. The output is not pushed: flyloft's cook makes the version.
- [ ] **Step 10: Revert `params.toml` to the published values and commit.**
  - `git commit -m "oplm-antibody-sequences builds two AntiRef train sets and CDR-masked held-out AntiRef90 clusters in datascience 1.2.0"`

### Task 4: The skill (brineylab/datasets)

**Files:**
- Create: `datasets/oplm-antibody-sequences/SKILL.md`

- [ ] **Step 1: Write the skill**, with jaffe-paired's sections:
  - **Frontmatter:**
    - `name: oplm-antibody-sequences`;
    - `description` (one sentence: what it holds and when to reach for it);
    - `metadata.version: 1.0.0`;
    - `metadata.tools: datascience@1.2.0`;
    - `metadata.license: cc-by-4.0`.
  - **Hub:** `brineylab/oplm-antibody-sequences`, tag `v1.0.0`.
  - **Files:** spec §5, column by column.
  - **Reading it:** a `snapshot_download` line, plus how OPLM points `data.train` at each folder (`sample_members` true or false on `antiref96`).
  - **Recipe:** source, pull date, steps, `params.toml`.
  - **The test.**
  - **Compute:** Task 3 step 9's numbers: node, CPUs, memory asked and peak, wall time per stage, disk, output size.
  - **Gotchas:**
    - the held-out guarantee is AntiRef90 cluster membership only (spec §9.2);
    - both thresholds sit in one dataset by decision (§9.3);
    - light chains are low-diversity;
    - no donor, nucleotides, or SHM mask;
    - subsample by taking any subset of shards.
- [ ] **Step 2: Check.**
  - Run: `python3 -I scripts/check.py datasets/oplm-antibody-sequences`. Expected: exit 0.
- [ ] **Step 3: Commit and push the branch** (ask the human first).
  - `git commit -m "oplm-antibody-sequences has its skill: the files, how OPLM reads them, the recipe, and its limits"`
  - `git push -u origin oplm-antibody-sequences`

### Task 5: Cook through flyloft (brineylab/flyloft host)

Requires Task 2 merged (flyloft's `submit_dataset` checks the tool against the shed's catalogue). Launching a campaign is outward-facing, so the human launches it, or approves its launch, through the `flyloft` skill.

- [ ] **Step 1: Hand flyloft a task.** In its datasets worktree, the implementer:
  - merges `origin/oplm-antibody-sequences`;
  - calls `submit_dataset("oplm-antibody-sequences", cpus=32, mem="256G", time=<the campaign's ceiling>, summary=...)`.

  Size `cpus`, `mem`, and `time` from Task 3 step 9's measurements, with headroom. If they don't fit the campaign's CPU-run limit or time ceiling, stop and tell the human before launching.
- [ ] **Step 2: On a passed build,** check that the record's `rows` lines match Task 3 step 9's counts. A difference means the build isn't deterministic: stop and report.
- [ ] **Step 3: After merge and promote,** confirm `snapshot_download("brineylab/oplm-antibody-sequences", repo_type="dataset", revision="v1.0.0")` returns the §5 layout. Then close brineylab/flyloft#224 with a comment naming the tag, the record, and briney/oplm#85.
