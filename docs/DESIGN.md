# The datasets repository: Design

Status: approved 2026-11-04; revised 2026-11-05 by [superpowers/specs/2026-11-05-recipes-tools-and-jaffe-paired-design.md](superpowers/specs/2026-11-05-recipes-tools-and-jaffe-paired-design.md), so that a recipe is instructions any cook runs, names its tools, and runs in the toolshed's `datascience` (§2, §3, §4, §5, §6); revised 2026-11-06 so that whoever merges promotes with their own Hub token, and CI holds none, since a Hub token is a person's, not an org's (§3, §5). This is the repository's own copy of the design that lives in flyloft as [`docs/design/datasets.md`](https://github.com/brineylab/flyloft/blob/main/docs/design/datasets.md), with the lab's decisions on flyloft issue [#174](https://github.com/brineylab/flyloft/issues/174) (D1–D7, all option A) marked by number. §1 to §4 are this repository's; §5 summarizes flyloft's side, which that document settles. Calls made in writing that nobody has discussed are marked **(call)**. The toolshed's design ([brineylab/toolshed, docs/DESIGN.md](https://github.com/brineylab/toolshed/blob/main/docs/DESIGN.md)) is the sibling this one mirrors; where this document says "as the toolshed's", that is the reference.

## 1. Scenario

The researcher's task needs two paired antibody sets: human, which the lab has (`oas-paired-human@v1.2.0`), and mouse, which it lacks.

**Standalone, from a laptop or a notebook.** The researcher's agent reads the skill `datasets/oas-paired-human/SKILL.md` and runs its one line, `snapshot_download("brineylab/oas-paired-human", repo_type="dataset", revision="v1.2.0")`, which returns a path; the parquet files are read from it. For the mouse set the agent copies `datasets/oas-paired-human/` to `datasets/oas-paired-mouse/`, changes the species in the recipe's parameters and the skill's prose, cooks it where it will be built (under `srun` in the recipe's tool image on a cluster, or with podman on a laptop for a small one), runs the recipe's test on the output, pushes the files to the Hub on a candidate branch, commits the record, and opens the pull request. A member other than the builder reviews it and merges; CI tags the version on the Hub.

**In a flyloft campaign**, the same, with the campaign's implementer reading the catalogue in its assignment, pulling through the cluster's shared cache, building as one CPU run of the campaign, and the campaign's critic reviewing the pull request before flyloft merges it (§5).

**The lab has grown.** The mouse set is there for every later campaign, every notebook, and anyone with the Hub library.

## 2. A dataset

A dataset is **a Hub dataset repository whose files a recipe wrote, and whose versions are tags** (D1). The files are what training and evaluation read directly, parquet where the data is tabular, sharded when a file would be large; the Hub serves them, checksums them, and caches them on whoever pulls. Nothing about a dataset is flyloft-specific: the same `snapshot_download` line works in a notebook, on a laptop, and in a job.

- **Variants are datasets, versions are time (D3).** `oas-paired-human` and `oas-paired-mouse` are two datasets, each a copy of the other's recipe with the species changed, as `esm2-650m` and `esmc-600m` are two tools. A different clustering threshold is a new dataset too, because models trained at 90 and at 95 are not comparable and should not share a name. A version changes when the source is re-pulled, a parameter moves, or a tool moves. The name says what you trained on; the version says when.
- **A recipe is instructions that write a version (D4, revised).** `recipe/build <out>` reads its parameters from `recipe/params.toml` beside it and writes the version's files into `<out>`. It runs inside toolshed tools' images, named in the skill, so its tools are pinned and the same images serve a laptop, a Slurm job, and a campaign. Its shape is its author's call. One job is the default. A split recipe, for a very long step whose resumption matters or for steps with different compute (CPU annotation, then GPU embedding), is several programs and prose stating their order, each one's tool, and each one's compute; `recipe/build` is a single-job recipe's program or a split recipe's first. Chaining datasets, one built from another's published version, is the other way to split. Whoever cooks the recipe runs it; this repository runs, schedules, and orders nothing.
- **The identity is the recipe's inputs**: the source and its pull date, the parameters, the tools' versions. The record of a version (§3) carries them, and the skill states them in prose.

**The skill** is the dataset's whole description, prose in the Agent Skills format Claude Code, Codex, and OpenCode read:

```markdown
---
name: oas-paired-human
description: "Paired human antibody sequences from OAS: clustered at 90% identity, split by cluster, annotated with abstar. Reach for it to train or evaluate a paired-chain model."
metadata:
  version: 1.2.0
  tools: datascience@1.0.0
  license: cc-by-4.0
---
# oas-paired-human
Hub: `brineylab/oas-paired-human`, tag `v1.2.0`
## Files
`train.parquet`, `eval.parquet`, `test.parquet`: one row per pair, columns ...
## Reading it
Anywhere: `path = snapshot_download("brineylab/oas-paired-human", repo_type="dataset", revision="v1.2.0")`, then read the parquet files under `path`.
In a flyloft campaign: the same line; the pull lands in the cluster's shared cache.
## Recipe
Source, pull date, species, threshold, split rule, abstar version; what the test checks.
## Compute
What the build takes: CPUs, memory, hours, disk.
## Gotchas
```

The frontmatter has five fields a machine reads: `name` (the directory's name and the Hub repository's), `description` (the catalogue line), `metadata.version` (the Hub tag, `v` prefixed), `metadata.tools` (the toolshed tools the recipe runs in, one or more `name@version` separated by single spaces, as a string: the format's `metadata` maps strings to strings), and `metadata.license` (the card's). Everything else is prose for the agent. The Hub's card is generated from it (§3).

## 3. The repository

`datasets`, public, one directory per dataset (D2):

```
README.md                      what it is; finding and reading a dataset from anywhere; installing the skills
CONTRIBUTING.md                adding a dataset: the layout, the conventions, building, the test and its record, versions, the review
hub.toml                       the Hub org the repository publishes to (`brineylab`; a scratch repository names a scratch org)
datasets/<name>/SKILL.md       the skill (§2)
datasets/<name>/recipe/build   the program: reads params.toml, writes the version's files into its argument
datasets/<name>/recipe/params.toml
datasets/<name>/recipe/test    checks an output directory: the files, their schema, row counts, the recipe's own checks; exits 0 iff it holds a version
results/<name>/<version>.txt   the record of the candidate's test: the Hub commit, where it ran, the files with their sha256, the output, the exit code
scripts/check.py               a dataset directory's rules, its record, and whether its version is published
scripts/push <name> <output dir>   upload the cook's output and the card to the Hub on the candidate branch; prints the manifest and the commit
scripts/record                 a record from the test's and the push's output, for any cook
scripts/promote                run by whoever merges: tag the merged record's commit as the version on the Hub; delete the candidate branch
.github/workflows/datasets.yml check
```

**Versions.** `metadata.version` is the Hub tag, `v<version>` on `<org>/<name>`, with the org from `hub.toml`, so a fork with its own org is its own catalogue and store with one edit. A published tag is never moved: any change under `datasets/<name>/` bumps the version, prose included, and CI refuses a pull request whose tag is already on the Hub. Agents and flyloft always name a version, never `main`.

**The Hub** is the store (D1). One dataset repository per dataset, public, created by the first push when it does not exist. The Hub gives what the toolshed's registry gives and more: every commit immutable, a tag per version, every file's sha256, hosting, a dataset viewer, and a download-and-cache library every agent already knows. A dataset built from public data is public from the start, which is also where reviewers look when the lab publishes. A dataset the lab could not make public is the exception, handled when it arrives (a private repository and a read token), not designed for now. A few hundred GB per dataset, the largest foreseen, is within the Hub's guidance (no per-repository cap for public repositories; files under 200 GB, parquet preferred, under 100k files). Free organizations get best-effort public storage beyond the first gigabytes, so before plan A's large dataset the lab confirms its Hub plan holds what it will publish.

**The candidate** is the Hub commit a pull request proposes to publish: the head of the branch `candidate-<tree>` on the dataset's Hub repository, `<tree>` being git's hash of the committed `datasets/<name>/recipe/` directory, so the branch names the inputs it was built from. The scripts compute it from the files, not from `.git`, so `record` and `check` need no checkout **(call)**; `push` needs one, to prove the files are the commit's. The skill is not in the tree: a prose change does not change the bytes. **Building is the cook's.** Whoever cooks a recipe runs it, and its test, where the dataset will be built, into an output directory of their choosing. `scripts/push <name> <output dir>` refuses when `datasets/<name>/` has uncommitted or ignored changes, or when git cannot say, so the candidate is named by the committed recipe's tree; it uploads the directory to the candidate branch, writes the card as a commit on it, and prints the file manifest with sizes and sha256 and then the head commit on a tagged `commit:` line, so `scripts/record` reads everything it needs from that output and nothing on the flyloft host needs the Hub library **(call)**; the Hub skips every file it already holds, so a second push of the same output moves prose only. Then `scripts/record` writes **the record**, `results/<name>/<version>.txt`: the Hub repository, the branch and its head commit, the recipe tree, the parameters, the tools, where it ran, the time, the files with their sizes and sha256, the test's output, and the exit code. The record lives outside `datasets/<name>/`, so committing it leaves the candidate alone. A person cooks under `srun` in the recipe's tool image on a cluster, or with `podman` on a laptop for a small one, as `CONTRIBUTING.md` writes out; flyloft cooks as its campaign decides (§5). CI never runs a recipe or pulls a dataset.

**The card.** The Hub asks every large dataset for a card and serves its viewer from parquet. `scripts/push` writes `README.md` on the candidate branch from the skill: a header with the license and the name, then the skill's body. One source, two readers.

**The workflow**, on GitHub's hosted runners only, never downloading a dataset and holding no Hub token:

- `check`, on every pull request, for the datasets it changes: the skill's frontmatter parses, its name is the directory's, each of its tools is in the toolshed's catalogue at that version (read from the shed's `main` by API); `recipe/build`, `recipe/params.toml`, and `recipe/test` exist; the version's tag is not on the Hub; the record exists for this version, names a commit on the Hub whose tree holds exactly the record's files with the record's sha256 (the Hub's file listing, no download), and shows exit code 0.

**Promoting** is the merger's, as pushing is the cook's: after the merge, whoever merged pulls `main` and runs `scripts/promote <name> <version>` with their own `HF_TOKEN`, which tags the record's commit `v<version>` on the Hub, never moving a tag that exists, and deletes the candidate branch; it refuses a record that is not on `origin/main`, so only a reviewed, merged record is published, and its last line says what it did. A Hub token is a person's, so CI holds none; this is the one place the repository differs from the toolshed, whose CI promotes with GitHub's own token.

**Guards.** Nothing a pull request contains runs on the lab's machines: CI runs the check script and its unit tests. Nothing that goes public holds a credential: `check.py` refuses a dataset directory or a record that holds the shape of one, in `scripts/push` before anything goes up, in `scripts/record` before anything is written, and in `check` as the backstop; `scripts/push` reads its token from `HF_TOKEN` and never prints it. The record's file list is the Hub's: what a version holds is what the record says, and `check` proves it. `main` requires `check` and no other approval: flyloft merges as the campaign's owner after its critic's review, and a person's pull request is merged by a member other than its builder.

**The test** is the recipe's own: `recipe/test <out>` reads the output directory and checks it is a version of this dataset: the files are there, each parses, the schema is the skill's, each split has at least as many rows as the recipe expects, and whatever else the recipe knows (a duplicate across splits, an unannotated row). It runs in seconds on hundreds of GB, because it reads footers and samples. It is not the recipe on a tiny slice: the build is the real thing and the test judges it. A recipe may take a `limit` in its parameters for a developer's dry run; the published version never does.

**From a notebook or a laptop.** The skill's `snapshot_download` line is the interface, and `load_dataset(..., revision=...)` works the same. On bcr, a notebook that points `HF_HUB_CACHE` at the cluster's shared cache (§5) finds what campaigns pulled, and the README has the line. To give an agent the repository's skills: clone it and symlink each `datasets/<name>` into the harness's skills directory. No `datasets` command until the prose proves insufficient.

## 4. General-purpose tools

A recipe runs in toolshed images named in its skill's `metadata.tools`, most often a general-purpose one: the shed's `datascience` holds the scientific Python stack, abstar and abutils, mmseqs2, DIAMOND, and `huggingface_hub`, and is built **without** `HF_HUB_OFFLINE` because a recipe downloads its source and pushes its result from inside it. No shed image is shaped around one recipe; `hello` and `jaffe-paired` both run in `datascience`.

## 5. flyloft's side, in summary

Settled in flyloft's [`docs/design/datasets.md`](https://github.com/brineylab/flyloft/blob/main/docs/design/datasets.md) §4 to §5; this repository needs none of it to work, and none of it changes what this repository is.

- **Reading (D6: jobs pull).** Every job script exports `HF_HUB_CACHE` under the cluster's shared data directory, and the Hub library does the rest: a cached version is returned at once, a missing one is downloaded, two jobs pulling at once cannot leave a half file. The cache is disposable. The implementer's assignment carries the catalogue rendered from this repository's skills.
- **Building.** A campaign's implementer gets a worktree of this repository, writes a dataset, and calls `submit_dataset`; flyloft cooks the recipe as its skill says (one job, or several), then calls `scripts/push` and writes the record with `scripts/record` from the test's and push's output, pushes the branch, opens the pull request, watches `check`, wakes its critic to review, merges, and runs `scripts/promote` with the token it holds for the campaign's owner, reading its last line. The same states as a tool build, with promoting done by flyloft rather than watched.
- **flyloft needs from this repository:** `scripts/record` and `scripts/check.py` runnable with the Python standard library alone on its host (its tier one carries copies of them), `scripts/push` printing the manifest and a `commit:` line, `scripts/promote` saying on its last line what it did, and the five frontmatter fields, `metadata.tools` among them.

## 6. Not here, and deferred

- A split recipe's record beyond one record listing every tool, each step's output in order: when the first split recipe needs per-step structure. Split recipes themselves are allowed (§2).
- A private dataset and its read token: none are foreseen.
- Freeing a cluster's cache: when a cluster fills.
- Data loaders, feature stores, streaming: project code.
- Retiring datasets nobody reads: by hand.
- A `datasets` command for laptops: when the skill's one line proves insufficient.
- The lab's Hub plan: confirmed by the lab before the first large dataset, not by code.

## 7. The decisions, for the record

From flyloft issue #174, decided 2026-11-04: D1 the Hub is the store; D2 recipes live here, in a GitHub repository mirroring the toolshed's split; D3 variants are datasets, versions are time; D4 a recipe is one program running in one tool's image (revised 2026-11-05 by the spec above: a recipe names its tools; one job is the default, not the rule); D5 publishing mirrors the toolshed's flow (contributor builds, CI never builds, merge promotes; revised 2026-11-06: the merger runs promote, since CI holds no Hub token); D6 jobs pull into the cluster's cache; D7 flyloft's part is the catalogue, reading, and `submit_dataset`. The two CoreWeave clusters have GPU partitions only; a no-GPU run there takes a GPU node's spare CPUs (flyloft's [`docs/design/spare-cpus.md`](https://github.com/brineylab/flyloft/blob/main/docs/design/spare-cpus.md)), which is where a dataset build on CoreWeave goes; the lab builds data on the rtx6000 cluster, not on b200.
