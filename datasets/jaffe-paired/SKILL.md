---
name: jaffe-paired
description: "Paired human antibody heavy and light chains from four donors' sorted B cells (Jaffe et al. 2022), annotated with abstar, clustered at 85% identity and split by cluster, train reduced at 95%. Reach for it to train or evaluate a paired-chain antibody model."
metadata:
  version: 1.0.0
  tools: datascience@1.2.0
  license: mit
---
# jaffe-paired

Hub: `brineylab/jaffe-paired`, tag `v1.0.0`

## Files

`train.parquet`, `eval.parquet`, `test.parquet`: one row per pair, a heavy and a light chain from one droplet. Columns:

- `pair_id`: `<barcode>_<sample>` (`AAACCTGAGACACGAC-1_1279049`).
- `sample`, `donor` (1 to 4), `flow_class` (`naive`, `unswitched`, `switched`, `plasmablast`, `unswitched + naive`, `switched + naive`): the sample's row of the source's `test_data.csv`.
- `cluster_85`: the `pair_id` of the pair's 85% cluster representative. In eval and test every row is its own representative.
- `cluster_95` (train only): the `pair_id` of its 95% representative; every train row is its own.
- Every field abstar 0.9.0 writes, once per chain: the heavy chain's with `:0` appended (`v_call:0`, `cdr3_aa:0`, `sequence_vdj_aa:0`), the light chain's with `:1`. `sequence_vdj_aa` is the variable domain, FWR1 through FWR4.

## Reading it

```python
from huggingface_hub import snapshot_download
import polars as pl
path = snapshot_download("brineylab/jaffe-paired", repo_type="dataset", revision="v1.0.0")
train = pl.read_parquet(f"{path}/train.parquet", columns=["pair_id", "sequence_vdj_aa:0", "sequence_vdj_aa:1"])
```

Name the columns you need: each file holds some 340.

## Recipe

**Source:** Jaffe et al. 2022, figshare article 19617633 version 3 (DOI `10.6084/m9.figshare.19617633.v3`, MIT), pulled 2026-11-06: `test_data.tar.gz` (file 34846953, MD5 `4d87c4da2d407ba95180be2cb1c91044`), of which each sample's Cell Ranger `vdj_b/filtered_contig.fasta` (cell-associated contigs, productive, high-confidence, and full-length by Cell Ranger), and `test_data.csv` (file 34846938, MD5 `3ccae335a8a03b5a771dc0eae97f7af6`), the 94 samples' donors and flow classes. The recipe refuses a download whose MD5 differs.

**Steps**, one job in `datascience@1.2.0`:

1. Annotate every contig with abstar 0.9.0 (`germline_database = "human"`). 0.9.0 matters: it writes `sequence_vdj_aa`, the variable domain, which the clustering uses; in 0.9.0 `sequence_aa` is the translated input, as AIRR 2.0 defines it.
2. Pair within each sample: a droplet's barcode is the contig id up to its first underscore. Keep a droplet only with exactly one heavy chain (`IGH`) and one light (`IGK` or `IGL`), both productive by abstar. The build prints what it dropped, by shape (`dropped 1H2L: <n>`) and for productivity (`dropped unproductive: <n>`); the record carries those lines.
3. Cluster every pair with `mmseqs easy-cluster --min-seq-id 0.85 -c 0.8 --cov-mode 0` (`identity`, `coverage`; 80% of both sequences) on the heavy chain's `sequence_vdj_aa` joined to the light chain's. One `easy-cluster` run over every pair: `datascience@1.2.0`'s mmseqs (master, commit 2a3dafc) carries the fix to the prefilter overflow (MMseqs2 #1092) that kills release 18 and abutils' bundled build on about 1.1M of these sequences.
4. Split by cluster `[0.96, 0.02, 0.02]`: the representatives, sorted, are shuffled with `random.Random(seed = 1)`, and whole clusters go to train until it holds 96% of the pairs, then to eval until 2%, then to test. No 85% cluster spans two splits. Eval and test keep the 85% representatives.
5. Re-cluster every train pair at 95% (`train_identity`), the same way; train keeps the 95% representatives.

`params.toml` also holds `limit = 0`, the number of samples for a developer's dry run; 0 is all.

**The test** checks the three files and their columns, each split's rows against a floor, no `pair_id` or `cluster_85` in two splits, both chains productive, `locus:0` `IGH` and `locus:1` `IGK` or `IGL`, and each `sequence_vdj_aa` free of gaps and stops and ending with its chain's `fwr4_aa`.

## Compute

One job, CPU only: 32 CPUs and 200G asked, on coreweave-rtx6000 `hpc-low` (Xeon Platinum 8562Y+). From nothing it takes about 4 h 20 min: the download (12 GB) 6 min; abstar and the pairing, sample by sample, 2 h 10 min; the 85% clustering of all 1,389,546 pairs 7 min; the 95% clustering of train's 1.33M 1 h 50 min. Peak memory 81 GB, in the annotation. Disk: 1.5 GB of files and 19 GB of stages under `<out>/.work/`, the tarball 12 GB of it; a rerun resumes from the last finished stage.

## Gotchas

- Barcodes are unique only within a sample; `pair_id` carries the sample for that reason.
- The droplet rule drops about 9% of droplets (sample 1279049: 389 with two lights, 299 with two of each, 49 with two heavies, 118 with one chain, of 9,808).
- Eval and test hold one pair per 85% cluster, so they are far fewer rows than 2% of the pairs: they are cluster-level held-out sets.
- `donor` makes a held-out-donor split possible; that is another dataset, a copy of this one with the split changed.
- With podman on a laptop, run with `--pids-limit=-1`: abstar's workers pass podman's default limit of 2048 threads.
