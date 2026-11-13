---
name: oplm-antibody-cdrh3
description: "Human antibody chains from AntiRef v2022.12.14 (OAS, healthy donors' blood) with a heavy-chain CDR3-identity holdout at 85%: 5,000 held-out heavy chains whose CDR3s have no 85%-identical CDR3 left in training, oplm-antibody-sequences v1's eval and test files unchanged, and four screened train sets (AntiRef90, 92, 94 and 96 clusters with AntiRef99 members). Reach for it to compare antibody train sets in OPLM's anneal, or to measure CDR3 loss on CDR3s the model has not seen."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: cc-by-4.0
---
# oplm-antibody-cdrh3

Hub: `brineylab/oplm-antibody-cdrh3`, tag `v1.0.0`

`oplm-antibody-sequences` v1 held out whole AntiRef90 clusters and nothing more, so 27% of eval_gte2's heavy chains had an exact copy of their CDR3 in train. This dataset adds a holdout where "unseen" means unseen: no heavy-chain CDR3 left in training is 85% or more identical to a held-out heavy chain's CDR3. Its four train sets share that holdout and that screen, so OPLM decays that differ only in train set can be compared (briney/oplm#78). It is built from the published AntiRef (Briney 2023, *Bioinformatics Advances*, [10.1093/bioadv/vbad109](https://doi.org/10.1093/bioadv/vbad109)). A donor holdout waits on a rebuild from current OAS.

## Files

```
antiref90/train/shard-00000.parquet …   one row per AntiRef90 cluster
antiref92/train/ …  antiref94/train/ …  antiref96/train/ …
eval_cdrh3.parquet  test_cdrh3.parquet
eval_singletons.parquet  eval_gte2.parquet  test_singletons.parquet  test_gte2.parquet
```

- **`antiref{90,92,94,96}/train/`**, uniref70's columns:
  - `sequence_id`, `sequence`: the cluster's representative, its AntiRef UUID and amino acids. **A row's `sequence` is AntiRef's representative unless the screen removed it**; then the cluster's first surviving member, in the seeded order, takes its place;
  - `member_ids`, `member_sequences`: the surviving AntiRef99 representatives inside the cluster, the row's own entry first.

  All four folders hold the same 299,748,717 AntiRef99 sequences, grouped differently, so the four train sets differ only in how training draws from them.
- **Shards:** 1,000,000 rows each (the last fewer), row groups of 10,000, zstd. Rows are in a seeded global shuffle (`md5('1:<level id>')`), so any subset of shards is a uniform sample. Members follow the representative in `md5('1:<antiref99>')` order.
- **`eval_cdrh3`, `test_cdrh3`:** 2,500 heavy chains each, the CDR3-identity holdout. Every CDR3 has at least 5 residues, and no two CDR3s across both files are 85% identical.
- **`eval_singletons`, `eval_gte2`, `test_singletons`, `test_gte2`:** oplm-antibody-sequences v1.0.0's files, byte-identical, so earlier #78 numbers stay comparable. 5,000 representatives of held-out AntiRef90 clusters each, heavy and light mixed.
- **Held-out columns**, all six files:
  - `sequence_id`, `sequence`;
  - `locus`: `IGH`, `IGK`, or `IGL` (`IGH` only in the `_cdrh3` files);
  - `cdr_mask_aa`: one digit per residue of `sequence`: `0` framework, `1` CDR1, `2` CDR2, `3` CDR3, from ANARCII 2.0.8's IMGT numbering (CDR1 27–38, CDR2 56–65, CDR3 105–117).

  Every member of a held-out AntiRef90 cluster is out of every train set.

`sequence` is the variable domain, FWR1 through FWR4.

## Reading it

```python
from huggingface_hub import snapshot_download
path = snapshot_download("brineylab/oplm-antibody-cdrh3", repo_type="dataset", revision="v1.0.0")
```

In OPLM, a `data.train` source is one of the four folders, **always with `sample_members: true`**: a row's representative may stand in for a removed one, so the representatives alone are not AntiRef's. The six held-out files are `type: sequence` evals; OPLM's `antibody_cdr3` eval reads them unchanged and scores only positions where `cdr_mask_aa` is `3`, per `locus`. Read heavy-only metrics on the `_cdrh3` files.

## Recipe

**Source:** AntiRef v2022.12.14 on Zenodo (CC BY 4.0), pulled 2026-11-09, the same two files as v1:
- record 7474336, `antiref_cluster-manifest.csv.gz` (14,054,641,207 bytes, MD5 `18fcf6376702a2d23e2acdc32f1fd40a`): one row per AntiRef100 sequence, with its representative at 100, 99, 98, 96, 94, 92, and 90% identity;
- record 7474658, `antiref100.fasta.gz` (18,496,427,276 bytes, MD5 `4a82d4be0c493377668fac9730aca866`): each sequence's UUID and amino acids.

The recipe refuses a download whose MD5 differs. AntiRef's clustering was MMseqs2 linclust, nested: each threshold clustered the previous one's representatives, with `-c 0.8 --cov-mode 0`.

**Identity.** Two CDR3s `a` and `b` are 85% identical when `levenshtein(a, b) <= max(len(a), len(b)) * 3 // 20`. Length differences count against identity.

**Steps**, one job in `datascience@1.2.0`. Each stage lives under `<out>/.work/` and is skipped when a rerun finds it finished. A self-check of the matching code against known answers runs first.

1. **Stage** the manifest and the FASTA as parquet, as v1.
2. **v1's holdout**, unchanged (`seed = 1`, `heldout = 5000`): the four v1 files come out byte-identical.
3. **The heavy CDR3 holdout.** Walk the remaining AntiRef90 representatives in `md5('<cdrh3_seed>:<antiref90>')` order and number each with ANARCII (IMGT). Keep a candidate when its chain is H, every residue is numbered, its CDR3 has at least 5 residues, and its CDR3 is not 85% identical to one already kept. The first 2,500 kept are eval, the next 2,500 test.
4. **The screen.** Every AntiRef99 sequence outside the held-out AntiRef90 clusters is checked against the 5,000 held-out CDR3s, on its C-terminal half (`sequence[len(sequence) // 2:]`), which always holds the CDR3:
   - **anchored:** every substring of 3–40 residues right after a `C` and right before a `[WF]G.G` is a candidate CDR3. The sequence goes when any candidate is 85% identical to a held-out CDR3. Trying every boundary pair means a misplaced boundary can't hide a match, and matching end to end keeps shared D or J stretches from removing unrelated antibodies;
   - **unanchored** (no candidate): the sequence goes when a held-out CDR3 `q` aligns semi-globally anywhere in the half within `len(q) * 3 // 17` edits, a superset of the 85% bound for any substring length.

   A pigeonhole index (an exact piece of the query must appear in any match) narrows the candidates before alignment. Hits are written to `.work/screened.parquet`, then the tripwire is checked: the build stops if the screen removed more than `screen_max` of AntiRef99 sequences. A rerun with a raised `screen_max` reuses the hits.
5. **Train.** Drop held-out clusters and screened sequences, then write each level's clusters with their surviving AntiRef99 members, in the seeded order; a cluster with no survivor is dropped. The build stops if a representative is not among its own AntiRef99 members, or if the four folders' member totals differ.

`params.toml`:
- `seed = 1`, `heldout = 5000`: v1's holdout;
- `cdrh3_seed = 2`, `cdrh3_heldout = 2500`;
- `screen_max = 0.06`;
- `shard_rows = 1000000`;
- `limit = 0`: whole AntiRef90 clusters, for a developer's dry run. 0 is all, and the published version has 0.

**The test** checks, with its own matching code (DuckDB's `levenshtein` and a q-gram-filtered semi-global search), not the build's:
- the files, their columns and row counts; v1's four by sha256 against v1.0.0;
- the shards' names and sizes, and each train folder against its floor;
- `_cdrh3` rows are `IGH` with a CDR3 of at least 5; masks' length, digits and single CDR3 run;
- no two held-out CDR3s 85% identical;
- no `sequence_id` in two held-out files, or in a held-out file and a train shard (first and last of each folder);
- representative-first members;
- **the screen holds** on 1,000 rows of each folder's first shard: no anchored candidate is 85% identical to a held-out CDR3, and 200 unanchored members carry none by the semi-global search.

## Compute

Measured on the first full build, on bcr's `cpu` partition with 32 CPUs and 256 GB of memory, run as flyloft jobs:
- **Time:** about 7.5 hours from nothing.
  - Download, stage and v1's holdout: about 50 min.
  - The CDR3 holdout: 5 min (11,478 candidates tried, 275 rejected as near a kept CDR3).
  - The screen: about 5.7 hours. Real data ran about four times slower than the synthetic benchmark (217 µs per anchored sequence): public CDR3s make many full alignments.
  - The four train folders and the test: about 45 min.
- **Memory:** not measured (flyloft did not return `sacct`); 256 GB was enough.
- **Disk:** `.work/` 117 GB; the output 80 GB.
- **The screen:** removed 16,222,603 of 315,971,320 AntiRef99 sequences (5.134%). 1,472 held-out CDR3s each removed more than 1,000; the largest removed 358,021.
- **Rows** (mean members per row): AntiRef90 152,351,629 in 153 shards (1.97); AntiRef92 161,836,404 in 162 (1.85); AntiRef94 175,083,828 in 176 (1.71); AntiRef96 199,443,463 in 200 (1.50). The test's floors are 90% of these.

## Gotchas

- **Four clustering levels live in one dataset**, against the datasets design's rule (D3), by the PI's decision of 2026-11-12, extending v1's exception: all four train sets must share one holdout and one screen, and one recipe guarantees that.
- **The tripwire was raised to 6%** by the PI on 2026-11-13, after the first build removed 5.134% against the planned 5%. The held-out sets were kept as drawn: public CDR3s are the ones whose holdout matters most. There is no per-CDR3 cap, which would bias the eval away from public CDR3s.
- **Light chains are held out by AntiRef90 cluster only**, as in v1. Their CDR3s are low-diversity; light-chain loss here still rewards recall.
- **The screen is CDR3-only.** A train sequence can share a held-out chain's V gene and framework; only its CDR3 is kept below 85%.
- **The screen over-removes slightly, by design:** every boundary pair is tried, the whole C-terminal half is searched, light chains are screened too, and unanchored sequences get a bound looser than 85%.
- **No screen against OPLM's uniref70 or deepclust70:** an antibody from UniProt may sit in both.
- AntiRef's filter: OAS unpaired, human, PBMC, no disease, no vaccine. There is no donor, no nucleotide sequence, no germline call, and no SHM mask; a donor holdout needs a rebuild.
- **Zenodo is slow to CoreWeave** (see oplm-antibody-sequences), so build on bcr.
- **A flyloft job's bundle drops the executable bit:** run `python3 -I recipe/build`, not `recipe/build`.
