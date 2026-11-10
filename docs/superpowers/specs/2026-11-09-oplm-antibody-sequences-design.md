# `oplm-antibody-sequences`: Design

Status: approved 2026-11-09, from a design conversation with the lab's PI. Tracked on brineylab/flyloft#224. The OPLM side, a CDR3 eval and the new source in the training mix, is briney/oplm#85, under the anneal experiment briney/oplm#78. Calls made in writing that nobody discussed are marked **(call)**.

## 1. Why

OPLM's anneal (decay) phase may gain from a small share of antibody sequences, about 1–3% of rows. Before investing in a rebuilt, donor-aware, annotated AntiRef, the lab wants a cheap pilot: does a decay with antibodies improve antibody performance over a matched decay on protein sequences only, measured where antibodies are hard (CDR3)? This dataset is that pilot's data. It is built from the published AntiRef (Briney 2023, *Bioinformatics Advances*, [10.1093/bioadv/vbad109](https://doi.org/10.1093/bioadv/vbad109)) as it stands, and laid out like OPLM's own sequence data, so OPLM's loader reads it unchanged.

## 2. Decisions (the PI's)

- **Use the existing AntiRef v2022.12.14; no rebuild.** Its filter (human, PBMC, no disease, no vaccine in OAS) is fine for the pilot. A rebuild from current OAS stays a future option, taken only if the pilot shows promise.
- **Eval and test come from AntiRef90**, the lowest threshold: held-out AntiRef90 clusters, represented by their representatives. Every member of a held-out cluster is out of train.
- **Two strata, as uniref70's:** singletons and gte2, 5,000 eval and 5,000 test each.
- **Three train options, from the same source:**
  - AntiRef96 representatives, sampled uniformly.
  - AntiRef99 representatives, sampled uniformly.
  - AntiRef96 clusters sampled uniformly, then one AntiRef99 member of each.
- **Format and layout match OPLM's sequence datasets**, uniref70 in particular (`brineylab/oplm-sequence-data`, described in briney/oplm `docs/data.md`).
- **One mask: CDR regions, by ANARCII.** Eval and test rows carry `cdr_mask_aa` in abstar's format, so a later abstar-annotated rebuild drops in.
- **Heavy and light chains both, with a `locus` column**, so OPLM can run heavy-only and light-only evals.

## 3. Goals, non-goals, anti-goals

**Goals.**
- OPLM can train on any of the three options and evaluate CDR3 loss, perplexity, and accuracy per locus without any new data handling. The new eval itself is oplm#85.
- Cluster-level separation: no AntiRef90 cluster has sequences in both train and eval/test.

**Non-goals** (wait for a rebuild, if the pilot earns it):
- a non-germline (SHM) mask;
- a donor holdout (AntiRef's published files carry no donor, and the 2022 annotated intermediates are gone);
- a leakage screen of eval/test against uniref70 or deepclust70;
- paired chains;
- newer OAS data.

**Anti-goals.**
- Annotating the train sets: only eval and test need masks.
- A `summary.json` or a `manifest.parquet` beside the files, as `oplm-sequence-data` has: the record and `scripts/push`'s manifest carry that here **(call)**.

## 4. Source

AntiRef v2022.12.14 on Zenodo, CC BY 4.0. Two files:

| Zenodo record | file | bytes | MD5 |
|---|---|--:|---|
| 7474336 (AntiRef, [10.5281/zenodo.7474336](https://doi.org/10.5281/zenodo.7474336)) | `antiref_cluster-manifest.csv.gz` | 14,054,641,207 | `18fcf6376702a2d23e2acdc32f1fd40a` |
| 7474658 (AntiRef100, [10.5281/zenodo.7474658](https://doi.org/10.5281/zenodo.7474658)) | `antiref100.fasta.gz` | 18,496,427,276 | `4a82d4be0c493377668fac9730aca866` |

Download URLs: `https://zenodo.org/api/records/<record>/files/<file>/content`. The recipe refuses a download whose MD5 differs, as jaffe-paired's does.

What they hold, as checked on 2026-11-09:

- **The manifest.** A header `antiref100,antiref99,antiref98,antiref96,antiref94,antiref92,antiref90`, then one row per AntiRef100 sequence. Each column is the ID of the sequence's cluster representative at that threshold. The clustering was nested: each threshold clustered the previous one's representatives with MMseqs2 linclust (`-c 0.8 --cov-mode 0`). So every representative at every threshold is itself an AntiRef100 sequence, and each AntiRef96 cluster lies inside one AntiRef90 cluster.
- **The FASTA.** Each header is the sequence's UUID4 and nothing else. Each sequence is amino acids, FWR1 through FWR4, built by the original filter as OAS's `fwr1_aa` … `fwr4_aa` joined. That is the span abstar's `sequence_vdj_aa` covers, which abstar's masks index.
- **What's missing.** No chain, no annotations, no nucleotides, no donor.
- **A sample.** The first 50 MB of the FASTA held 906,018 sequences: no `X`, no `*`, lengths 106 / 118 / 131 at the 1st / 50th / 99th percentile.

AntiRef100 holds about 335M sequences (of 451M input: 260M heavy, 191M light), and AntiRef90 about a third of the input. The exact counts at 96 and 99 are not published outside the paper's figure; the build prints them.

## 5. The version's files

The layout mirrors `oplm-sequence-data`'s per-source folders:

```
antiref96/train/shard-00000.parquet …   one row per AntiRef96 cluster
antiref99/train/shard-00000.parquet …   one row per AntiRef99 representative
eval_singletons.parquet                 5,000
eval_gte2.parquet                       5,000
test_singletons.parquet                 5,000
test_gte2.parquet                       5,000
```

- **`antiref96/train/`.** Columns:
  - `sequence_id`: the AntiRef96 representative's UUID.
  - `sequence`: its amino acids.
  - `member_ids`, `member_sequences`: lists of the AntiRef99 representatives in the cluster, the representative's own entry first. This is uniref70's convention: the clustering is nested, so the AntiRef96 representative is always one of its own AntiRef99 members.

  OPLM's `sample_members: false` trains on AntiRef96 representatives; `sample_members: true` samples an AntiRef96 cluster, then one AntiRef99 member.
- **`antiref99/train/`.** Columns `sequence_id` and `sequence`, as deepclust70's rows.
- **Eval and test.** Columns:
  - `sequence_id`, `sequence`: the held-out AntiRef90 representative.
  - `locus`: `IGH`, `IGK`, or `IGL`, abstar's spelling, from ANARCII's chain type H, K, or L.
  - `cdr_mask_aa`: abstar 0.9.0's CDR mask. A string with one digit per residue of `sequence`: `0` for framework (FWR1–FWR4), `1` CDR1, `2` CDR2, `3` CDR3, with IMGT regions (CDR1 27–38, CDR2 56–65, CDR3 105–117; an insertion takes its base position's region). abstar's docstring says FWR4 is `4`, but its code writes `0`; this follows the code.
- **Shards.** `shard-%05d.parquet`, 1,000,000 rows each (the last fewer), as deepclust70's; row groups of 10,000; zstd **(call)**.
  - uniref70's 100,000 rows would make about 5,000 files and some 70 GB, through `scripts/push`'s single `upload_folder` commit.
  - 1,000,000 rows makes about 500 files. OPLM's loader doesn't care.
- **Column types.** As uniref70's: `sequence_id` and `sequence` are strings; `member_ids` and `member_sequences` are lists of strings, non-empty and the same length (OPLM's loader requires both).
- **Order.** Each train set is written in a seeded global shuffle, as uniref70 is. OPLM's loader expects shuffled shards. Pilot runs that subsample (oplm#78 uses 1/35 of the source to keep production pass counts) can then take any subset of shards as a uniform sample.

## 6. Steps

One job, CPU only, in one tool: flyloft cooks only one-tool recipes (`submit_dataset`), and a split recipe is deferred in flyloft's `docs/design/datasets.md` §8. The tool is `datascience@1.2.0` (§9).

flyloft runs the build, the test, and `scripts/push` as one CPU run, within the campaign's per-run time limit. Its output directory is keyed by the recipe's commit, so a resubmission after a recipe fix starts from scratch, download included. The campaign's time limit has to cover the whole thing.

ANARCII (2.0.8) ships its model weights inside the package, so it downloads nothing at runtime. For each sequence it returns:
- `numbering`: a list of `((position, insertion letter), residue)` pairs, with gaps as `"-"`;
- `chain_type`: `H`, `K`, or `L`, or `F` on failure, with the reason in `error`.

"Every residue numbered" means the non-gap residues join back into `sequence`. Below 102,400 sequences per call, its output stays in memory.

1. **Download** both files and check their MD5s.
2. **Hold out.**
   - Each AntiRef90 cluster's size is its number of manifest rows (AntiRef100 sequences). A singleton has one; gte2 has two or more **(call)**.
   - The distinct AntiRef90 IDs, sorted, are shuffled with `random.Random(seed)`, jaffe-paired's convention. Walk them in that order, each stratum separately.
   - Number each candidate's representative with ANARCII, IMGT scheme. Keep a candidate only if:
     - its chain type is H, K, or L;
     - every residue of `sequence` is numbered;
     - the CDR3 is non-empty.
   - Within each stratum, the first 5,000 kept are eval and the next 5,000 test. Candidates that fail numbering stay in train.
   - Number candidates in batches, a pool a little over 10,000 per stratum, not one call each **(call)**.
3. **Train.** Drop every manifest row whose `antiref90` is one of the 20,000 held out. From what remains:
   - `antiref96` rows are the distinct `antiref96` IDs, each with its distinct `antiref99` IDs as members, representative first;
   - `antiref99` rows are the distinct `antiref99` IDs.

   Sequences come from the FASTA, joined by ID.
4. **Write** §5's files.
5. **Print** the counts the record should carry, last:
   - `held out failed numbering <stratum>: <n>`;
   - `rows <file or folder>: <n>`;
   - per-locus counts for each eval/test file (`locus eval_gte2 IGH: <n>`).

Scale: the manifest is about 335M rows × 7 UUIDs, roughly 85 GB as plain CSV. Doing the join and group-by out of core is the builder's call (DuckDB and polars are both in `datascience`). So is resuming from stages under `<out>/.work/`, as jaffe-paired does.

`params.toml`: `pulled = "2026-11-09"`, `seed = 1`, `heldout = 5000`, `shard_rows = 100000`, and a `limit` for a developer's dry run over the first `limit` manifest rows (0 is all, and the published version has 0).

## 7. The test

It runs in seconds, from footers and samples, as the repository's rules require:

- the files and folders of §5 exist, with their columns;
- each eval/test file has exactly 5,000 rows;
- each train folder's rows are above a floor, 90% of the first build's counts as jaffe-paired's;
- no `sequence_id` appears in two eval/test files, or in a sampled train shard and an eval/test file;
- each `cdr_mask_aa` has the length of its `sequence`, only the digits `0`–`3`, and one contiguous run of `3`s;
- each `locus` is `IGH`, `IGK`, or `IGL`;
- each sampled `antiref96` row's first member is itself.

## 8. Compute

To be measured on the first build and written into the skill. My guesses:

- download 32.5 GB;
- an hpc-low CPU node with large memory for the manifest join;
- ANARCII over about 25,000 sequences on CPU in minutes;
- the output tens of GB of zstd parquet.

## 9. Decided after review (the PI's, 2026-11-09)

1. **The tool is `datascience` 1.2.0: 1.1.0 plus ANARCII 2.0.8 and CPU torch.**
   - It is published in the toolshed before this dataset is submitted, and the skill names `datascience@1.2.0`.
   - A separate `anarcii` tool would need a split recipe, which flyloft can't cook (§6).
   - The `deeplearning` image (torch plus CUDA) is not needed for a CPU numbering step.
2. **No leakage screen within AntiRef for the pilot.** The guarantee is cluster membership only, and the skill says so plainly:
   - **Below 90%.** A held-out representative can still have a train sequence with the same V gene and a similar CDR3 at under 90% overall identity. oplm#78 notes that such splits flatter antibody loss.
   - **At 90% and above.** linclust is greedy and compares only to cluster representatives, over six nested levels, so a train sequence can be 90% or more identical to a held-out representative and sit in another AntiRef90 cluster.

   Both arms of the pilot (antibody decay and protein-only control) are judged on the same sets. A screen (uniref70's `select_eval`, run against train) belongs to a production dataset.
3. **Two thresholds in one dataset: an exception to `docs/DESIGN.md` D3.** `antiref96/` and `antiref99/` live in one dataset, as `oplm-sequence-data` holds two sources, so all three train options share one set of eval and test files. The name says what the dataset is for, OPLM training, not a threshold.
