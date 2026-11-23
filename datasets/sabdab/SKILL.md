---
name: sabdab
description: "Every SAbDab2 antibody instance with its source summary annotations, CDR-H3 length, and the IMGT-numbered instance crop (with bound antigens). Filter the metadata and read only the matching antibody–antigen coordinates."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: cc-by-4.0
  count: 22866
  unit: structures
---
# SAbDab

Hub: `brineylab/sabdab`, tag `v1.0.0`.

## Files

`data/*.parquet` forms one table: one row per SAbDab2 antibody instance, keyed by `INSTANCE`. Group by `PDB_ID` for depositions or by `SABDAB_ID` for copies of a numbered variable region. Single-domain and unbound antibodies are included.

Every column of the upstream all-instance summary CSV is kept under its source name, with `PDB_ID` alongside the source's `PDB`. Empty source fields are null. A column uses an integer, float or date type only when every nonmissing value in that column converts; otherwise it is UTF-8 text. Two derived columns are appended:

- `cdrh3_length_aa`: length of the reported IMGT `CDR-H3` sequence, null when that sequence is missing;
- `cif`: the decompressed UTF-8 text of SAbDab2's IMGT-numbered instance crop (`instance_structures/*_abag.cif.gz` when it has bound antigens, otherwise `*_ab.cif.gz`).

`data/_snapshot.json` records the source URL, capture time, SAbDab2 `last_update` marker, instance count, summary and archive SHA-256 checksums, the summary column order, and sample CIF checksums.

## Reading it

```python
from pathlib import Path
import polars as pl
from huggingface_hub import snapshot_download

root = Path(snapshot_download("brineylab/sabdab", repo_type="dataset", revision="v1.0.0"))
instances = pl.scan_parquet(root / "data/*.parquet")
hits = (instances.filter((pl.col("heavy_taxid") == 9606)
                         & pl.col("cdrh3_length_aa").is_between(16, 19))
        .select("INSTANCE", "PDB_ID", "cdrh3_length_aa").collect())
if hits.height:
    key = hits["INSTANCE"][0]
    cif = instances.filter(pl.col("INSTANCE") == key).select("cif").collect().item()
    Path("selected.cif").write_bytes(cif.encode("utf-8"))
```

## Recipe

`recipe/build <out>` runs in `datascience@1.2.0`: it downloads `/api/download/all-summary`, creates one `/api/download/search-structures/jobs` job with `full_structure=false`, `antibody_instance_crops=true`, `include_antigen=true`, and downloads that job's single tar archive. It never requests a detail record or a structure per entry. Both the archive's own summary and the live summary must agree on all 22,866 rows, `/api/stats/summary` must report a stable `last_update` before and after collection, and every summary `INSTANCE` must match exactly one crop. Source inputs are cached under `<out>/cache/.work/`, and completed Parquet shards and `_snapshot.json` are moved into `<out>/data/` only after reconciliation. `params.toml` sets `api = "https://sabdab.opig.stats.ox.ac.uk/api"`; `last_update` and `summary_sha256` pin this capture. A source revision or checksum mismatch stops the build.

Source data by the Oxford Protein Informatics Group, used under [CC BY 4.0](https://sabdab.opig.stats.ox.ac.uk/about). [Capel et al., *SAbDab2: the structural antibody database in the age of machine learning*](https://doi.org/10.1093/nar/gkag1091).

`recipe/test <out>` checks the sharded table, common schema, unique `INSTANCE` values, the inventory digest, CDR-H3 lengths, and catalogued CIF samples against the source checksums and the summary's chain IDs.

## Compute

The first full capture is CPU-only in `datascience@1.2.0`, with up to 16 CPUs, 128 GiB memory and 24 hours on bcr. Its measured runtime, disk and memory are recorded with the version's capture; there are no GPU steps.

## Gotchas

- Antibody source species and expression host have separate fields. The example uses the heavy chain's source taxon.
- The IMGT CDR sequence may contain residues without resolved coordinates. Use SAbDab2 logical chain identifiers when joining to the instance CIF, including split scFv chains.
- Source columns that mix numeric and nonnumeric annotations remain text rather than dropping information.
- v1 intentionally has no API detail records, abstar annotation, clustering, deduplication, quality filters or splits.
