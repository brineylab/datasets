# `oplm-antibody-cdrh3`: Design

Status: draft 2026-11-12, from a design conversation with the lab's PI. Tracked on briney/oplm#78, the anneal-mix experiment. It builds on `oplm-antibody-sequences` v1.0.0 (design `2026-11-09-oplm-antibody-sequences-design.md` on that dataset's branch; skill `datasets/oplm-antibody-sequences/SKILL.md`). Calls made in writing that nobody discussed are marked **(call)**.

## 1. Why

oplm#78 tested a decay (anneal) mix with antibodies on OPLM's 1/35 overfit proxy (170M model, 140k→175k from the stable checkpoint). It used AntiRef96 clusters with AntiRef99 members at 1.5%, 3% and 6% of tokens. Results: briney/oplm#78 issuecomment-6812930334. The PI chose **1.5% for production**. Two findings set up this follow-up.

- **The current eval sets reward recall.** v1 holds out whole AntiRef90 clusters, nothing more. Of eval_gte2's CDR3s, an exact copy is in the training shards for 27% of heavy chains and about 85% of light chains.
- **Extra antibody data buys memorization faster than generalization.** Going from 1.5% to 6%:
  - loss on unseen heavy CDR3s fell only 1.50 → 1.41;
  - loss on seen ones fell 1.31 → 0.79;
  - the seen-vs-unseen gap widened 0.19 → 0.62.

  The proxy repeats its 6M antibody chains 3–12 times, and production would too.

So the question now is which antibody **train set** generalizes best at the fixed 1.5% share. Coarser clusters (AntiRef90, 92, 94 representatives) with member sampling from AntiRef99 spread draws across more distinct families and repeat exact sequences less. Answering this needs an eval where "unseen" means something: a **heavy-chain CDR3-identity holdout**.

## 2. Decisions (the PI's)

**Revised 2026-11-12, after measuring the screen.** Scored against about 7,900 real heavy CDR3s, a 24,000-sequence train sample showed the screen at 80% would remove about 10% of train at 10,000 held out, against a 3% tripwire. Removal scales mostly with the number held out, not with CDR3 length. The PI chose **85% CDR3 identity at any length** (same-length-only matching saved little once at 85%) and **2,500 + 2,500** held-out heavy chains, with the tripwire at **5%** (about 4.3% expected). Conserved Cys104 and Trp118 were already outside the compared CDR3 (IMGT 105–117). Below, every threshold, size and bound reflects this revision.

**Revised 2026-11-13, after the first full build.** The screen removed 5.134% of AntiRef99 train sequences (16,222,603 of 315,971,320), over the 5% tripwire. Removal is concentrated in common CDR3s: 1,472 held-out CDR3s each remove more than 1,000 sequences, the largest 358,021. The PI kept the held-out sets as drawn and raised the tripwire to **6%**.

- **Holdout: CDR3 identity, from AntiRef, first.** A donor holdout needs an OAS rebuild with donor annotations, and waits.
- **Heavy chains only, at 85% CDR3 identity.** No heavy-chain CDR3 left in training is 85% or more identical to a held-out heavy chain's CDR3. Light chains stay on v1's AntiRef90-cluster holdout. Their CDR3s are low-diversity: holding them out by CDR3 identity would gut light-chain training or leave almost nothing unseen.
- **Train sets to compare, all at 1.5% of decay tokens on the 1/35 proxy:**
  - AntiRef90 representatives with AntiRef99 members;
  - AntiRef92 → 99;
  - AntiRef94 → 99;
  - AntiRef96 → 99, rebuilt under the new holdout as the baseline.
- **How a winner is chosen:**
  - lower CDR3 loss on unseen CDR3s;
  - lower heavy CDR3 loss on the new CDR3-identity holdout.
- **The paired-chain axis of #78 is dropped.**
- **One dataset, four clustering levels: v1's exception to `docs/DESIGN.md` D3, extended (PI, 2026-11-12).** All four train sets have to share one holdout and one screen, and one recipe guarantees that. The skill states the exception, as v1's does.

## 3. Goals, non-goals, anti-goals

**Goals.**
- A new held-out heavy-chain set whose CDR3s have no 85%-identical CDR3 anywhere in training. OPLM's existing `antibody_cdr3` eval reads it unchanged.
- Four train sets sharing one holdout, so the four decays differ only in the train set.
- v1's eval and test files carry over byte-identical, so earlier #78 numbers stay comparable.

**Non-goals.**
- A donor holdout, newer OAS data, paired chains, or an SHM mask: these need the OAS rebuild.
- A CDR3 holdout for light chains.
- A leakage screen against uniref70 or deepclust70, as in v1.
- An AntiRef99-representatives train set: the sweep doesn't use one **(call)**.

**Anti-goals.**
- A screen that is only as good as a regex. A held-out CDR3's near-duplicate must not slip into train because a CDR3 boundary was misplaced (§5.3).
- Changing OPLM's code for this. The CDR3 eval, the loader and `sample_members` already handle everything here.

## 4. Source and identity

Same source as v1: AntiRef v2022.12.14, the Zenodo manifest and FASTA, with the same MD5s and the same nested linclust levels (100, 99, 98, 96, 94, 92, 90).

~~This is a **new dataset**, not a v1 version. Name: `oplm-antibody-cdrh3`.~~ **Revised 2026-11-13 (PI):** this is **`oplm-antibody-sequences` 2.0.0**, a new version of the same dataset: the same data with a different eval and test holdout. Against D3 by the PI's decision; the skill says so. 2.0.0 drops 1.0.0's `antiref99/train` (PI). Train results are not comparable across the two versions.

## 5. Steps

### 5.1 v1's holdout, unchanged

Run v1's hold-out step with v1's parameters (`seed = 1`, `heldout = 5000`). The 20,000 held-out AntiRef90 clusters and their four files come out identical to v1.0.0. The test checks that by hash against v1.0.0's files.

### 5.2 The heavy CDR3 holdout

- **Candidates.** The representatives of the remaining AntiRef90 clusters, walked in a seeded order (`md5('<seed>:<antiref90>')`, as v1) with a new seed, `cdrh3_seed = 2` **(call)**. Number each with ANARCII (IMGT), as v1 does.
- **Keep a candidate when:**
  - its chain is H;
  - every residue is numbered;
  - its CDR3 (IMGT 105–117) has at least 5 residues **(call)**;
  - its CDR3 is less than 85% identical to every CDR3 already kept. Without this, one family could dominate the eval **(call)**.
- **Split.** The first 2,500 kept are `eval_cdrh3.parquet`, the next 2,500 `test_cdrh3.parquet`. Columns are v1's: `sequence_id`, `sequence`, `locus` (all `IGH`), `cdr_mask_aa`.
- **Identity.** Two CDR3s `a` and `b` are 85% identical when `1 − levenshtein(a, b) / max(len(a), len(b)) ≥ 0.85`, that is, when the edit distance is at most `floor(0.15 × max length)`. Length differences count against identity **(call)**.

### 5.3 The train screen

Remove from train:
- every sequence in a held-out AntiRef90 cluster (5.1 and 5.2), as v1 does;
- every sequence whose CDR3 region holds a near match to a held-out heavy CDR3.

**What "near match" means here.** The match is CDR3 against CDR3: the PI's 85% is CDR3 identity, not containment. The guarantee must still not depend on locating each train sequence's CDR3 exactly. ANARCII on about 300M sequences is too slow for CPU, and a regex (`C(...)[WF]G.G`) agreed with ANARCII's CDR3 on only 93% of eval chains. So the screen tries every plausible boundary pair.

- **Window.** For each train sequence, the window is its C-terminal half, `sequence[len(sequence) // 2:]`. CDR3 starts near residue 105 of about 120, so the half always holds it, and the screen never needs to locate Cys104. Planning chose this over a window that starts 10 residues before Cys104: it is a superset of that window, so it can only remove more **(call)**.
- **Anchored candidates (call).** A candidate CDR3 is any substring of the window that starts right after a `C` and ends right before a `[WF]G.G` motif, 3 to 40 residues long.
  - Each candidate is compared end to end with each held-out CDR3 by §5.2's identity.
  - A train sequence goes when any of its candidates is 85% or more identical to any held-out CDR3.
  - This tries every boundary pair, so a misplaced boundary can't hide a match. It also can't match a held-out CDR3 against a fragment of a longer train CDR3, which keeps shared germline D or J stretches (`…YYYYYGMDV`) from removing unrelated antibodies.
- **Unanchored sequences.** A sequence with no anchored candidate (about 6% of v1 train sequences by the regex) gets the conservative fallback. It goes when any window substring meets the identity bound. The check runs as a semi-global edit distance of at most `floor(3 × len(query) / 17)`. That is a superset of the 85% bound for any substring length, since the bound allows at most `floor(0.15 × max length)` edits and a substring more than 20/17 of the query's length is out of reach **(call)**.
- **Light chains.** The screen covers every train sequence, light chains included. A light chain rarely matches a heavy CDR3, and skipping chain typing keeps the screen simple **(call)**.
- **Speed.** How to run 5,000 queries against about 300M sequences fast is the builder's call. For example, by pigeonhole: a match within edit distance `k` shares an exact `⌊L/(k+1)⌋`-mer with the query, so an exact k-mer index narrows the candidates before alignment.

**The build prints:**
- how many sequences the screen removed;
- how many held-out CDR3s removed more than 1,000 sequences, and the largest removal.

A public heavy CDR3 drawn into the holdout takes its whole family out of train. That is the point, and the count makes it visible.

- **No per-CDR3 cap.** A cap would bias the eval away from public CDR3s **(call)**.
- **Tripwire.** If the screen removes more than 6% of AntiRef99 train sequences, the build stops so a person can look before anything publishes **(call)**.

### 5.4 Train sets

From what remains, write four folders in v1's antiref96 format:
- `antiref90/train/`, `antiref92/train/`, `antiref94/train/`, `antiref96/train/`;
- each row is a cluster at that level: the representative's `sequence_id` and `sequence`, then `member_ids` and `member_sequences` listing the distinct AntiRef99 representatives inside it, the representative first;
- the same seeded shuffle, 1,000,000-row shards, row groups of 10,000, and zstd as v1.

Every folder holds the same set of AntiRef99 sequences, grouped differently. So the four train sets differ only in how training draws from them: a uniform cluster, then a uniform member.

The nested clustering makes each representative its own AntiRef99 member, as v1 checks for AntiRef96. If linclust's nesting breaks that at a coarser level, the build stops.

**The screen will remove some representatives while members of their clusters survive.** CDR3 identity doesn't follow linclust's full-length clusters. Equal member sets across the four folders matter more than AntiRef's choice of representative, so:
- the surviving member first in the seeded order (`md5('<seed>:<antiref99>')`) becomes the row's representative: its `sequence_id`, its `sequence`, and the first entry of the member lists;
- a cluster with no surviving member is dropped;
- the skill says that in this dataset, a row's `sequence` is AntiRef's representative unless the screen removed it;
- OPLM always reads these folders with `sample_members: true` **(call)**.

### 5.5 Print

v1's `rows` and `locus` lines, plus:
- the screen's counts from 5.3;
- each train folder's rows and mean members per row.

## 6. The test

v1's checks, plus:

- v1's four eval and test files are byte-identical (sha256) to v1.0.0's;
- `eval_cdrh3` and `test_cdrh3` each have 2,500 rows, all `IGH`, and every CDR3 at least 5 residues;
- no `sequence_id` appears in two held-out files, or in a held-out file and a sampled train row's members;
- **the screen holds.** For a sample of train rows (several thousand members per folder), no window is within the 85% bound of any held-out heavy CDR3. The test reruns the semi-global check on that sample; the build's own index is not trusted;
- all four folders' member sets have the same total count;
- each sampled row's first member is itself;
- the screen removed no more than 6% of AntiRef99 train sequences.

## 7. Compute

Build on bcr, as v1 (Zenodo is slow to CoreWeave). v1's download in `.work/` can be reused if it's still there.

My guesses, to be measured:
- v1's 37 minutes;
- the screen, a few CPU-hours with a k-mer index;
- four train folders, about 25 GB each, about 100 GB of output.

## 8. How OPLM uses it (briney/oplm#78)

This is in scope. The plan builds the dataset first (a PR here, cooked on bcr), then runs the sweep and reports on #78 **(call)**.

**The runs.**
- Four decay branches with `overfit.sh` (`AB=1.5`), one per train folder, from the 140k stable checkpoint to 175k, 4 nodes each.
- **The 1/35 subsample** for each folder is the run of whole shards, in shard order, whose total member count comes closest to 1/35 of that folder's members. Repetition depends on distinct AntiRef99 sequences, not cluster rows, so this keeps the four runs' pass counts about equal; the realized fraction is reported **(call)**.
- Same recipe as `decay140k-u25-ab1.5`: uniref70 at 25% of tokens, antibody tokens taken from deepclust70.
- Row fractions come from each folder's mean member length, as `overfit.sh` computes now.
- `admin_override` for these runs is to be confirmed with the PI at launch.

**The evals**, every 1,000 steps:
- `antibody_cdr3` on v1's `eval_gte2` and `eval_singletons`;
- `antibody_cdr3` on `eval_cdrh3`, with metrics limited to `{loss,accuracy,perplexity}_heavy`. Its light metrics would be empty.

**Scored standalone on `eval_cdrh3`:**
- the protein-only control, `decay140k-u25` at 175k;
- the old `decay140k-u25-ab1.5`, whose training never excluded these CDR3s' neighbours. Comparing it with the rebuilt AntiRef96 run shows how much the old numbers were inflated by leakage **(call)**.

**Report on #78**, at 175k, for the four runs and the control:
- heavy CDR3 loss on `eval_cdrh3`, the primary metric;
- v1-file CDR3 loss, split into seen and unseen CDR3s with `cdr3match.py`. Run it per train folder, since each holds a different 1/35 subsample;
- protein CE on deepclust70 and uniref70, eval and train probes;
- P@L on cameo, casp, pdb40 and pdb40_2048.

**The decision rule:**
- Prefer the train set with the lowest `eval_cdrh3` heavy loss, provided its unseen-CDR3 loss on v1's files is no worse.
- Protein CE must stay within the ±0.002 spread seen between protein-only schedule variants. If it doesn't, flag it rather than pick that set.
