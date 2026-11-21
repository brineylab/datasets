---
name: afdb-rep-stok-large
description: "Every structure in afdb-rep@1.0.0 — the 2.28M AlphaFold DB v4 Foldseek-cluster representatives — as STok structure tokens: one discrete GCP-VQVAE Large token (4096-entry codebook) per residue, null where the residue lacks a complete backbone, split once by a hash of the id into train, validation and test, the two hold-outs carrying the observed N/CA/C coordinates. Reach for it to train or evaluate STok's paired sequence-structure models on AlphaFold-predicted structures, or any model that consumes structure tokens."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0 stok@1.0.0
  license: cc-by-4.0
  count: 2277197
  unit: structures
---
# afdb-rep-stok-large

Hub: `brineylab/afdb-rep-stok-large`, tag `v1.0.0`

## Files

`train/00000.parquet` … `train/00150.parquet`: 151 shards holding 2,254,438 rows. `validation/00000.parquet`: 1 shard, 11,495 rows. `test/00000.parquet`: 1 shard, 11,264 rows. `rejected/`: one `NNNNN.jsonl` per source shard that had rejections (57 files), `{"sequence_id", "reason"}` per line, 1,648 records in all. Rows are sorted by `sequence_id` within each split; 15,000 rows per shard (the last of a split partial), zstd, row groups of 2,000. Columns, in order:

- `sequence_id`: afdb-rep's `id`, the AlphaFold DB model id (`AF-A0A1Q3Z6G9-F1`).
- `sequence`: the modeled sequence, one-letter codes.
- `structure_tokens`: one int16 per residue — the GCP-VQVAE Large codebook index — `null` where the residue lacks a complete N/CA/C/O backbone, so the list stays aligned with `sequence`.
- `coordinates` (validation and test only): the observed N/CA/C per residue, `list<list<list<float32>>>`, `null` atoms where unobserved, so decoded folding can be scored against the AlphaFold model. Train drops it.
- `mean_plddt`, `uniprot_accession`: carried from afdb-rep unchanged.

Every shard's footer carries a `stok.tokenizer` metadata key — `preset large`, the checkpoint and codebook sha256s, `codebook_size 4096`, the stok version — and all shards agree on it; it is the tokenizer identity downstream training pins.

## Reading it

```python
from huggingface_hub import snapshot_download
from stok.data.format import read_source
path = snapshot_download("brineylab/afdb-rep-stok-large", repo_type="dataset", revision="v1.0.0")
train = read_source(f"{path}/train")   # stok's own reader: shards, rows, columns, tokenizer identity
```

STōk's `stok train` reads these directories directly as its plain dataset format (`src/stok/data/format.py`); `read_source` is the same code the trainer uses. With polars or pyarrow, read the columns like any Parquet.

## Recipe

**Source:** `brineylab/afdb-rep@v1.0.0` (its 152 shards, 2,278,845 rows: id, uniprot_accession, sequence, length, mean_plddt, full mmCIF text), pulled 2026-11-21 into `<out>/.work/hf-cache` and recorded in `<out>/.work/source.json`. The structures are DeepMind's AFDB v4 predictions, CC BY 4.0.

A split recipe, three programs in order — the tokenization needs a GPU the split does not, so it runs as its own step:

1. `recipe/build <out>` (datascience@1.2.0, CPU, network): stages the source, verifies its 152 shards and 2,278,845 rows, and — when `<out>/.work/tokens` holds nothing — prints the tokenize instruction and exits 0.
2. `recipe/tokenize <out>` (stok@1.0.0, one GPU): `stok tokenize-structures <source>/data <out>/.work/tokens --preset large --text-column cif --id-column id --keep-column mean_plddt --keep-column uniprot_accession --include-coordinates`, shard-parallel through the `NUM_JOBS`/`JOB_INDEX` environment (job I of N takes every N-th input shard; job 0 of 152 is the one-shard pilot). One output shard per input shard, named for it. STōk's fixed training-native policy — full chains of 25–1,280 residues, native sequence inputs, reference imputation, FP32, one structure at a time — so token identity never depends on batching or sharding. Rejected rows land in `.work/tokens/rejected/NNNNN.jsonl`; finished output shards are skipped on a rerun, so a preempted job simply runs again.
3. `recipe/build <out>` again (datascience@1.2.0, CPU): verifies the staged tokens — 152 shards, every footer parses, one tokenizer identity everywhere, token rows + rejected rows == the source's 2,278,845 (nothing lost) — then splits. The split is fixed once, from the id alone: `bucket = int.from_bytes(sha256(sequence_id)[:8], "big") % 1_000_000`; `bucket < 5000` validation, `bucket < 10000` test, else train — 0.5% each, deterministic, disjoint by construction, no id in two splits. Each hold-out must land within 0.5% ± 0.15% of all rows or the build stops. `train/` drops `coordinates`; the hold-outs keep it. Rows keep the tokens' (sorted) order. The stage then reads the output back from its footers: shards numbered without gaps, exact schemas, row counts, split sizes. A partial or stale split is wiped and redone from the tokens, so the stage starts over cleanly rather than resuming.

`params.toml`: `repository`, `revision`, `source_shards = 152`, `source_rows = 2278845`; the tokenizer identity (`preset = "large"`, `codebook_size = 4096`, the checkpoint sha256); `validation_bound = 5000`, `test_bound = 10000`, `split_tolerance = 0.0015`; `shard_rows = 15000`, `row_group_rows = 2000`; the test floors (`train_floor = 1900000`, `validation_floor = 9000`, `test_floor = 9000`); `limit = 0`.

**The test** (`recipe/test`, datascience@1.2.0) reads the shards' footers, light columns and sampled row groups: the three splits' shards are numbered without a gap; train's schema is exactly sequence_id, sequence, structure_tokens (list&lt;int16&gt;), mean_plddt, uniprot_accession, and the hold-outs' adds coordinates (list&lt;list&lt;list&lt;float32&gt;&gt;) after structure_tokens; every shard of every split carries the same `stok.tokenizer` identity naming the pinned Large checkpoint; each split is at least its floor and the hold-outs sit within 0.5% ± 0.15% of all rows; no sequence_id is in two splits or repeated within one, ids are sorted within each split, and no rejected sequence_id is among the rows — the split is a partition of the accepted ids; sampled rows are whole: structure_tokens one per residue and aligned with coordinates, tokens null or in [0, 4096), every all-null coordinate residue null in tokens too, mean_plddt in [0, 100], the id is `AF-<accession>-F1` matching uniprot_accession, the sequence uppercase letters. Where stok is importable (the stok image), it also runs STōk's own `read_source` over every split.

## Compute

Staged in three steps, measured on the campaign's runs (coreweave-barcelona):

- **Tokenize** (stok@1.0.0, one B200 each): ~6.7 structures per second per GPU — the one-shard pilot (job 0 of 152) took 14,981 structures in 37 minutes; the remaining 151 shards ran as 16 concurrent one-GPU jobs, each 5.2–6.2 hours, the whole set ~102 structures per second (91 GPU-hours in all, the pilot included); peak GPU memory 1,802 MiB.
- **Split** (datascience@1.2.0, CPU): 2 minutes — 152 token shards (14.4 GB) read, 153 shards written, on 8 CPUs and 32 G asked.
- **Test and push**: the test streams every split's `sequence_id` once (2,277,197 ids) plus footers and sampled row groups, on 8 CPUs and 32 G; the push uploads the output's 1.5 GB.

Disk under `<out>/.work/`: the source's 120.6 GB, the tokens' 14.4 GB (they carry the coordinates column for every row; the split drops it from train), all kept so a rerun resumes; the output itself is 1.5 GB.

## Gotchas

- **No pLDDT filter, by design**: every afdb-rep structure that parses and fits 25–1,280 residues is a row, whatever its confidence — pLDDT is carried as a column (`mean_plddt`) and filtering happens at training time (STōk's `min_plddt`).
- **Rejected structures are not rows**: 1,648 in all (1,629 `chains_too_long` — proteins over 1,280 residues — and 19 `chains_too_short`, proteins under 25; no parse failures), each with its reason in `rejected/NNNNN.jsonl`, counted, never silently dropped. Token rows + rejected == the source's 2,278,845.
- **The split is fixed once.** It is a hash of the id, so it is a structural hold-out: every afdb-rep entry is its own Foldseek cluster's representative, and a random split of the representatives is the standard non-redundant hold-out. Never re-draw it, and never let a hold-out `sequence_id` into train — the build and the test both check the partition. Sequence pretraining on UniRef50 against this hold-out belongs to `brineylab/uniref50-afdb-holdout-filtered`, built from exactly these validation and test sequences.
- `structure_tokens` is `null` where the residue lacks a complete N/CA/C/O backbone (AlphaFold models are nearly always complete, so nulls are rare); the token list stays aligned with `sequence` regardless.
- Token identity is deterministic per device (FP32, one structure at a time), but CPU and GPU may differ near ties and GPU generations may differ from each other; provenance is the footer's `checkpoint_sha256`/`codebook_sha256`, not raw token values. This version's tokens were produced on NVIDIA B200 GPUs.
- Train carries no coordinates by design; reach for `brineylab/afdb-rep` (the mmCIF text) if a train row's structure is ever needed again.
