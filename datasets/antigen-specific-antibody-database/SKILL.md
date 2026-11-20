---
name: antigen-specific-antibody-database
description: "The complete NaturalAntibody Antigen Specific Antibody Database 2.0 in Parquet. Use it to query antibody–antigen observations together with their reported measurements, chains, confidence and provenance."
metadata:
  version: 1.0.1
  tools: datascience@1.2.0
  license: cc-by-nc-4.0
  count: 1177819
  unit: records
---
# Antigen Specific Antibody Database

Hub target: `brineylab/antigen-specific-antibody-database`, tag `v1.0.1`. This recipe targets NaturalAntibody ASD 2.0.

## Files

`asd.parquet` contains one row per record in the upstream Delta snapshot, including repeated observations and incomplete records. NaturalAntibody reports 1,177,819 records across 29 sources. The upstream columns keep their names and nesting. Re-encoding may change row order and physical Parquet annotations such as nullability. [ASD release and schema](https://naturalantibody.com/asd/)

| Field | Interpretation |
| --- | --- |
| `dataset`, `confidence` | Upstream source abbreviation and ASD's confidence category for the observation. |
| `affinity_type`, `affinity`, `processed_measurement` | Upstream measurement label, original string, and ASD's numeric interpretation where available. The label gives the measurement scale and sometimes its units. Qualitative binding observations also occur here. |
| `chains.antibody_chains`, `chains.target_chains` | Maps of chain labels to sequences. ASD 2.0 documents antibody keys `heavy` and `light` and the target key `full`. |
| `chains.antibody_chains_numbered` | Upstream numbering and annotations keyed by antibody chain. |
| `nanobody`, `scfv` | ASD's antibody-format annotations. Interpret an absent light chain together with these flags. |
| `metadata.target_name`, `metadata.target_pdb`, `metadata.target_uniprot` | Target label and associated identifiers as supplied. |
| `metadata.source_url`, `metadata.article_url` | Source data and publication references when supplied. |

The Parquet footer records the upstream release label, source URL and SHA-256 fingerprint of the input table directory.

## Reading it

After publication, pin the lab release and select columns with PyArrow.

```python
from pathlib import Path
from huggingface_hub import snapshot_download
import pyarrow.parquet as pq

root = snapshot_download("brineylab/antigen-specific-antibody-database", repo_type="dataset", revision="v1.0.1")
observations = pq.read_table(Path(root) / "asd.parquet", columns=["dataset", "affinity_type", "affinity"])
```

## Recipe

NaturalAntibody distributes ASD 2.0 under CC BY-NC 4.0. This recipe changes the storage representation from Delta Lake to Parquet. Credit NaturalAntibody and retain the upstream source and article references. [Original release](https://naturalantibody.com/asd/) · [License](https://creativecommons.org/licenses/by-nc/4.0/)

Run `recipe/build <out>` in `datascience@1.2.0`. It downloads the public 2.0 release folder configured in `params.toml`, pulled 2026-11-17. For an already downloaded release, set `ASD_SOURCE` to the extracted directory containing the table. The recipe uses DuckDB's Delta reader to resolve the active snapshot, including removals. DuckDB fetches its matching official Delta extension on first use if needed. [DuckDB Delta extension](https://duckdb.org/docs/extensions/delta)

The build compares the logical schema, row counts by source and the entire multiset of exported rows with the source before replacing the output. The comparison includes nested fields and duplicate multiplicities. A verified download is kept under `<out>/.work/source` for reuse. The build logs the input fingerprint and UTC run time.

Run `recipe/test <out>` on the standalone output to check the release metadata, documented field paths, total record count and number of sources. Each source's row count is printed for the build record.

## Compute

One job, CPU only: 16 CPUs and 128G asked, on bcr's `cpu` partition. Measured on the first full build: about 9 min end to end, the Google Drive download and source SHA-256 fingerprint about 8 min of it, the Delta export, the full row-by-row comparison, the test and the push about 1 min. Peak memory was not measured (flyloft did not return `sacct`); 128G was enough. Disk: the verified download kept under `<out>/.work/source` (the upstream snapshot, 20 Parquet files plus the `_delta_log` and three CSVs, about 2.5 GB), the exported `asd.parquet` 264 MiB, and DuckDB's comparison spill under `<out>/.work/`.

## Gotchas

- Units and scales vary by measurement type and source. A numeric value alone is insufficient to interpret an observation.
- Nulls, empty sequences, and literal strings such as `"nan"` retain their source meanings. Study metadata can be incomplete.
- The release total includes the large BUZZ source. NaturalAntibody excludes BUZZ from several summary statistics on its website.
