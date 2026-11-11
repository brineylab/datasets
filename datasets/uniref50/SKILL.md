---
name: uniref50
description: "UniRef50 of UniProt release 2026_04 as sharded two-column parquet: one row per entry (a 50%-identity cluster's representative), sequence_id and sequence, in the FASTA's order. Reach for it to pre-train or evaluate a protein language model on UniRef50 at a pinned release."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: cc-by-4.0
---
# uniref50

Hub: `brineylab/uniref50`, tag `v1.0.0`

## Files

`data/00000.parquet` … `data/00041.parquet`: 42 shards holding 41,243,524 rows, one row per UniRef50 entry, in the FASTA's order. Every shard but the last holds exactly 1,000,000 rows (the last 243,524); zstd, row groups of about 100,000 rows. Columns:

- `sequence_id`: the FASTA header's first token, the entry id (`UniRef50_A0A5A9P0L4`).
- `sequence`: the entry's amino acids, its lines after the header joined.

## Reading it

```python
from huggingface_hub import snapshot_download
import polars as pl
path = snapshot_download("brineylab/uniref50", repo_type="dataset", revision="v1.0.0")
shard = pl.read_parquet(f"{path}/data/00000.parquet", columns=["sequence_id", "sequence"])
```

Rows keep the FASTA's order, so a subset of shards is a contiguous slice of the release, not a sample; shuffle yourself for training.

## Recipe

**Source:** UniRef release 2026_04 (published 2026-11-04), CC BY 4.0, pulled 2026-11-11: `uniref50.fasta.gz` (9,182,717,121 bytes, MD5 `0dd988dc772143255691f30c0fb9e396`) at https://ftp.uniprot.org/pub/databases/uniprot/uniref/uniref50/uniref50.fasta.gz, holding the release's 41,243,524 entries. The recipe refuses a download whose size or MD5 differs.

One job in `datascience@1.2.0`: download the FASTA into `<out>/.work/`, resuming a partial one by range; then stream it, never holding the whole file in memory, into `<out>/data/00000.parquet`, `00001.parquet`, … in the FASTA's order, `shard_rows` rows per shard (the last one partial), zstd, row groups of about 100k rows. Stages resume: a rerun keeps the verified FASTA and the shards already written, and a finished build only rereads the footers.

`params.toml`: `release = "2026_04"`; the file's `url`, `bytes`, and `md5`; `sequences = 41243524`, the release's count; `shard_rows = 1000000`.

**The test** reads the shards' parquet footers and three sampled row groups, in seconds: the shards are `00000.parquet` onward without a gap; the schema is exactly `sequence_id` and `sequence`, strings; every shard but the last holds exactly 1,000,000 rows; the total is exactly the release's 41,243,524; and in the samples every `sequence_id` starts with `UniRef50_` and every `sequence` is uppercase letters only.

## Compute

One job, CPU only: 8 CPUs and 32G asked, on bcr's `cpu` partition. From nothing it takes about 14 min: the download (8.6 GB, one stream from ftp.uniprot.org at about 18 MB/s) 8.5 min; the MD5 check and the 42 shards 5.5 min. Peak memory 5.8 GB. Disk: 6.6 GB of shards and 8.6 GB under `<out>/.work/`, the FASTA all of it, kept so a rerun resumes; the test reads only footers and three row groups, in 3 s.

## Gotchas

- The URL serves UniProt's current release only: once 2026_05 is out, the pinned MD5 refuses it, and a rebuild is a new version.
- The FASTA header's other fields (`n=`, `Tax=`, `TaxID=`, `RepID=`) are dropped; cluster sizes and taxonomy are in UniRef's XML, not here.
