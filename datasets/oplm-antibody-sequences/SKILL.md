---
name: oplm-antibody-sequences
description: "Human antibody heavy and light chains from AntiRef v2022.12.14 (OAS, healthy donors' blood), laid out as OPLM's sequence data: AntiRef96 clusters with their AntiRef99 members, AntiRef99 representatives, and held-out AntiRef90 clusters with locus and an IMGT CDR mask. Reach for it to add antibodies to OPLM training or to measure CDR3 loss."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: cc-by-4.0
---
# oplm-antibody-sequences

Hub: `brineylab/oplm-antibody-sequences`, tag `v1.0.0`

A pilot: does a decay with antibodies improve OPLM's antibody performance, judged on CDR3, against a decay on protein sequences only? It is built from the published AntiRef as it stands (Briney 2023, *Bioinformatics Advances*, [10.1093/bioadv/vbad109](https://doi.org/10.1093/bioadv/vbad109)). A rebuild from current OAS, with donors and germline annotations, waits on the pilot.

## Files

The layout is `brineylab/oplm-sequence-data`'s, one folder per training source:

```
antiref96/train/shard-00000.parquet …   one row per AntiRef96 cluster
antiref99/train/shard-00000.parquet …   one row per AntiRef99 representative
eval_singletons.parquet  eval_gte2.parquet  test_singletons.parquet  test_gte2.parquet
```

- **`antiref96/train/`**, uniref70's columns:
  - `sequence_id`: the AntiRef96 representative's AntiRef UUID;
  - `sequence`: its amino acids;
  - `member_ids`, `member_sequences`: the AntiRef99 representatives inside the cluster, the representative's own entry first.
- **`antiref99/train/`**, deepclust70's columns: `sequence_id`, `sequence`.
- **Shards:** 1,000,000 rows each (the last fewer), row groups of 10,000, zstd. Rows are in a seeded global shuffle (`md5('1:<sequence_id>')`), so any subset of shards is a uniform sample.
- **Eval and test** each hold 5,000 representatives of held-out AntiRef90 clusters: `_singletons` from clusters of one AntiRef100 sequence, `_gte2` from clusters of two or more. Heavy and light chains are mixed. Columns:
  - `sequence_id`, `sequence`;
  - `locus`: `IGH`, `IGK`, or `IGL`;
  - `cdr_mask_aa`: abstar 0.9.0's CDR mask, one digit per residue of `sequence`: `0` framework, `1` CDR1, `2` CDR2, `3` CDR3. It uses IMGT regions (CDR1 27–38, CDR2 56–65, CDR3 105–117, insertions with their base position) from ANARCII 2.0.8's numbering.

  Every member of a held-out cluster is out of both train sets.

`sequence` is the variable domain, FWR1 through FWR4: the span abstar's `sequence_vdj_aa` covers.

## Reading it

```python
from huggingface_hub import snapshot_download
path = snapshot_download("brineylab/oplm-antibody-sequences", repo_type="dataset", revision="v1.0.0")
```

In OPLM, a `data.train` source is a folder of shards:
- **AntiRef96 representatives:** `antiref96/train` with `sample_members: false`.
- **AntiRef96 clusters sampled to one AntiRef99 member:** `antiref96/train` with `sample_members: true`.
- **AntiRef99 representatives:** `antiref99/train`.

The four held-out files are `type: sequence` evals. The CDR3 eval, which scores only positions where `cdr_mask_aa` is `3` and runs per `locus`, is briney/oplm#85.

## Recipe

**Source:** AntiRef v2022.12.14 on Zenodo (CC BY 4.0), pulled 2026-11-09:
- record 7474336, `antiref_cluster-manifest.csv.gz` (14,054,641,207 bytes, MD5 `18fcf6376702a2d23e2acdc32f1fd40a`): one row per AntiRef100 sequence, with its representative at 100, 99, 98, 96, 94, 92, and 90% identity;
- record 7474658, `antiref100.fasta.gz` (18,496,427,276 bytes, MD5 `4a82d4be0c493377668fac9730aca866`): each sequence's UUID and amino acids.

The recipe refuses a download whose MD5 differs. AntiRef's clustering was MMseqs2 linclust, nested: each threshold clustered the previous one's representatives, with `-c 0.8 --cov-mode 0`.

**Steps**, one job in `datascience@1.2.0`:

1. **Stage** the manifest and the FASTA as parquet. Every manifest ID must have a sequence, and every sequence a manifest row.
2. **Hold out.**
   - Put the AntiRef90 clusters in the seeded order, `md5('<seed>:<antiref90>')`, and walk singletons and gte2 separately.
   - Number each representative with ANARCII (`seq_type="antibody"`, `mode="accuracy"`, IMGT). Keep it when its chain type is H, K, or L, every residue is numbered, and it has a CDR3.
   - The first `heldout` kept are eval, the next `heldout` test. Candidates that fail numbering stay in train; the build prints how many.
   - Before any of this, the build numbers one known heavy chain and stops if its mask moved.
3. **Train.** Drop every manifest row in a held-out cluster. AntiRef99 rows are the distinct `antiref99`. AntiRef96 rows are the distinct `antiref96`, with their distinct `antiref99` as members; the build stops if a representative is not its own first member. Both are written in the seeded order.

`params.toml`:
- `seed = 1`, `heldout = 5000`, `shard_rows = 1000000`;
- `limit = 0`: whole AntiRef90 clusters, for a developer's dry run. 0 is all, and the published version has 0.

**The test** checks:
- the files, their columns, and `heldout` rows in each held-out file;
- the shards' names and sizes, and each train folder against its floor;
- no `sequence_id` in two held-out files or in a held-out file and a train shard (first and last);
- each mask's length, digits, and single CDR3 run;
- `locus`;
- representative-first members.

## Compute

Measured on the first full build, on a workstation under podman with 16 CPUs and 100 GB of memory:
- **Time:** about 37 minutes.
  - Download, 32 parallel range requests: 11 min.
  - Stage: 9 min.
  - Hold out (ANARCII on 16 CPUs): 5 min.
  - AntiRef99: 3 min.
  - AntiRef96: 9 min.
- **Memory:** the container's peak reached its 100 GB limit. That peak counts page cache, and DuckDB spills past 80% of the limit, so 100 GB is enough but not much more than enough; ask 128 GB.
- **Disk:**
  - `.work/`: 89 GB (32.5 GB of downloads and 62.5 GB staged);
  - DuckDB's spill: up to about 90 GB;
  - the output: 40 GB (AntiRef96 24 GB, AntiRef99 16 GB).
- **Rows:** AntiRef96 210,559,202 in 211 shards; AntiRef99 315,983,206 in 316 shards. The test's floors are 90% of these.

## Gotchas

- **Zenodo is slow to CoreWeave.** On 2026-11-10 it served CoreWeave at 5–7 KB/s per connection and the Scripps network at about 520 KB/s, while CoreWeave reached other hosts at hundreds of MB/s. The 32.5 GB download would take about two days on CoreWeave, so build on bcr.
- **Held out by AntiRef90 cluster membership only.** No identity screen was run.
  - A train sequence can share a held-out sequence's V gene and a similar CDR3 at under 90% identity.
  - Because linclust is greedy and nested over six levels, a train sequence can even be 90% or more identical to a held-out representative and sit in another AntiRef90 cluster.
  - Antibody loss on these sets flatters the model. Compare runs on the same sets; don't read absolute values.
- Two clustering thresholds live in one dataset, against the datasets design's rule (D3), by the lab's decision for this pilot: every train option shares one set of eval and test files.
- No screen against OPLM's uniref70 or deepclust70 either: an antibody from UniProt may sit in both.
- AntiRef's filter: OAS unpaired, human, PBMC, no disease, no vaccine. There is no donor, no nucleotide sequence, no germline call, and no SHM mask; a donor holdout needs a rebuild.
- Light chains are low-diversity and easy for a model; read heavy-only CDR3 loss for the signal.
- In a production decay, 3% of rows exceeds AntiRef99's 316M, so the antibodies repeat. A pilot that subsamples takes a subset of shards.
