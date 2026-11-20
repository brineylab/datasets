---
name: afdb-rep
description: "The AlphaFold Protein Structure Database's v4 predictions of the 2.28M Foldseek cluster representatives of the AFDB proteome (foldcomp's afdb_rep_v4 lookup) as sharded parquet: one row per model with its id, UniProt accession, sequence, length, mean pLDDT, and the full mmCIF text, sorted by id. Reach for it to pull AlphaFold structures, sequences or pLDDTs for a non-redundant slice of the whole AFDB proteome in bulk, without 2.28M per-entry downloads from DeepMind's bucket."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: cc-by-4.0
---
# afdb-rep

Hub: `brineylab/afdb-rep`, tag `v1.0.0`

## Files

`data/00000.parquet` … `data/00151.parquet`: 152 shards holding 2,278,845 rows, one row per AlphaFold DB v4 model of a representative of a Foldseek cluster of the AFDB proteome (foldcomp's `afdb_rep_v4` lookup; every model `F1`), sorted by `id` across all shards, so a point lookup reads one row group. Every shard but the last holds exactly 15,000 rows (the last 13,845); zstd, row groups of 2,000 rows. Columns:

- `id`: the model's id, the mmCIF's `_entry.id` (`AF-A0A1Q3Z6G9-F1`; none in the lookup carries an isoform suffix).
- `uniprot_accession`: the entry the model is of: `id` without the `AF-` and the `-F1`.
- `sequence`: the modeled sequence, one-letter codes, `_entity_poly.pdbx_seq_one_letter_code`.
- `length`: `len(sequence)`, int64.
- `mean_plddt`: the model's global pLDDT, `_ma_qa_metric_global.metric_value`, 0–100.
- `cif`: the model's full mmCIF text, decompressed, byte-for-byte as DeepMind's bucket holds it (large_string).

## Reading it

```python
from huggingface_hub import snapshot_download
import polars as pl
path = snapshot_download("brineylab/afdb-rep", repo_type="dataset", revision="v1.0.0")
shard = pl.read_parquet(f"{path}/data/00000.parquet", columns=["id", "sequence", "mean_plddt"])
```

Selected rows back as `<id>.cif` files (the filters prune row groups on the id and accession statistics):

```python
from pathlib import Path
import pyarrow.parquet as pq
want = ["A0A1Q3Z6G9", "A0A009E921"]  # UniProt accessions
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
                    filters=[("id", "=", "AF-A0A009E921-F1")]).to_pylist()[0]
structure = MMCIFParser().get_structure(one["id"], io.StringIO(one["cif"]))
```

## Recipe

**Sources:** foldcomp's `afdb_rep_v4.lookup` (Kim et al., bioRxiv 2023) — the entry names of the representatives of the clusters Foldseek made of the AFDB proteome (Barrio-Hernandez et al., Nature 2023) — `https://steineggerlab.s3.amazonaws.com/foldcomp/afdb_rep_v4.lookup`, 96,263,277 bytes, sha256 `ee3b35f386fa8bd9c703b96e525893d5aca9f59bd5059a183049bf65cccd91c1`, last modified 2025-02-26, pinned by byte size and sha256, both checked before anything is fetched. The structures are DeepMind's original per-entry mmCIFs, CC BY 4.0 (cite Jumper et al., Nature 2021, and Varadi et al., NAR 2024), pulled 2026-11-20 one object per id from the GCS bucket `public-datasets-deepmind-alphafold-v4`, read through its S3-compatible XML API with AWS Signature V4 (region `auto`, service `s3`) signed by the cook's `GCS_HMAC_ACCESS_ID`/`GCS_HMAC_SECRET`, with `Accept-Encoding: gzip` (the objects are stored gzip-encoded): each CIF arrives byte-for-byte as the bucket holds it, gunzipped locally, never re-serialized through a parser. foldcomp supplies only the id list — no foldcomp-converted structure is in this dataset.

One job in `datascience@1.2.0`. The lookup is downloaded into `<out>/.work/` (kept there, so a rerun does not refetch it) and its second column taken as the id list: 2,278,845 `AF-<accession>-F1-model_v4` entry names, checked unique, sorted. The ids are then walked in sorted order, in rounds of `flush_members` ids: a round's `.cif.gz` files are fetched by `fetch_workers` persistent connections, each id with `fetch_attempts` attempts and backoff, over up to `fetch_passes` passes (what outlives them dies the build); a 404 at every attempt is the bucket truly lacking the object, recorded as a `.missing` marker. The round's files are then parsed (`_entry.id` matches the id, pLDDT in [0, 100], sequence one-letter, per-residue pLDDT count equals the sequence length) and staged as rows to per-shard chunk files under `<out>/.work/buckets/`; every shard whose `shard_rows` rows are complete is assembled into `<out>/data/NNNNN.parquet` — rows sorted by `id` across all shards (they are fetched sorted), `shard_rows` rows per shard (the last partial), zstd, row groups of `row_group_rows` — before the round's fetched files are deleted, so peak disk stays near the shards' own size plus one round. Every stage resumes: a rerun keeps the verified lookup, the staged `.cif.gz` files and `.missing` markers, the chunks of every finished round, and the shards already written. Ids the bucket lacks are written to `<out>/.work/missing.txt` and allowed while they stay under 0.1% of the list (`entries // 1000`); past that the build stops rather than publish. With `limit > 0` only the first `limit` sorted ids are built: a developer's dry run (its test fails on the `limit` alone, so nothing is pushed).

`params.toml`: the lookup's `url`, `bytes`, and `sha256`; the `bucket`; `entries = 2278845`; `shard_rows = 15000`; `row_group_rows = 2000`; `flush_members = 2000`; `fetch_workers = 64`; `fetch_attempts = 8`; `fetch_passes = 3`; `limit = 0`.

**The test** reads the shards' footers and light columns, then 16 evenly spaced rows whole. From the footers and columns: the shards are `00000.parquet` onward without a gap; the schema is exactly the six columns above; every shard but the last holds exactly 15,000 rows; the total is the lookup's 2,278,845 less the missing ids and never under 90% of it; every id matches `AF-<accession>[-<isoform>]-F<n>` and its `uniprot_accession`; the ids are sorted and unique across all shards; every `length` is `len(sequence)`; every `mean_plddt` is in [0, 100]. The missing ids, read from `<out>/.work/missing.txt`: each matches `AF-<accession>[-<isoform>]-F<n>`, they are sorted and unique, none is among the rows, and they stay under 0.1% of the archive; and when the lookup is still in `.work/`, the rows and the missing are checked against its members. On the sampled rows: the `cif` parses with Biopython's `MMCIFParser`; its `_entry.id` is the id; its residues spell the `sequence` and number `length`; its global metric is `mean_plddt`; its atoms' B-factors (the per-atom pLDDT) mean to `mean_plddt` within 0.01; and its per-residue pLDDTs' plain mean is `mean_plddt` within 5.0.

## Compute

One job, CPU only: 32 CPUs and 64G asked, under a day — the 64G because a shard whose chunks arrive out of id order is sorted whole in memory (a shard's 15,000 CIFs are a few GB; the ids are fetched sorted, so most shards never take that path). The lookup is 96 MB, seconds. The fetch stage is bound by the bucket's per-object latency more than bandwidth: 64 parallel persistent connections to `storage.googleapis.com`, one signed GET each with `Accept-Encoding: gzip` (an object is ~65 KB gzipped, ~4x smaller than the CIF text it holds), so the 2.28M objects take on the order of 5–6 hours; the parse-and-stage stage runs under the fetches, a round of 2,000 members at a time. Disk: about 150 GB of shards, plus under `<out>/.work/` the lookup, one round's fetched cifs (about 130 MB), and the chunks of the rounds since the last complete shard (a few GB) — a peak near 155 GB — kept so a rerun resumes (each round's fetched files are deleted once its rows are staged, and a shard's chunks once it is final). The test reads footers, light columns and 16 row groups, in about a minute.

## Gotchas

- Recooking needs a Google Cloud HMAC key in the environment, `GCS_HMAC_ACCESS_ID`/`GCS_HMAC_SECRET`: the bucket's `gs://` reads need any authenticated Google identity, and its S3-compatible XML API — what the recipe speaks — answers AWS Signature V4 signed with one. The recipe reads the keys from the environment and never prints or writes them.
- Ids the bucket lacks are in `<out>/.work/missing.txt` (the build prints them too): under 0.1% of the list the build continues and the dataset is that many rows short — the Files section's counts then overstate by exactly the missing; past 0.1% the build stops rather than publish, and the missing list is a note to the next version, not a silent hole.
- PAE (predicted aligned error) matrices are out of scope: the mmCIFs do not carry them. For a v4 PAE, fetch `AF-<uniprot_accession>-F1-predicted_aligned_error_v4.json` from the same GCS bucket `public-datasets-deepmind-alphafold-v4` (`gsutil cp` or `gcloud storage cp` with an authenticated account, or the S3-compatible API with an HMAC key). AFDB's per-entry pages serve only the current release's PAE.
- `mean_plddt` is the CIF's global metric, which in v4 is the mean of the per-residue pLDDTs **weighted by each residue's atom count** — the atoms' B-factor mean — not their plain mean: over afdb-swissprot's dry run of v4 entries the global matched the atom-weighted mean to 0.005 (the metric's 2-decimal rounding) while the plain mean sat 0.21 off at the median and 2.49 at the max. The test checks the atom-weighted mean to 0.01 and the plain mean to 5.0. Per-residue pLDDT is in each row's `cif`: the atoms' B-factors, or the `_ma_qa_metric_local` loop. (AFDB's later releases, v6 on, report the plain mean as the global, so v4's numbers sit slightly off the current website's.)
- The 2.28M fetched `.cif.gz` files are never uploaded to the Hub: the `cif` column already carries every byte of every object, and `scripts/push` leaves `<out>/.work/` out.
- This is the v4-era snapshot: the representatives are foldcomp's `afdb_rep_v4` list, fixed at its 2025-02-26 upload, of v4 models. Entries added to AFDB after v4, and clusters remade on a newer release, are not here; for every Swiss-Prot entry instead of a representative per cluster, reach for `brineylab/afdb-swissprot`.
- The lookup's URL serves whatever S3 currently hosts: if it were ever replaced, the pinned byte size and sha256 refuse the download, and a rebuild is a new version.
