# The datasets repository: Vision

Status: approved by the lab on 2026-11-04 (flyloft issue [#174](https://github.com/brineylab/flyloft/issues/174), decisions D1–D7). Change only with the lab.

**What it is.** The lab's datasets, built once and read everywhere. Each dataset is a recipe in this repository (fetch, curate, split, annotate) and a versioned set of files on the Hugging Face Hub. A skill, in prose, says what the dataset is, what its files hold, and the one line that loads them, and both people and their agents read it. A campaign on a cluster, a notebook on JupyterHub, and an agent on a laptop all read the same version by name.

**Why.** Today each person rolls their own notebook: pull OAS, filter, cluster, split, annotate, at thresholds that differ from one notebook to the next. Two people who say "OAS paired" cannot tell whether they trained on the same bytes. The toolshed ([brineylab/toolshed](https://github.com/brineylab/toolshed)) fixed the same problem for models and pipelines: a public repository, one directory per tool, a skill that humans and agents both read, a build-and-review path, and flyloft as one user and one contributor among many. This repository is its data equivalent.

**Who uses it.** Anyone with the Hub library: a researcher in a notebook, a researcher's own coding agent, a Slurm job, and a flyloft campaign, which reads a dataset through the cluster's shared cache and builds one it lacks through this repository's pull request flow with its critic as the reviewer. flyloft is an important user, not the owner; nothing here is flyloft-specific.

**What a dataset is.** A Hub dataset repository whose files a recipe wrote, and whose versions are tags. Variants are datasets and versions are time: `oas-paired-human` and `oas-paired-mouse` are two datasets, and a different clustering threshold is a new dataset too, because models trained on them are not comparable and should not share a name. A version changes when the source is re-pulled, a parameter moves, or a tool moves. The name says what you trained on; the version says when.

**What it is not.**
- Not a store of bytes: the Hub holds every file; git holds recipes, skills, and records.
- Not a loader or a feature store: a dataset is files, and what reads them is project code.
- Not a place for one campaign's own split or subset: that stays in the campaign's directory. A dataset is for what the lab will use again.
- Not a runner: a recipe is instructions, and whoever cooks it runs it anywhere, as one job or several; this repository holds recipes and records and files results.
- Not built by CI: whoever asks for a dataset builds it where it will be built, tests the output, and commits the record. CI checks records and never pulls a dataset.

**Measures of success.** A researcher names a dataset and a version and reads its files from anywhere in one line. A dataset the lab lacks is built from a recipe, reviewed, and published for everyone. Two people who trained on the same name and version trained on the same bytes, and the record says what made them.
