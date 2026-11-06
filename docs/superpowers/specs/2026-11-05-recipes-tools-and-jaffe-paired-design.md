# Recipes, general-purpose tools, and `jaffe-paired`: a revision to plan A

Status: from a design conversation with the lab's PI, 2026-11-05, whose approval stands for the lab's. It changes decisions in `docs/VISION.md` and `docs/DESIGN.md` (both lab-approved, D4 among them), in the toolshed's design and AGENTS.md (an image's `HF_HUB_OFFLINE`), and in flyloft's `docs/design/datasets.md`; the revised plan edits this repository's and the toolshed's first. Calls made in writing that nobody discussed are marked **(call)**.

## 1. Why

Plan A's Tasks 1–4 are built and on `main` (`1e6f722`): `check.py`, `build`, `test`, `record`, `push`, `promote`, and the workflow. Before building the recipe image (Task 5) and the first real dataset (Task 7), the conversation surfaced three things the plan got wrong for the lab:

1. **A recipe image per dataset.** "A recipe is one program in one tool's image" (D4) led the plan to an `abstar` image holding abstar, mmseqs2, polars, and `huggingface_hub` for one recipe's sake. The lab wants toolshed images to stay general and reusable, never shaped around one recipe.
2. **This repository running recipes.** `scripts/build` wraps a recipe in `podman run`, keeps a `.built` marker, and skips a second run; `scripts/test` runs a recipe's test. A recipe is instructions, not an oven: running it belongs to whoever cooks (flyloft, a person's agent, a person at a terminal), and whether it runs as one job or several is the recipe author's call. This repository holds recipes, records, and the deterministic steps that file and publish a result; it never runs, schedules, or orders a recipe's work.
3. **The first real dataset.** `oas-paired-human` needs held-out donors and other choices still unsettled. `jaffe-paired`, from Jaffe et al., "Functional antibodies exhibit light chain coherence" (Nature, 2022), is smaller, single-source, and the lab already builds it the same way each time; it replaces OAS as the first real dataset. OAS follows later, as its own design.

## 2. Decisions

Decided by the lab in the conversation:

- **General-purpose toolshed images.** The toolshed gains a few general images for the work between specialized tools. The first is `datascience`: the scientific Python stack, the lab's own packages (abstar, abutils), and sequence clustering and search tools (mmseqs2, DIAMOND). A later `deeplearning` image is `datascience` plus torch and CUDA, for jobs that need a GPU but no particular model tool. Specialized tools (esm2, boltz) stay as they are.
- **The shape of a recipe is its author's call.** One job is the default. Splitting into several jobs makes sense for a very long step whose resumption matters, or for steps with different compute (CPU annotation and clustering, then GPU embedding). This repository's guidance says so; it provides no mechanism that runs or orders steps. A split recipe is several programs and prose saying their order, their tools, and their compute. Chaining datasets (one dataset built from another's published version) is also open to an author.
- **`scripts/build` and `scripts/test` go, entirely**, with their podman modes and the `.built` marker. The recipe's test stays part of the recipe: the cook runs it and its output goes into the record.
- **`push`, `record`, `check`, and `promote` stay.** `push` is the deterministic step every cook calls to file a result on the Hub; `record` writes the record in its one format; `check` proves a pull request's record against the Hub on every pull request; `promote` tags the version on merge.
- **The committed-inputs guard moves into `push`**: it refuses a recipe directory with uncommitted changes and names the candidate branch by the committed recipe's tree. `push` takes the output directory directly.
- **Review stays: someone other than the builder reviews before merge.** A critic agent reviewing an implementing agent's work counts. No human approval is required for any merge or promotion, and nothing stalls a campaign waiting for one.
- **`metadata.tool` becomes a list now**, so no skill ever needs migrating and no reader supports two shapes.
- **`jaffe-paired`** is the first real dataset, as §4 describes.
- **abstar 0.9.0** (released 2026-11-05) provides `sequence_vdj` and `sequence_vdj_aa`, the assembled V(D)J region, which is what the recipe clusters. 0.8.0's `sequence_aa` held the same thing, but 0.9.0 gives `sequence` and `sequence_aa` their AIRR 2.0 meanings (the input, and its translation from V's start to the read's end), so the recipe pins 0.9.0 and names the new field.

## 3. Goals, non-goals, anti-goals

**Goals.**
- A toolshed image any lab job can use for data work, and a recipe that runs in it.
- `jaffe-paired@v1.0.0` on the Hub under `brineylab`, built, tested, filed, reviewed by a critic, merged, and tagged, without a human gate.
- This repository's scripts reduced to filing, recording, checking, and promoting.
- Guidance an agent can follow to write a recipe, decide its shape, cook it anywhere, and file it.

**Non-goals.**
- `deeplearning` (no recipe needs it yet: built when the first GPU recipe arrives) **(call)**.
- `oas-paired-human`, held-out donors, and any OAS design.
- A multi-job recipe's record format beyond what a list of tools gives (§5.3).

**Anti-goals: what would make this a failure even if it worked.**
- This repository running, scheduling, or ordering a recipe's work, in any form.
- A toolshed image shaped around one recipe.
- A human required to approve a merge or a promotion.
- `datasets` coupled to flyloft: flyloft is one cook among many; nothing here names it or requires it.

## 4. `jaffe-paired`

**Source.** figshare article 19617633, version 3, DOI `10.6084/m9.figshare.19617633.v3`, license MIT, published 2022-04-21:
- `test_data.tar.gz` (file 34846953, 11,941,014,666 bytes, MD5 `4d87c4da2d407ba95180be2cb1c91044`): Cell Ranger `multi` output per sample. Of it the recipe uses only `test_data/<sample>/outs/per_sample_outs/<sample>/vdj_b/filtered_contig.fasta`, which holds exactly the contigs of the sample's `filtered_contig_annotations.csv`: Cell Ranger's cell-associated contigs, every one productive, high-confidence, and full-length by Cell Ranger (checked for sample 1279049: 20,534 contigs in each, the same set). The tarball also holds `filtered_contig_annotations.csv` (Cell Ranger's own annotations, already filtered to productive, high-confidence, full-length contigs) and gene-expression output; neither is used.
- `test_data.csv` (file 34846938, 1,981 bytes, MD5 `3ccae335a8a03b5a771dc0eae97f7af6`): the 94 samples, columns `dataset` (the sample name, e.g. `1279049`), `donor` (1–4), `flow_class` (`naive`, `unswitched`, `switched`, `plasmablast`, `unswitched + naive`, `switched + naive`).

The recipe's committed inputs name both files by figshare file id, size, and MD5, and the recipe refuses a download whose MD5 differs **(call)**; the skill states the article version, the DOI, and the date pulled.

**The recipe**, in order (one job, in `datascience`):

1. Download both files. From the tarball keep only each sample's `filtered_contig.fasta` (stream it through `tar` with a member pattern; the rest is gene expression).
2. Annotate every contig with abstar 0.9.0 against the human germline database, output parquet.
3. Pair within each sample. A contig's droplet barcode is its `sequence_id` up to the first underscore (`AAACCTGAGACACGAC-1_contig_1` → `AAACCTGAGACACGAC-1`, 16 nucleotides and `-1`). The pair id is `<barcode>_<sample>` (`AAACCTGAGACACGAC-1_1279049`); barcodes are unique only within a sample.
4. Count each droplet's chains over the contigs in its `filtered_contig.fasta`. Keep a droplet only when it has exactly one heavy chain and exactly one light chain (kappa or lambda), and abstar calls both `productive` **(call: abstar's verdict as well as Cell Ranger's)**. Drop every other droplet. In sample 1279049, 91% of 9,808 barcodes are one heavy and one light; 389 are one heavy and two lights, 299 two and two, 49 two heavies and one light, 118 a single chain. The recipe prints how many droplets it dropped, by shape and for abstar's verdict separately, and the record carries that output.
5. Cluster the pairs with mmseqs2 at 85% identity and 80% coverage, on the heavy chain's `sequence_vdj_aa` joined to the light chain's. mmseqs2's coverage mode and the clustering command are the builder's (§7).
6. Split by cluster, 96 / 2 / 2 into train, eval, and test: shuffle the clusters with the seed in the parameters and assign whole clusters, so no 85% cluster spans two splits. Eval and test hold the 85% cluster representatives.
7. Re-cluster every train pair (not only the representatives) at 95% identity and 80% coverage, on the same joined sequence. Train holds the 95% cluster representatives.
8. Write `train.parquet`, `eval.parquet`, `test.parquet`.

**The parameters** (`recipe/params.toml`): `pulled` (the date the files were downloaded), `article = 19617633`, `article_version = 3`, `germline_database = "human"`, `identity = 0.85`, `coverage = 0.8`, `train_identity = 0.95`, `split = [0.96, 0.02, 0.02]`, `seed = 1` **(call: the names)**.

**The files.** One row per pair, in each of the three:
- every field abstar 0.9.0 writes, once per chain, the heavy chain's with `:0` appended to the field name (`v_call:0`, `sequence_vdj_aa:0`), the light chain's with `:1`;
- `pair_id`, `sample`, `donor`, `flow_class` (from `test_data.csv`) **(call)**;
- `cluster_85`: the `pair_id` of the pair's 85% cluster representative; in train also `cluster_95`, the `pair_id` of its 95% representative **(call: the names)**.

Expected size: about 1.5M pairs before the 85% and 95% reduction (the PI's figure; sample 1279049 alone holds about 9,000).

**The test** (`recipe/test <out>`, reading footers and samples):
- the three files exist and parse, with the columns above;
- each split's rows clear a floor the recipe states after the first build;
- no `pair_id` in two splits; no `cluster_85` in two splits;
- every `productive:0` and `productive:1` is true;
- every `sequence_vdj_aa:0` and `sequence_vdj_aa:1` holds no gap character (`-`, `.`) and no stop (`*`), and ends with that chain's `fwr4_aa`, so a later abstar whose field means something else fails here rather than clustering on it;
- every heavy chain's `locus:0` is `IGH` and every light chain's `locus:1` is `IGK` or `IGL`.

**The skill** (`datasets/jaffe-paired/SKILL.md`): name `jaffe-paired`; a description that says what it is and when to reach for it (paired human antibodies from four donors' sorted B cells, clustered, for training or evaluating a paired-chain model); `metadata.version: 1.0.0`, `metadata.tools: datascience@1.0.0`, `metadata.license: mit` (the source's); then the sections of DESIGN §2: the files and their columns, the one line that reads it, the recipe (source, version, pull date, every parameter, abstar's version and why it matters), what the build took, and gotchas (barcodes are unique only within a sample; the droplet rule drops about 9%; `donor` makes a held-out-donor variant possible as another dataset).

**Compute.** CPU only. About 3M chains through abstar, then two mmseqs2 runs; the PI expects an hour or two in all. Built on coreweave-rtx6000's `hpc-low` partition, which takes CPU-only jobs on GPU nodes' spare CPUs (flyloft's `spare-cpus.md`; bcr is down for a day or so); the skill's compute section is filled in from the real build.

## 5. Changes in this repository

### 5.1 Scripts

- **`scripts/build`, `scripts/test`: deleted**, with their tests and the podman stub.
- **`scripts/push <name> <output dir>`**:
  - refuses when `datasets/<name>/` has uncommitted or ignored changes (`git status --porcelain --ignored`), and refuses when `git status` itself fails (no git, no repository), naming why;
  - names the candidate `candidate-<tree>`, `<tree>` the committed recipe's hash, as now;
  - uploads the output directory as given, leaving out every path with a component starting with `.` (a recipe's `.work/`), as now;
  - writes the card from the skill, prints the manifest and `commit:`, and never prints the token, as now;
  - the `.built` marker and its tool check are gone with `build`.
- **`scripts/record`, `scripts/check.py`, `scripts/promote`, `scripts/changed-datasets`**: unchanged in purpose; they take `metadata.tools` (§5.2).
- **A recipe's files**: `check.py` still requires `recipe/build`, `recipe/params.toml`, and `recipe/test` **(call)**. `recipe/build` is a single-job recipe's program, or a split recipe's first; a split recipe's other programs sit beside it in `recipe/`, and its skill says their order. The rule is revisited with the first split recipe.

### 5.2 The frontmatter

`metadata.tool` becomes **`metadata.tools`** **(call: the name)**: one or more `name@version`, separated by single spaces, as a string. The Agent Skills format defines `metadata` as a map from string keys to string values (agentskills.io/specification), so a YAML list would break the format the harnesses read; the spec's own `allowed-tools` is space-separated the same way. A recipe of one tool names one.

`check.py` parses it by splitting on spaces, checks each entry against `name@MAJOR.MINOR.PATCH`, and checks each against the shed's catalogue. The record's header `tool:` becomes `tools:`, the same string; `check` compares it to the skill's.

### 5.3 The record of a split recipe

A split recipe's record is one record: `tools` lists every tool its steps used, and the body holds each step's output in order, which the cook pastes and `record` stamps. `runner`, `host`, and `started` describe the step that ran the test **(call)**. Per-step structure in the header waits for the first split recipe that needs it.

### 5.4 The workflow

Unchanged: `check` on every pull request, `promote` on a push to `main`.

### 5.5 The guidance

- **`CONTRIBUTING.md`** (plan A's Task 6 writes it), in the toolshed's voice:
  - the layout and the rules;
  - that a recipe is instructions and the cook runs it, anywhere;
  - choosing a recipe's shape: one job by default; split for a long step worth resuming or for steps of different compute; chaining datasets as the other way to split; the prose a split recipe states (order, tool and compute of each step);
  - cooking a recipe: in a tool's image under `srun` with pyxis, or with `podman` on a laptop, written out as commands, not as scripts here;
  - filing a result: run the recipe's test, `scripts/push`, `scripts/record` with the test's and push's output, commit the record, open the pull request;
  - what the record must show, and the review questions: does the skill describe the files the record lists and state the recipe's inputs; does the record show the test passed where the build ran; is the version new; are the tools the ones the record shows;
  - review by someone other than the builder, a critic agent included.
- **`README.md`**: drops "CI never builds" phrasing that implies this repository builds anything; otherwise as now.
- **`AGENTS.md`**: the layout and rules updated to §5.1–5.2.

### 5.6 `hello`

Plan A's synthetic `hello` stays as the cheap end-to-end exercise of filing, checking, and promoting, now naming `datascience@1.0.0`; it must pass before `jaffe-paired` is built.

## 6. The `datascience` tool, in the toolshed

A toolshed contribution through the shed's own flow (its CONTRIBUTING, build, test, record, review). The toolshed's design gains a short section on general-purpose images: what they are for, that they are built **without** `HF_HUB_OFFLINE` because a recipe reaches the network (the shed's other images set it), and that their versions move when any package does, on a cadence rather than per package release. The skill's *Gotchas* says that pyxis passes the caller's environment into the container, so a caller's `HF_HUB_OFFLINE=1` would stop a recipe's downloads and `scripts/push` **(call)**.

Built on the PI's laptop with the shed's `scripts/build` and `scripts/push` (a cluster never builds), and tested with the shed's `scripts/test datascience srun --partition=hpc-low ...` from a coreweave-rtx6000 login node, where it will be used. The shed's scripts need no change for a CPU tool: `scripts/test` already prints `gpu: none` without a GPU, and nothing in `check.py` requires `HF_HUB_OFFLINE`.

Contents, pinned at build time, for `datascience@1.0.0`:
- the base `python:3.12-slim-bookworm` by digest (abstar 0.9.0 needs Python 3.10 or later);
- abstar 0.9.0 and the abutils it requires (0.6.1); abstar's germline databases ship inside its package;
- numpy, polars, pandas, pyarrow, duckdb, scipy, scikit-learn, biopython, `huggingface_hub`, `datasets` (the Hub's library), and for plots matplotlib and seaborn (the PI: "matplotlib, seaborn, etc."; stopping at those two is a **(call)**);
- mmseqs2 as abutils ships it (`abutils/binaries/mmseqs_linux_amd64`, MMseqs2 commit `7e28409`), linked to `/usr/local/bin/mmseqs` so a recipe and abstar run the same binary; no second download **(call)**;
- DIAMOND, from its release binary, pinned at build time;
- git, from apt, so `scripts/push`'s guard works inside the image;
- `COPY test /toolshed/test` last; `test/run.sh` annotates a paired fixture with abstar, sized past abstar's first size threshold (its multi-process path, found in its code) as the shed's CONTRIBUTING asks, and checks `sequence_vdj_aa`, clusters it with `mmseqs`, runs `diamond version`, and imports the Python packages.

The lab's cluster image `deeplearning_v2026-09-15.sqsh` (inventoried in flyloft's `docs/environments/`) holds abstar 0.8.0, polars 1.44.2, pyarrow 25.0.1, `huggingface_hub` 1.31.0; it is a reference for versions, not a base.

## 7. Left to the builder

- The base image and its digest; package versions current at build time; how abstar's germline databases get into the image.
- mmseqs2's command (`easy-cluster` or `easy-linclust`) and coverage mode; how the joined heavy-light sequence is written for it; how cluster tables are read back.
- How the recipe streams `filtered_contig.fasta` out of the 11.9 GB tarball, and whether it keeps the tarball between runs.
- The recipe's floor per split, set after the first build and stated in the skill.
- The exact order of tasks in the revised plan, and how plan A's Tasks 5–8 are rewritten.

## 8. Consequences outside this repository

- **VISION** ("CI checks records and never pulls a dataset" stands) and **DESIGN** (§2's `recipe/build` as "one program", §3's `scripts/build`/`scripts/test` and the `.built` skip, §4's recipe image, the frontmatter's `metadata.tool`, §6's deferred multi-job recipe): edited to this document once the lab approves it.
- **The toolshed**: `datascience` and the design section in §6.
- **flyloft's `docs/design/datasets.md`**: a dataset build is no longer `scripts/build && scripts/test && scripts/push` in one run; flyloft cooks the recipe as its skill says, then calls `push` and `record`; it reads `metadata.tools`. flyloft's own design and plans change accordingly; nothing here waits on them.
