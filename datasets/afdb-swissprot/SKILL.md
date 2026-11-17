---
name: afdb-swissprot
description: "The AlphaFold Protein Structure Database's v4 predictions of every Swiss-Prot entry as sharded parquet: one row per model with its id, UniProt accession, sequence, length, mean pLDDT, and the full mmCIF text, sorted by id. Reach for it to pull AlphaFold structures, sequences or pLDDTs for Swiss-Prot proteins in bulk, without per-entry downloads from EBI."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: cc-by-4.0
---
# afdb-swissprot

Hub: `brineylab/afdb-swissprot`, tag `v1.0.0`

## Files

`data/00000.parquet` … `data/00036.parquet`: 37 shards holding 542,378 rows, one row per AlphaFold DB v4 model of a Swiss-Prot entry (one model per entry, `F1`), sorted by `id` across all shards, so a point lookup reads one row group. Every shard but the last holds exactly 15,000 rows (the last 2,378); zstd, row groups of 2,000 rows. Columns:

- `id`: the model's id, the mmCIF's `_entry.id` (`AF-P42345-F1`; a few carry an isoform suffix, `AF-P12345-1-F1`).
- `uniprot_accession`: the entry the model is of: `id` without the `AF-` and the `-F1`.
- `sequence`: the modeled sequence, one-letter codes, `_entity_poly.pdbx_seq_one_letter_code`.
- `length`: `len(sequence)`, int64.
- `mean_plddt`: the model's global pLDDT, `_ma_qa_metric_global.metric_value`, 0–100.
- `cif`: the model's full mmCIF text, decompressed, byte-for-byte as the archive holds it (large_string).

## Reading it

```python
from huggingface_hub import snapshot_download
import polars as pl
path = snapshot_download("brineylab/afdb-swissprot", repo_type="dataset", revision="v1.0.0")
shard = pl.read_parquet(f"{path}/data/00000.parquet", columns=["id", "sequence", "mean_plddt"])
```

Selected rows back as `<id>.cif` files (the filters prune row groups on the id and accession statistics):

```python
from pathlib import Path
import pyarrow.parquet as pq
want = ["P42345", "Q9Y6K9"]  # UniProt accessions
for shard in sorted(Path(path, "data").glob("*.parquet")):
    picked = pq.read_table(shard, columns=["id", "uniprot_accession", "cif"],
                           filters=[("uniprot_accession", "in", want)])
    for row in picked.to_pylist():
        Path(f"{row['id']}.cif").write_text(row["cif"])
```

One row's cif parsed in memory:

```python
import io
import pyarrow.parquet as pq
from Bio.PDB import MMCIFParser
one = pq.read_table(f"{path}/data/00000.parquet", columns=["id", "cif"],
                    filters=[("id", "=", "AF-A0A060D764-F1")]).to_pylist()[0]
structure = MMCIFParser().get_structure(one["id"], io.StringIO(one["cif"]))
```

## Recipe

**Source:** EBI's AlphaFold Protein Structure Database v4 archive of the Swiss-Prot proteome, CC BY 4.0 (cite Jumper et al., Nature 2021, and Varadi et al., NAR 2024), pulled 2026-11-17: `swissprot_cif_v4.tar` (39,471,090,688 bytes, last modified 2025-08-24) at https://ftp.ebi.ac.uk/pub/databases/alphafold/v4/swissprot_cif_v4.tar, holding 542,378 entries, one `AF-<accession>-F1-model_v4.cif.gz` each. EBI publishes no checksum for it, so the recipe pins the byte size and verifies every member by decompressing it.

One job in `datascience@1.2.0`. The tar is downloaded into `<out>/.work/` by `download_streams` parallel HTTP range streams that join into one file, each resuming from where its slice stopped; its member names are scanned; then it is streamed again, never unpacking files to disk, and each member decompressed, checked (`_entry.id` matches the name, pLDDT in [0, 100], sequence one-letter, per-residue pLDDT count equals the sequence length) and staged: in rounds of `flush_members` members, rows go to per-shard chunk files under `<out>/.work/buckets/`, and `<out>/data/00000.parquet`, `00001.parquet`, … are assembled from the chunks at the end, rows sorted by id across all shards, `shard_rows` rows per shard (the last partial), zstd, row groups of `row_group_rows`. Every stage resumes: a rerun keeps the verified tar, the chunks of every finished round, and the shards already written. With `limit > 0` only the first `dry_bytes` of the tar are downloaded and only the first `limit` members are read: a developer's dry run.

`params.toml`: the tar's `url`, `bytes`, and `entries`; `shard_rows = 15000`; `row_group_rows = 2000`; `flush_members = 2000`; `download_streams = 16`; `dry_bytes = 536870912` (a dry run's prefix download); `limit = 0`.

**The test** reads the shards' footers and light columns, then 16 evenly spaced rows whole. From the footers and columns: the shards are `00000.parquet` onward without a gap; the schema is exactly the six columns above; every shard but the last holds exactly 15,000 rows; the total is the archive's 542,378 and never under 90% of it; every id matches `AF-<accession>[-<isoform>]-F<n>` and its `uniprot_accession`; the ids are sorted and unique across all shards; every `length` is `len(sequence)`; every `mean_plddt` is in [0, 100]. On the sampled rows: the `cif` parses with Biopython's `MMCIFParser`; its `_entry.id` is the id; its residues spell the `sequence` and number `length`; its global metric is `mean_plddt`; its atoms' B-factors (the per-atom pLDDT) mean to `mean_plddt` within 0.01; and its per-residue pLDDTs' plain mean is `mean_plddt` within 5.0.

## Compute

One job, CPU only: 8 CPUs and 32G asked. A single connection to ftp.ebi.ac.uk moves about 0.9 MB/s from this cluster (measured, 2026-11-17), so the recipe downloads the 39.5 GB tar as 16 parallel HTTP range streams, each resumable; the dry run's first 0.5 GB moved at 7.5 MB/s (14 MB/s once warm), so the download is about an hour. The names scan of 542,378 member headers, minutes; the rows stage (decompress, parse, stage, re-compress) at the rate the build prints per round (277 members/s in the dry run, about 35 minutes for all); assembling the 37 shards reads and re-compresses every chunk once. Peak memory a few GB: one round of 2,000 members is staged at a time. Disk: about 40 GB of shards, plus under `<out>/.work/` the 39.5 GB tar and, until assembly deletes them, about 40 GB of chunk files — a peak near 120 GB — kept so a rerun resumes (a shard's chunks are deleted once it is final). The test reads footers, light columns and 16 row groups, in about a minute.

## Gotchas

- PAE (predicted aligned error) matrices are out of scope: the mmCIFs do not carry them. For a v4 PAE, fetch `AF-<uniprot_accession>-F1-predicted_aligned_error_v4.json` from the GCS bucket `public-datasets-deepmind-alphafold-v4` (`gsutil cp` or `gcloud storage cp`); the bucket lists anonymously, but reading an object needs an authenticated account as of 2026-11-17. EBI's per-entry pages serve only the current release's PAE, and the v4 FTP directory holds no PAE archive for Swiss-Prot.
- The 39.5 GB tar is never uploaded to the Hub: the `cif` column already carries every byte of every member, and `scripts/push` leaves `<out>/.work/` out.
- `mean_plddt` is the CIF's global metric, which in v4 is the mean of the per-residue pLDDTs **weighted by each residue's atom count** — the atoms' B-factor mean — not their plain mean: over the dry run's first 3,000 entries the global matched the atom-weighted mean to 0.005 (the metric's 2-decimal rounding) while the plain mean sat 0.21 off at the median and 2.49 at the max. The test checks the atom-weighted mean to 0.01 and the plain mean to 5.0. Per-residue pLDDT is in each row's `cif`: the atoms' B-factors, or the `_ma_qa_metric_local` loop. (AFDB's later releases, v6 on, report the plain mean as the global, so v4's numbers sit slightly off the current website's.)
- This is the v4-era snapshot, last modified 2025-08-24: Swiss-Prot has grown since (576,073 entries at 2026-11), and entries added after v4 exist only in AFDB's newer releases, not here.
- The URL serves whatever v4 tar EBI currently hosts: if EBI ever replaces it, the pinned byte size refuses the download, and a rebuild is a new version.
