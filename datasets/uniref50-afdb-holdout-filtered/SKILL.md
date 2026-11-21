---
name: uniref50-afdb-holdout-filtered
description: "UniRef50 of UniProt release 2026_04 (uniref50@1.0.0) minus every entry that is a close homolog — MMseqs2 at >=50% sequence identity and >=80% coverage on both sides — of an afdb-rep-stok-large validation or test protein: 41.2M sequences for pretraining that cannot leak the structure dataset's held-out split. Reach for it to pre-train a sequence model before joint training on afdb-rep-stok-large."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: cc-by-4.0
  count: 41217001
  unit: sequences
---
# uniref50-afdb-holdout-filtered

Hub: `brineylab/uniref50-afdb-holdout-filtered`, tag `v1.0.0`

## Files

`data/00000.parquet` … `data/00041.parquet`: 42 shards holding 41,217,001 rows, one row per surviving UniRef50 entry, in uniref50's own FASTA order. Every shard but the last holds exactly 1,000,000 rows (the last 217,001); zstd, row groups of 100,000. Columns, exactly uniref50's two:

- `sequence_id`: the FASTA header's first token, the entry id (`UniRef50_A0A5A9P0L4`, UniRef's `-N` disambiguation suffix included).
- `sequence`: the entry's amino acids, its lines after the header joined.

## Reading it

```python
from huggingface_hub import snapshot_download
import polars as pl
path = snapshot_download("brineylab/uniref50-afdb-holdout-filtered", repo_type="dataset", revision="v1.0.0")
shard = pl.read_parquet(f"{path}/data/00000.parquet", columns=["sequence_id", "sequence"])
```

Rows keep uniref50's order, so a subset of shards is a contiguous slice of the release, not a sample; shuffle yourself for training.

## Recipe

**Sources:** `brineylab/uniref50@v1.0.0` (UniRef50 of UniProt release 2026_04, all 42 shards, 41,243,524 entries, CC BY 4.0) and `brineylab/afdb-rep-stok-large@v1.0.1` — its `validation/` and `test/` splits only (22,759 sequences; the train shards are never pulled) — both through `snapshot_download` into `<out>/.work/hf-cache` and recorded in `<out>/.work/sources.json` with the pull date, shard counts and rows. The hold-out shards must carry `stok.tokenizer` metadata naming the pinned GCP-VQVAE Large checkpoint, so the filter chains exactly that published split; a re-drawn afdb-rep-stok-large split is a new version of both datasets.

One job in `datascience@1.2.0` (CPU, network), five resumable stages under `<out>/.work/`:

- **holdout**: the validation and test proteins streamed to `holdout.fasta` — ids checked unique across the union — and counted in `holdout.json` (22,759 sequences, 6.7 MB, sha256 `d4f98de2055186ab12399f0feead4ee7a240c31365d9b7a316a196acdcde0fa8` in this build).
- **mmseqs**: the holdout queries as one MMseqs2 query DB, searched against every uniref50 source shard in turn (one target DB per shard, a scratch directory per chunk — `search` takes four paths: query, target, result, scratch — deleted with the chunk's other litter), MMseqs2 `2a3dafc46f9a1bc79af96b4c11a24d63a7b0b4d4`, every shard with the same flags: `--min-seq-id 0.5 -c 0.8 --cov-mode 0 -s 7.5 -e 100 --max-seqs 2000` on the node's CPUs (capped at 64). Every reported alignment's identity and both coverages are re-checked in code against the same thresholds. A shard's hit target ids land in `.work/mmseqs/chunks/NNNNN.ids`, written atomically — a checkpoint a preempted run resumes from, one shard at a time. The staged search records the sha256 of the holdout FASTA it ran against; a build whose holdout digest differs wipes the staged search rather than resuming from it, so the filter always follows the holdout this build chained. The searches may be strided across runs (`MMSEQS_SHARD_OFFSET` and `MMSEQS_SHARD_STRIDE`: job I of N searches every N-th shard), the removed set written only when every shard's chunk is staged. Their sorted union becomes `.work/removed-ids.txt`: 26,523 uniref50 entries removed as close homologs of a held-out protein. The version and every flag are recorded in `.work/mmseqs/parameters.json`. The e-value is permissive (100) on purpose: the identity and coverage criteria are the filter, and the e-value only decides what MMseqs2 reports.
- **write**: uniref50's rows in their own order, minus the removed ids, as `data/NNNNN.parquet` — 1,000,000 rows per shard (the last partial), zstd, row groups of 100,000, each shard written to a temp name and moved into place whole, so a rerun resumes at the first missing shard (the summary's rows count the survivors on disk plus what the run wrote, so a resumed build reports the total). Every removed id must match exactly one source row. Eight sampled removed ids are kept with their sequences in `.work/removed-sample.json` for the test to re-search.
- **verify**: the output read back from its footers — shards numbered without gaps, the schema exactly uniref50's two columns, every shard but the last exactly 1,000,000 rows, and the total exactly the source's 41,243,524 less the removed count.

`params.toml`: the two repositories and revisions; `uniref50_shards = 42`, `uniref50_rows = 41243524`; `holdout_floor = 9000`; the pinned checkpoint sha256; `min_seq_id = 0.5`, `coverage = 0.8`, `cov_mode = 0`, `sensitivity = 7.5`, `evalue = 100.0`, `max_seqs = 2000`; `sample_size = 8`; `shard_rows = 1000000`, `row_group_rows = 100000`; `rows_floor = 38000000`; `limit = 0`.

**The test** (`recipe/test`, datascience@1.2.0) reads the shards' footers and sampled rows: the shards are numbered without a gap; the schema is exactly `sequence_id` and `sequence`; every shard but the last holds exactly 1,000,000 rows; the total is over the floor and never over uniref50's own 41,243,524; sampled ids are `UniRef50_` entry ids (the `-N` suffix included) and sequences are uppercase letters only. Where the build's `.work` is staged (the cook, and any rerun), the filter itself is judged too: `removed-ids.txt` is sorted, unique and all `UniRef50_` entry ids, and rows + removed exactly 41,243,524; the output's ids are streamed against the source's, in order — every output row is a source row, every skipped source row is removed, no removed id is among the rows — so the output is exactly uniref50 minus the removed set; and every sampled removed id is re-searched with its sequence under the filter's own MMseqs2 flags against a rebuilt holdout query DB and must again hit a holdout protein, so the removals are real homologs, not a plumbing accident.

## Compute

One job in `datascience@1.2.0`, CPU only. Measured on the campaign's runs (coreweave-barcelona):

- **Sources**: uniref50@1.0.0 is 7.1 GB (42 shards); pulled warm where the cluster's shared cache holds it, otherwise a fresh 7.1 GB download. The afdb-rep-stok-large hold-out splits are a small pull (~148 MB).
- **mmseqs**: 22,759 queries against 42 target shards, one DB per shard. Run strided as seven 32-CPU jobs (`MMSEQS_SHARD_OFFSET`/`MMSEQS_SHARD_STRIDE` 7), each 6–7 minutes (354–417 s): the query `createdb` once, then seconds per shard search at sensitivity 7.5. The campaign staged this stage's chunks under `<out>/.work` before submitting, so the cook resumed instead of recomputing.
- **write** and **verify**: the write streams uniref50's 7.1 GB and writes the 7.1 GB output (42 shards); a full pass is minutes — a resumed one, writing nothing, re-streams the source in ~40 s. The verify reads footers, sub-second.
- **test**: 37 s — it streams every id of source and output once, plus the re-search of the eight sampled removed ids.

Disk: the output's 7.1 GB, plus under `<out>/.work/` the uniref50 snapshot's 7.1 GB, the holdout FASTA's 6.7 MB and one shard's transient FASTA and MMseqs2 databases (deleted as each shard finishes); the campaign's staged `.work` measured 21.3 GB in all. All kept while `.work` stages resumption.

## Gotchas

- **The removal rule is the dataset**: a uniref50 entry is gone when a holdout protein aligns to it at ≥50% identity with both coverages ≥80% (`--cov-mode 0`). 26,523 entries were removed (0.064% of the release). The e-value is permissive (100) on purpose — the identity and coverage criteria are the filter, and the e-value only decides what MMseqs2 reports.
- `--max-seqs 2000` caps the targets reported per query per shard; a holdout protein with more than 2,000 above-threshold homologs inside one uniref50 shard would have the rest of them kept. At UniRef50's clustering (one representative per 50%-identity cluster) this is not expected to bind.
- The chain is versioned on both ends: this is uniref50@1.0.0 (UniProt release 2026_04) filtered against afdb-rep-stok-large@1.0.1's hold-out. Either moving — a new UniProt release, or a re-drawn structure split — is a new version of this dataset, and re-filtering is not optional: skipping it is how sequence pretraining leaks the structure hold-out the comparison depends on.
- The hold-out sequences themselves are never rows here; they live in `brineylab/afdb-rep-stok-large`'s validation and test splits.
