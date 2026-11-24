---
name: epam-pcps
description: "The six EPAM parent-child-pair corpora (FlAIRR, RACE, Tang, Wyatt/Jaffe, and Replay IGH/IGK) as ordered parquet, with one canonical whole-clonal-family 20,000-pair-target subsample each of Tang and Wyatt. Reach for it to evaluate antibody-evolution models on identical EPAM inputs without fetching and resampling the deposit independently."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: cc-by-4.0
  count: 743080
  unit: pairs
---
# epam-pcps

Hub: `brineylab/epam-pcps`, tag `v1.0.0`

EPAM (Sung et al., *PLOS Computational Biology* 2025; the deposit credits Johnson et al.) evaluates the real parent-to-child step of antibody somatic hypermutation. One row here is one parent-child pair (PCP), carrying the parent and observed-child BCR nucleotide sequences and their clonal-family annotations. The six-corpora total is 743,080 PCPs; the subsamples are views of already-counted rows.

## Files

```
flairr/pcps.parquet
race/pcps.parquet
tang/pcps.parquet              tang/subsample-20k.parquet
wyatt/pcps.parquet             wyatt/subsample-20k.parquet
replay_igh/pcps.parquet        replay_igk/pcps.parquet
provenance.json                source identity, every published file's sha256 and rows, and the exact subsample declaration
```

Only Tang and Wyatt have subsamples; the four smaller corpora are used whole. Every parquet has the deposit's original rows, in source order, and the same ordered 19 columns:

`sample_id`, `family` (clonal family within a sample), `parent_name`, `parent`, `child_name`, `child` (BCR nucleotide sequences), `branch_length`, `depth`, `distance`, `v_gene`, `j_gene`, `cdr1_codon_start`, `cdr1_codon_end`, `cdr2_codon_start`, `cdr2_codon_end`, `cdr3_codon_start`, `cdr3_codon_end`, `parent_is_naive`, `child_is_leaf`.

`branch_length` and `distance` are float64; `depth` and the six codon-boundary fields are int64; the two flags are booleans; the other nine columns are strings. The deposit's CSVs have a leading unnamed pandas row-index column; the parquet conversion excludes that index and reads all 19 named PCP columns unchanged. Values are read with DuckDB's ordinary CSV parsing (including its ordinary missing-value handling), without filtering, cleaning, or reordering. `provenance.json` carries this reader declaration, every file's sha256 and row count, and each corpus's source archive member and sha256.

| Corpus | Rows | Species / locus | Source study and source CSV sha256 | Known training-data overlap |
|---|---:|---|---|---|
| `flairr` | 2,798 | human IGH | Ford et al. 2023; `3ee40a2db0f943d665e3ff0aebcbf18986e1259c6cfd89708bd8019d7d30a815` | EPAM reports an out-of-sample evaluation; no overlap asserted. Other models were not audited. |
| `race` | 20,656 | human IGH | Rodriguez et al. 2023; `e92f20a68d88538839fa1dd89981bfec3bc3c2b50cb6ce888f24f66c48bce675` | EPAM reports an out-of-sample evaluation; no overlap asserted. Other models were not audited. |
| `tang` | 505,915 | human IGH | Tang et al. 2022 and Vergani et al. 2017; `b91b41b71ba7e91dc0075f7564b3f37e098853fc2eebb62af5800d5936a0a9c7` | Part of Tang is included in the OAS used to train AbLang2. |
| `wyatt` | 193,601 | human IGH | Jaffe et al. 2022 (EPAM's Wyatt prefix); `753c751f6601d5eb3988c9967edc570a58eb84ea8def51b1ee7e70c007107d0f` | Jaffe forms a substantial part of AbLang2's training data and is the productive-sequence training data for Thrifty-prod. |
| `replay_igh` | 10,056 | mouse IGH | GC Replay, DeWitt et al. 2025; `acef28498c0b8d8f1f448dd3f327b6952d04fca008367ab1a1f51d87fd1a7de1` | No training-data overlap for a nominee model was asserted by this snapshot. Models fitted to Replay require their own assessment. |
| `replay_igk` | 10,054 | mouse IGK | GC Replay, DeWitt et al. 2025; `564183cad60695584444bb360bffc4ee8ec7870d5d7504bf4d30259133228845` | No training-data overlap for a nominee model was asserted by this snapshot. Models fitted to Replay require their own assessment. |

The CSVs themselves are **not published**; their checksums are acceptance checks against the deposit, not an alternate raw-data copy.

**Canonical subsamples.** `tang/subsample-20k.parquet` and `wyatt/subsample-20k.parquet` hold whole rows with all 19 columns, selected by whole clonal family. The family key is the `(sample_id, family)` pair, never `family` alone. Distinct families in first-corpus-row encounter order are sorted by the lowercase hexadecimal SHA-256 digest of:

```
f"{seed}:{len(sample_id)}:{sample_id}{len(family)}:{family}"
```

where the length is in Unicode characters, seed and lengths are ordinary decimal strings, and the whole string is encoded UTF-8. Seed `20261124`, target 20,000 PCPs. Walk this hash order and add each complete family while the total is below the target; if adding a family crosses it, retain that family whole and stop. Never trim pairs to 20,000. Within each subsample, rows remain in the original corpus's order. An actual full-hash collision would stop the draw. Every selected family, its measured overshoot, and the file checksum are checked by the recipe test and recorded in `provenance.json`.

This draw is new: it does not reproduce campaign `aa191851` (seed 0) or `c8eae861` (seed 20261120), which used different and partly unrecorded procedures. Those older tables remain traceable but are not presented as pairwise comparable. In the full corpora, composite family keys give Tang 142,857 families and Wyatt 50,692; `family` alone would incorrectly merge them into 43,692 and 49,206 groups respectively.

## Reading it

```python
from huggingface_hub import snapshot_download
import polars as pl

path = snapshot_download("brineylab/epam-pcps", repo_type="dataset", revision="v1.0.0")
tang = pl.read_parquet(f"{path}/tang/subsample-20k.parquet")

# Load corpus by corpus, not a recursively globbed panel: the two subsamples repeat rows.
replay = pl.read_parquet(f"{path}/replay_igh/pcps.parquet")
```

Use the subsamples for repeatable reduced-cost Tang/Wyatt benchmarks and `pcps.parquet` for the whole corpus. These are evaluation PCPs, not a train/eval/test split.

**Repeat the source comparison.** In a Python environment with DuckDB, download only `https://zenodo.org/api/records/17353498/files/pcps.tar.gz/content`; set `root` to this downloaded Hub dataset and `archive` to that verified archive. This is the same typed read used by the build, without repository code:

```python
import hashlib, json, tarfile
from pathlib import Path
import duckdb

root, archive = Path(root), Path(archive)
declared = {
    "branch_length": "DOUBLE", "depth": "BIGINT", "distance": "DOUBLE",
    "cdr1_codon_start": "BIGINT", "cdr1_codon_end": "BIGINT",
    "cdr2_codon_start": "BIGINT", "cdr2_codon_end": "BIGINT",
    "cdr3_codon_start": "BIGINT", "cdr3_codon_end": "BIGINT",
    "parent_is_naive": "BOOLEAN", "child_is_leaf": "BOOLEAN",
}
# DuckDB names the leading empty-header integer index column0 for an in-memory CSV.
# It is declared for row alignment but excluded from the published 19-column table.
declared["column0"] = "BIGINT"
meta = json.loads((root / "provenance.json").read_text())
assert hashlib.sha256(archive.read_bytes()).hexdigest() == meta["source"]["sha256"]
# Text fields are declared VARCHAR. Python repr produces DuckDB-valid quoted identifiers and SQL types here.
declarations = ", ".join(repr(c) + ": " + repr(declared.get(c, "VARCHAR"))
                         for c in meta["conversion"]["columns"])
with tarfile.open(archive, "r:gz") as tar, duckdb.connect() as db:
    members = {m.name: m for m in tar.getmembers()}
    for corpus, source in meta["corpora"].items():
        csv_bytes = tar.extractfile(members[source["source_member"]]).read()
        assert hashlib.sha256(csv_bytes).hexdigest() == source["source_sha256"]
        selected = ", ".join('"' + c + '"' for c in meta["conversion"]["columns"])
        expected = db.sql(
            f"SELECT {selected} FROM read_csv(?::BLOB, header=true, all_varchar=true, columns={{{declarations}}})",
            params=(csv_bytes,),
        ).fetch_arrow_table().combine_chunks()
        actual = db.read_parquet(str(root / corpus / "pcps.parquet")).fetch_arrow_table().combine_chunks()
        assert actual.schema == expected.schema and actual.equals(expected)
        print(f"{corpus}: all {source['source_rows']} ordered rows and values match")
```

The build ran this complete row-and-value comparison as its conversion check; the separate recipe test checks the standalone outputs and independently redraws both subsamples from them.

## Recipe

**Source:** the EPAM deposit, Zenodo record 17353498 (DOI `10.5281/zenodo.17353498`, CC BY 4.0), member `pcps.tar.gz`, pulled 2026-11-24:

- URL `https://zenodo.org/api/records/17353498/files/pcps.tar.gz/content`;
- 54,015,727 bytes, MD5 `c9f5a5798e4a387b14a66a27f97c1acf` (Zenodo's checksum), SHA-256 `73f94dff6912b1e4e6872c9c952e4c3a10c06c4a209e47a765dbc34f5bea532c`;
- exactly ten archive members: six source CSVs and four directory entries. No other deposit member is fetched.

The archive and each source CSV must match its pinned byte count/digest exactly before conversion. The six source filenames and sha256 values are fixed in `recipe/common.py` and mirrored in `provenance.json`.

**Steps**, one CPU job in `datascience@1.2.0`: verify the archive, read the six CSVs using the declared DuckDB types, write zstd-compressed parquet, compare every ordered value and datatype with a fresh typed read of its source, then draw the two canonical subsamples once from the successfully converted corpora and write them. Write `provenance.json` with the source provenance, ordered-row comparison declaration, subsample seed/key/order/accumulation and crossing-family rules, subsample rows/families/overshoot, and all published file rows and sha256. The archive and verified source snapshots remain under `<out>/.work/` and are not uploaded.

**The test** checks the eight parquet file names and `provenance.json`, exact corpus rows and 743,080 total, string-column and ordered numeric/boolean schemas, all published-file rows and sha256 in the manifest, source CSV sha256 provenance, Tang/Wyatt composite-family counts versus incorrect family-only counts, complete-family membership, and an independent exact redraw of every subsample row in original order.

## Compute

One CPU-only job in datascience, 16 CPUs and 16 GB requested. Only the pinned 54,015,727-byte archive is downloaded. The expected dominant memory is the largest corpus, 505,915 PCPs; final measured elapsed time, memory and disk are recorded in the cook record. Source and conversion staging under `<out>/.work/` is not published. The archive is retained for clean reruns.

## Gotchas

- **One panel by PI decision (ngk5, 2026-11-24), not split under design rule D3.** Four human and two mouse evaluation corpora share one recipe identity (one archive at one pull date), rather than being recipe-parameter variants. Splitting this panel would recreate version drift; use explicit corpus paths instead.
- **Do not use `family` as the global family key.** It repeats across samples. `(sample_id, family)` is the sampling and family-completeness unit.
- The subsample is not exactly 20,000 rows: the crossing family is retained whole. Consult `provenance.json` for the measured result.
- Contamination notes describe known EPAM comparisons, not a universal contamination screen. Tang partly overlaps AbLang2; Wyatt/Jaffe overlaps AbLang2 and Thrifty-prod. Absence of a listed overlap is not evidence of universal independence.
- Subsamples repeat rows from full-corpus parquet files. Never count both when counting corpus PCPs.
- Only `pcps.tar.gz` is needed or permitted by this recipe. Do not retrieve the deposit's very large `aaprobs.tar.gz`, `dataframes_and_tables.tar.gz`, or `models_setup.tar.gz`.
