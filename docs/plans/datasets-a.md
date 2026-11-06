# Datasets, Plan A: The Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> Tasks 5–7 are replaced by `datasets-a2.md`; Task 8 waits for flyloft's plan B. DESIGN's 2026-11-06 revision supersedes this plan's `promote` job and its `HF_TOKEN` repository secret: whoever merges runs `scripts/promote` with their own token, and CI holds none.

**Goal:** The lab's datasets repository exists as `brineylab/datasets`, with its check script, the contributor's build, test, push, record, and promote scripts, a workflow that checks a pull request's record against the Hub and promotes on merge, a recipe image in the toolshed, and two datasets published to the Hub under `brineylab`: `hello`, a synthetic one of kilobytes that exercises the whole path, and `oas-paired-human`, the real one.

**Architecture:** One directory per dataset holds a skill, a recipe (one program plus its parameters), and the recipe's test; the bytes live on the Hub as a tag per version. `scripts/check.py` and `scripts/record` are Python standard library only, because flyloft's host and the clusters' login nodes run them; `scripts/push` and `scripts/promote` use `huggingface_hub` and run inside the recipe's tool image or in CI. The candidate is a Hub branch named by the recipe tree's git hash; the record on the pull request names the candidate's commit and the files with their sha256, and `check` proves the Hub holds exactly those. Everything mirrors the toolshed ([brineylab/toolshed](https://github.com/brineylab/toolshed)); read its `scripts/` before writing the same thing here.

**Tech Stack:** Python 3.8+ standard library for `check.py`, `record`, and the tests (`unittest`, with the Hub, podman, and srun stubbed); bash with `set -euo pipefail` for the wrapper scripts; `huggingface_hub` (1.x) in `push` and `promote`; GitHub Actions on hosted runners; podman on a laptop, pyxis under `srun` on a cluster; the toolshed's conventions for the recipe image.

**Spec:** `docs/DESIGN.md` (this repository). The flyloft side, which this plan does not build, is flyloft's `docs/design/datasets.md`; what it needs from here is DESIGN §5.

## Global Constraints

- **Where the work happens:** this repository, on `main` for the skeleton (Tasks 1–4, commit by commit) and then a pull request per dataset (Tasks 6–7), because a dataset arrives as a pull request with its record. Task 5 is a pull request on the toolshed.
- **Names, exactly:** the directories and scripts of DESIGN §3; `hub.toml` with `org = "brineylab"` and `toolshed = "ghcr.io/brineylab/toolshed"`; the candidate branch `candidate-<tree>`; the tag `v<version>`; the record at `results/<name>/<version>.txt`; the workflow `.github/workflows/datasets.yml` with jobs `check` and `promote`; the Hub repository `<org>/<name>` of type dataset.
- **The recipe tree** `<tree>` is git's tree hash of `datasets/<name>/recipe/` computed from the files by `check.py --tree` (blob and tree objects hashed as git does, sorted entries, modes `100644` and `100755`), so that `git rev-parse HEAD:datasets/<name>/recipe` prints the same hash when the directory is committed. Pinned by a test.
- **The frontmatter** has exactly five machine-read fields: `name` (equal to the directory's), `description`, `metadata.version` (`MAJOR.MINOR.PATCH`), `metadata.tool` (`name@version`, a tool in the shed's `main` catalogue), `metadata.license` (a Hub license id such as `cc-by-4.0`). Parse it without a YAML library: the shed's `check.frontmatter` does, and this one does the same.
- **The record format**, written only by `scripts/record`, read by `check.py` and by flyloft:

  ```
  ---
  dataset: <name>
  version: <version>
  hub: <org>/<name>
  branch: candidate-<tree>
  commit: <40 hex>
  tree: <40 hex>
  tool: <name@version>
  runner: <srun|podman|flyloft>
  host: <hostname>
  started: <ISO 8601>
  exit: <0..255>
  ---
  <the build's output, verbatim: the test's lines and the push's `file <path> <size> <sha256>` lines and `commit: <40 hex>`>
  ```

- **`scripts/push` prints**, after the upload, one `file <relative path> <size in bytes> <sha256 hex>` line per data file (never the card) and last a line `commit: <40 hex>`, the candidate branch's head after the card commit. Nothing else on stdout after the `commit:` line.
- **Credentials:** `HF_TOKEN` is read from the environment by `push` and `promote` and never printed. `check.py --scan` refuses text holding the shape of one (`hf_[A-Za-z0-9]{30,}`, `ghp_[A-Za-z0-9]{30,}`, `gho_`, `AKIA[0-9A-Z]{16}`, `-----BEGIN`, `xox[bp]-`), and `build`, `record`, and `check` call it, as the shed's do.
- **Stdlib only** in `check.py`, `record`, `changed-datasets`, and `tests/`: the Hub is reached with `urllib.request`, and `huggingface_hub` is stubbed in tests by a module on `sys.path`.
- **CI never builds, tests, or pulls a dataset.** The `check` job runs the unit tests and `check.py` on the datasets a pull request changed; `promote` runs on a push to `main` with the repository secret `HF_TOKEN`.
- **Commits:** one sentence stating the behavior, as the shed's. A pull request is merged with a merge commit.
- **Before each commit:** `python3 -I -m unittest discover tests` passes; `bash -n` on every bash script.

## Review Focus

1. **A recipe directory with uncommitted changes:** `scripts/build` refuses it, naming the directory, so a candidate is always built from committed inputs. Pinned in Task 3.
2. **A record whose files do not match the Hub's tree at its commit** (a file added or changed after the test): `check.py --hub` fails, naming the first mismatched path. Pinned in Task 2.
3. **A push when the candidate branch already exists** from an earlier build of the same tree: the branch is replaced, not appended to, so the record's commit holds exactly the output. Pinned in Task 4.
4. **A tag that already exists at promote:** never moved; `promote` exits 1 naming the tag. Pinned in Task 4.
5. **A skill naming a tool the shed's catalogue lacks:** `check.py --hub` fails, naming the tool, before anything is built or pushed. Pinned in Task 2.

---

### Task 1: The repository, the check script, and its tests

**Files:**
- Create: `hub.toml`, `scripts/check.py`, `scripts/changed-datasets`, `tests/helpers.py`, `tests/test_check.py`, `tests/fixtures/datasets/tiny/SKILL.md`, `tests/fixtures/datasets/tiny/recipe/build`, `tests/fixtures/datasets/tiny/recipe/params.toml`, `tests/fixtures/datasets/tiny/recipe/test`, `.github/workflows/datasets.yml` (the `check` job only)
- Replace: `README.md`

**Interfaces:**
- Produces, in `scripts/check.py`: `frontmatter(path: Path) -> dict` (the five fields, `metadata` nested); `rules(dataset_dir: Path) -> list[str]` (the directory's problems, empty when fine); `tree_hash(recipe_dir: Path) -> str` (git's tree hash from the files); `scan(text: str) -> list[str]` (the credential shapes found); `hub_org() -> str` and `toolshed_registry() -> str` from `hub.toml`. Command line: `check.py <dataset dir>` (rules, exit 1 on any); `check.py --tree <dataset dir>` (prints the hash); `check.py --candidate <dataset dir>` (prints `candidate-<tree>`); `check.py --scan <file>` (exit 1 when a shape is found). `--hub` is Task 2's.
- Produces: `scripts/changed-datasets <git range>` prints the dataset names whose `datasets/<name>/` the range touched, one per line, as the shed's `changed-tools`.

- [ ] **Step 1: Write the fixture and the failing tests**

The fixture `tests/fixtures/datasets/tiny/` is a complete dataset directory: a skill with `name: tiny`, `metadata.version: 1.0.0`, `metadata.tool: hello@1.0.1`, `metadata.license: mit`; `recipe/build` (executable bash) that writes `train.txt` with three lines and `eval.txt` with one into its argument; `recipe/params.toml` with `seed = 1`; `recipe/test` (executable bash) that exits 0 iff both files exist with those line counts. In `tests/test_check.py`:

```python
def test_frontmatter_reads_the_five_fields(self):
    fm = check.frontmatter(TINY / "SKILL.md")
    self.assertEqual((fm["name"], fm["metadata"]["version"], fm["metadata"]["tool"], fm["metadata"]["license"]), ("tiny", "1.0.0", "hello@1.0.1", "mit"))

def test_rules_pass_on_the_fixture_and_name_each_defect(self):
    self.assertEqual(check.rules(TINY), [])
    with copy_of(TINY) as d:
        (d / "recipe" / "params.toml").unlink()
        self.assertIn("recipe/params.toml is missing", check.rules(d))
    with copy_of(TINY) as d:
        skill = d / "SKILL.md"; skill.write_text(skill.read_text().replace("name: tiny", "name: other"))
        self.assertIn("name 'other' is not the directory's 'tiny'", check.rules(d))
    with copy_of(TINY) as d:
        skill = d / "SKILL.md"; skill.write_text(skill.read_text().replace("version: 1.0.0", "version: 1.0"))
        self.assertIn("version '1.0' is not MAJOR.MINOR.PATCH", check.rules(d))
    with copy_of(TINY) as d:
        (d / "recipe" / "build").chmod(0o644)
        self.assertIn("recipe/build is not executable", check.rules(d))

def test_tree_hash_is_gits(self):
    with copy_of(TINY) as d:
        git = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x", *a], cwd=d, check=True, capture_output=True, text=True).stdout.strip()
        git("init", "-q"); git("add", "."); git("commit", "-q", "-m", "x")
        self.assertEqual(check.tree_hash(d / "recipe"), git("rev-parse", "HEAD:recipe"))

def test_scan_finds_credential_shapes(self):
    self.assertEqual(check.scan("token hf_" + "a" * 34 + " end"), ["hf_"])
    self.assertEqual(check.scan("nothing here"), [])

def test_hub_toml_names_the_org_and_the_shed(self):
    self.assertEqual((check.hub_org(), check.toolshed_registry()), ("brineylab", "ghcr.io/brineylab/toolshed"))
```

`copy_of` in `tests/helpers.py` copies a fixture into a temporary directory and yields its path.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python3 -I -m unittest discover tests`
Expected: FAIL with `ModuleNotFoundError: No module named 'check'` (the helpers put `scripts/` on `sys.path`).

- [ ] **Step 3: Write `hub.toml`, `scripts/check.py`, and `scripts/changed-datasets`**

`hub.toml`: the two lines in Global Constraints. `check.py`: the functions in Interfaces, Python 3.8 syntax, no third-party imports; `tree_hash` hashes each file as `blob <size>\0<bytes>` with sha1, each directory as a git tree object (entries sorted as git sorts, mode `100644` or `100755` by the executable bit, `40000` for subdirectories), and returns the hex of the recipe directory's tree; `rules` checks, in order: `SKILL.md` exists and its frontmatter parses with the five fields; `name` equals the directory's; `metadata.version` matches `^\d+\.\d+\.\d+$`; `metadata.tool` matches `^[a-z0-9-]+@\d+\.\d+\.\d+$`; `recipe/build` exists and is executable; `recipe/params.toml` exists and parses (`tomllib` on 3.11+, else a minimal `key = value` reader for the fixture's shapes: strings, ints, floats, booleans); `recipe/test` exists and is executable; `scan` of every file under the directory is empty. `changed-datasets`: bash, `git diff --name-only <range> -- datasets | cut -d/ -f2 | sort -u`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python3 -I -m unittest discover tests && python3 -I scripts/check.py tests/fixtures/datasets/tiny && echo ok`
Expected: `OK` from unittest, then `ok`.

- [ ] **Step 5: The `check` job and the README, then commit**

`.github/workflows/datasets.yml`: on `pull_request`, a job `check` on `ubuntu-latest` that checks out with full history, runs `python3 -I -m unittest discover tests`, then for each name from `scripts/changed-datasets origin/main...HEAD` runs `python3 -I scripts/check.py datasets/<name>` (Task 2 adds `--hub`). `README.md`: what the repository is (two sentences from VISION), finding a dataset (`ls datasets`, each skill's `description`), reading one from anywhere (the `snapshot_download` line with `repo_type="dataset"` and a `revision`), on bcr (`export HF_HUB_CACHE=/mnt/data/datasets/hub-cache` to share the cluster's cache), installing the skills into an agent (clone, then symlink each `datasets/<name>` into the harness's skills directory, as the shed's README says), and a pointer to `CONTRIBUTING.md` (Task 6).

```bash
git add -A && git commit -m "The repository's check script knows a dataset directory's rules and its recipe tree"
```

### Task 2: The check script reads the Hub: the version, the tool, and the record

**Files:**
- Modify: `scripts/check.py`, `.github/workflows/datasets.yml`
- Create: `tests/test_check_hub.py`, `tests/fixtures/results/tiny/1.0.0.txt`, `tests/fixtures/hub/` (JSON answers the stub serves)

**Interfaces:**
- Consumes: Task 1's `frontmatter`, `rules`, `tree_hash`.
- Produces: `check.py --hub <dataset dir>`: exit 1 with a reason when the version's tag exists on `<org>/<name>`, when the record is missing for this version, when the record's `commit` is not on the Hub or its tree does not hold exactly the record's `file` lines (path, size, sha256), when the record's `exit` is not 0, or when `metadata.tool` is not in the shed's catalogue. Functions: `hub_get(url: str) -> object` (JSON over `urllib.request`, no token, 404 as `None`); `parse_record(path: Path) -> dict` (the header fields and the `files` list of `(path, size, sha256)` from the body); `shed_catalogue() -> set[str]` (`name@version` for every `tools/*/SKILL.md` on the shed's `main`, read through `https://raw.githubusercontent.com/<owner>/<repo>/main/tools/<name>/SKILL.md` after listing `tools/` through `https://api.github.com/repos/<owner>/<repo>/contents/tools`, with `<owner>/<repo>` from `hub.toml`'s `toolshed` registry path).
- The Hub endpoints, all public GETs: `https://huggingface.co/api/datasets/<org>/<name>/refs` (`{"branches": [...], "tags": [{"name": "v1.0.0", "targetCommit": "<sha>"}]}`); `https://huggingface.co/api/datasets/<org>/<name>/tree/<commit>?recursive=true&expand=true` (a list of `{"type": "file", "path": ..., "size": ..., "lfs": {"oid": "<sha256>", "size": ...}}` for LFS files; a non-LFS file such as `README.md` has no `lfs`).

- [ ] **Step 1: Write the fixture record and the failing tests**

`tests/fixtures/results/tiny/1.0.0.txt` in the record format, `files` being `train.txt 18 <sha256 of its bytes>` and `eval.txt 6 <sha256>`, `commit` and `tree` forty hex characters, `exit: 0`. `tests/fixtures/hub/` holds `refs.json` (no tags), `tree.json` (the two files with those sha256s as `lfs.oid` plus a `README.md` without `lfs`), `catalogue.json` (a `tools/` listing with `hello`), and `hello-SKILL.md` (frontmatter with `version: 1.0.1`). The stub replaces `check.hub_get` and `check.shed_catalogue` with lookups into those files. Tests:

```python
def test_a_fresh_version_with_a_matching_record_passes(self): self.assertEqual(check.hub_problems(TINY, RESULTS), [])
def test_an_existing_tag_is_refused(self): ...refs.json with tag v1.0.0... self.assertIn("v1.0.0 is already on the Hub", problems)
def test_a_missing_record_is_refused(self): self.assertIn("results/tiny/1.0.0.txt is missing", check.hub_problems(TINY, EMPTY))
def test_a_record_whose_files_differ_from_the_hub_is_refused(self): ...tree.json with eval.txt's sha256 changed... self.assertIn("eval.txt differs from the Hub", problems)
def test_a_record_with_a_nonzero_exit_is_refused(self): self.assertIn("the record's exit is 1", problems)
def test_a_tool_the_shed_lacks_is_refused(self): ...skill with tool nothere@1.0.0... self.assertIn("nothere@1.0.0 is not in the toolshed", problems)
def test_parse_record_reads_the_header_and_the_files(self): r = check.parse_record(RESULTS / "tiny" / "1.0.0.txt"); self.assertEqual((r["version"], r["exit"], len(r["files"])), ("1.0.0", 0, 2))
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -I -m unittest tests.test_check_hub`
Expected: FAIL with `AttributeError: module 'check' has no attribute 'hub_problems'`.

- [ ] **Step 3: Implement `hub_problems(dataset_dir, results_dir) -> list[str]`, `parse_record`, `hub_get`, `shed_catalogue`, and `--hub`**

The file comparison: the record's `files` set must equal the set of the Hub tree's LFS files, by `(path, size, sha256)`; a file in one and not the other, or differing, is named with "differs from the Hub" or "is not on the Hub" / "is not in the record". `--hub` runs `rules` first and then `hub_problems`; `shed_catalogue` is called only when the rules pass.

- [ ] **Step 4: Run the tests and the job**

Run: `python3 -I -m unittest discover tests`
Expected: `OK`. In `datasets.yml`, the `check` job's per-dataset command becomes `python3 -I scripts/check.py --hub datasets/<name>`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "The check script proves a version is new, its tool is in the shed, and the Hub holds exactly the record's files"
```

### Task 3: The contributor builds and tests a candidate, and the record has one writer

**Files:**
- Create: `scripts/build`, `scripts/test`, `scripts/record`, `tests/test_scripts.py`, `tests/stubs/podman` (an executable that records its arguments and runs the recipe on the host)

**Interfaces:**
- Produces: `scripts/build <name> <outroot> [podman]`: refuses a dirty `datasets/<name>/` (`git status --porcelain`), runs `check.py` on it, computes `<tree>` with `check.py --tree`, and if `<outroot>/<name>/<tree>/.built` exists prints `built: <outroot>/<name>/<tree> (skipped)` and exits 0; else runs `datasets/<name>/recipe/build <outroot>/<name>/<tree>` (directly, or with `podman` as `podman run --rm --userns=keep-id -v "$PWD":/work -v "<outroot>":"<outroot>" -w /work <toolshed>/<tool name>:<tool version> bash datasets/<name>/recipe/build <outroot>/<name>/<tree>`, the image from the skill's `metadata.tool` and `hub.toml`'s `toolshed`), writes `.built` on success, and prints `built: <outroot>/<name>/<tree>`. `scripts/test <name> <outroot> [podman]`: runs `recipe/test <outroot>/<name>/<tree>` the same way, passes its output through, and exits with its code. `scripts/record <name> <commit> <exit> <runner> <host> <started> < output`: the format in Global Constraints, `branch` and `tree` from `check.py --candidate`/`--tree`, `tool` from the skill, refusing output that fails `--scan` (exit 1, nothing written), printing the record's path.

- [ ] **Step 1: Write the failing tests**

With the `tiny` fixture copied into a temporary git repository (committed) and `tests/stubs` first on `PATH`:

```python
def test_build_refuses_uncommitted_changes(self): ...append a line to recipe/params.toml, no commit... self.assertEqual(run("scripts/build", "tiny", out).returncode, 1); self.assertIn("datasets/tiny has uncommitted changes", stderr)
def test_build_writes_the_version_under_the_tree_and_skips_the_second_time(self):
    p = run("scripts/build", "tiny", out); tree = run("python3", "-I", "scripts/check.py", "--tree", "datasets/tiny").stdout.strip()
    self.assertEqual(p.stdout.strip(), f"built: {out}/tiny/{tree}"); self.assertTrue((out / "tiny" / tree / "train.txt").exists())
    self.assertIn("(skipped)", run("scripts/build", "tiny", out).stdout)
def test_build_with_podman_wraps_the_recipe_in_the_tools_image(self):
    run("scripts/build", "tiny", out, "podman"); args = (Path(tests_tmp) / "podman.args").read_text()
    self.assertIn("ghcr.io/brineylab/toolshed/hello:1.0.1", args); self.assertIn("bash datasets/tiny/recipe/build", args)
def test_test_passes_the_recipes_verdict_through(self): self.assertEqual(run("scripts/test", "tiny", out).returncode, 0); ...remove eval.txt...; self.assertEqual(run("scripts/test", "tiny", out).returncode, 1)
def test_record_writes_the_format_and_refuses_a_credential(self):
    p = run("scripts/record", "tiny", "a" * 40, "0", "podman", "laptop", "2026-11-05T00:00:00Z", input="file train.txt 18 ...\ncommit: " + "a" * 40 + "\n")
    rec = Path("results/tiny/1.0.0.txt").read_text(); self.assertTrue(rec.startswith("---\ndataset: tiny\nversion: 1.0.0\nhub: brineylab/tiny\nbranch: candidate-"))
    self.assertEqual(run("scripts/record", "tiny", "a" * 40, "0", "podman", "laptop", "now", input="hf_" + "b" * 34).returncode, 1)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -I -m unittest tests.test_scripts`
Expected: FAIL, `scripts/build: No such file or directory`.

- [ ] **Step 3: Write the three scripts and the podman stub**

Bash, `set -euo pipefail`, `cd "$(dirname "$0")/.."` first, as the shed's. The podman stub writes its arguments to `$TESTS_TMP/podman.args` and executes the command after `--` ... (the part after the image) on the host, so the fixture recipe runs.

- [ ] **Step 4: Run the tests; `bash -n` each script**

Run: `python3 -I -m unittest discover tests && bash -n scripts/build scripts/test scripts/record && echo ok`
Expected: `OK`, `ok`.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "The contributor builds a candidate from committed inputs, tests its output, and writes the record"
```

### Task 4: The push, the promotion, and the workflow's second job

**Files:**
- Create: `scripts/push`, `scripts/promote`, `tests/test_push_promote.py`, `tests/stubs/huggingface_hub/__init__.py` (a fake `HfApi` that records calls and answers from in-memory state)
- Modify: `.github/workflows/datasets.yml` (the `promote` job)

**Interfaces:**
- Produces: `scripts/push <name> <outroot>` (Python, `python3 -I`, `huggingface_hub` imported): `HfApi(token=os.environ["HF_TOKEN"])`; `create_repo("<org>/<name>", repo_type="dataset", exist_ok=True)`; delete `candidate-<tree>` if it exists (ignore a 404), `create_branch(branch, revision="main")`; `upload_folder(folder_path=<outroot>/<name>/<tree>, repo_id, repo_type="dataset", revision=branch, commit_message="<name> <version>: the output of recipe tree <tree>", ignore_patterns=[".built"])`; the card: `upload_file` of `README.md` built from the skill (a YAML header with `license: <metadata.license>` and `pretty_name: <name>`, then the skill's body after the frontmatter) to the same branch; then print one `file <path> <size> <sha256>` line per data file (sha256 computed locally, sorted by path) and `commit: <oid of the card commit>`. `scripts/promote <name> <version>`: reads `results/<name>/<version>.txt`, `create_tag(repo_id, tag="v<version>", revision=<record's commit>, repo_type="dataset")` and exits 1 naming the tag if it exists; then `delete_branch(repo_id, branch=<record's branch>, repo_type="dataset")`, ignoring a 404; prints `promoted: <org>/<name> v<version> at <commit>`.
- The `promote` job: on `push` to `main`, `ubuntu-latest`, `pip install huggingface_hub`, for each name from `scripts/changed-datasets <before>...<after>` (the push event's shas) run `python3 -I scripts/promote <name> <version from the skill>` with `HF_TOKEN: ${{ secrets.HF_TOKEN }}`.

- [ ] **Step 1: Write the fake and the failing tests**

The fake `HfApi` keeps `repos`, `branches` (name to commit), `tags`, and `calls`; `upload_folder` and `upload_file` return objects with `.oid` of forty hex characters, each new; `create_tag` raises `HfHubHTTPError` with a 409 when the tag exists; `delete_branch` raises a 404-shaped error when the branch is absent. Tests, with `tests/stubs` first on `sys.path` and `HF_TOKEN=hf_test`:

```python
def test_push_creates_the_repo_replaces_the_candidate_and_prints_the_manifest(self):
    api.branches["candidate-" + tree] = "old"
    out = run("python3", "-I", "scripts/push", "tiny", outroot).stdout.splitlines()
    self.assertEqual(api.calls[:3], [("create_repo", "brineylab/tiny"), ("delete_branch", "candidate-" + tree), ("create_branch", "candidate-" + tree)])
    self.assertEqual(out[:2], [f"file eval.txt 6 {sha_eval}", f"file train.txt 18 {sha_train}"]); self.assertRegex(out[2], r"^commit: [0-9a-f]{40}$"); self.assertEqual(len(out), 3)
    self.assertIn(("upload_file", "README.md"), api.calls); self.assertNotIn("hf_test", "\n".join(out))
def test_the_card_carries_the_license_and_the_skills_body(self): card = api.files["README.md"]; self.assertTrue(card.startswith("---\nlicense: mit\npretty_name: tiny\n---\n")); self.assertIn("## Files", card)
def test_promote_tags_the_records_commit_and_deletes_the_branch(self): ...; self.assertEqual(api.tags["v1.0.0"], record_commit); self.assertNotIn(branch, api.branches)
def test_promote_never_moves_an_existing_tag(self): api.tags["v1.0.0"] = "x" * 40; p = run(...promote...); self.assertEqual(p.returncode, 1); self.assertIn("v1.0.0 already exists", p.stderr); self.assertEqual(api.tags["v1.0.0"], "x" * 40)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `python3 -I -m unittest tests.test_push_promote`
Expected: FAIL, `scripts/push: No such file or directory`.

- [ ] **Step 3: Write `scripts/push`, `scripts/promote`, and the `promote` job**

- [ ] **Step 4: Run the tests**

Run: `python3 -I -m unittest discover tests`
Expected: `OK`.

- [ ] **Step 5: Commit, and set the secret**

```bash
git add -A && git commit -m "A candidate is pushed to the Hub with its card, and a merge promotes the record's commit to its version tag"
```

Then, once, by a person: a Hub token with write access to the `brineylab` org's datasets as the repository secret `HF_TOKEN` (`gh secret set HF_TOKEN`).

### Task 5: The recipe image, in the toolshed

**Files (in a clone of `brineylab/toolshed`, on a branch):**
- Create: `tools/abstar/SKILL.md`, `tools/abstar/Containerfile`, `tools/abstar/test/run.sh`, `tools/abstar/test/tiny.fasta`
- Create, after the test: `results/abstar/1.0.0.txt`

**Interfaces:**
- Produces: the shed's `abstar@1.0.0`, `ghcr.io/brineylab/toolshed/abstar:1.0.0`, the image every recipe here runs in for now.

- [ ] **Step 1: Write the tool, following the shed's `CONTRIBUTING.md`**

`Containerfile`: `FROM python:3.12-slim` pinned by digest; `apt-get` `wget` and `ca-certificates`; mmseqs2 from its GitHub release tarball at a pinned version (`mmseqs-linux-avx2.tar.gz`), its binary on PATH; `pip install abstar==0.8.0 polars==<pinned> pyarrow==<pinned> huggingface_hub==<pinned>` with versions current at build time; `python3 -c "import abstar"` at build time so the germline databases abstar ships are present; **no** `HF_HUB_OFFLINE`, and the skill says why; no `NVIDIA_*` (a CPU tool); `COPY test /toolshed/test` last. `SKILL.md`: `name: abstar`, `metadata.version: 1.0.0`, description "Antibody annotation (abstar), clustering (mmseqs2), and the Python a dataset recipe needs; the recipe image of brineylab/datasets, built without HF_HUB_OFFLINE so a recipe can push to the Hub"; `## Commands`: `abstar run <fasta or dir> <project dir> -o parquet [--germline_database human|mouse|...]`, `mmseqs easy-cluster <fasta> <prefix> <tmp> --min-seq-id 0.9 -c 0.8`; `## Running it`: the podman line and the `request_run` line as the shed's skills have; `## Gotchas`: this image reaches the network and is meant to. `test/run.sh`: `abstar run /toolshed/test/tiny.fasta /tmp/abstar -o parquet` on a fixture of ten real antibody heavy and light chains, then `python3 -c` asserting the parquet has ten rows with a `v_call` column, `mmseqs version`, and `python3 -c "import huggingface_hub, polars, pyarrow"`.

- [ ] **Step 2: Build, push, test, record, pull request**

Per the shed's `CONTRIBUTING.md`: `scripts/build abstar`, `podman run --rm <candidate> bash /toolshed/test/run.sh` (with network, since the test needs none but the image allows it), `scripts/push abstar` (the shed's seed creates the package), `scripts/test abstar podman` on the laptop or `scripts/test abstar srun --partition=cpu --time=00:30:00` on bcr (a CPU tool; the shed's test asks for one GPU by convention, and this one passes without), commit the record, open the pull request, a member other than the builder reviews, merge, `promote` publishes `abstar:1.0.0`.

- [ ] **Step 3: Confirm**

Run: `podman run --rm ghcr.io/brineylab/toolshed/abstar:1.0.0 abstar --help | head -3`
Expected: abstar's usage.

### Task 6: `hello`, and the repository's first version end to end

**Files:**
- Create: `datasets/hello/SKILL.md`, `datasets/hello/recipe/build`, `datasets/hello/recipe/params.toml`, `datasets/hello/recipe/test`, `CONTRIBUTING.md`
- Create, after the build: `results/hello/1.0.0.txt`

**Interfaces:**
- Produces: `brineylab/hello` on the Hub at `v1.0.0`: `train.parquet`, `eval.parquet`, `test.parquet`, columns `pair_id` (string), `sequence_heavy`, `sequence_light` (strings of amino acids), 240, 30, and 30 rows.

- [ ] **Step 1: Write the dataset**

`params.toml`: `seed = 1`, `pairs = 300`, `split = [0.8, 0.1, 0.1]`. `recipe/build` (Python under `#!/usr/bin/env -S python3 -I`): a `random.Random(seed)` makes `pairs` heavy chains of 110 to 130 and light chains of 105 to 115 letters from the twenty amino acids, each pair's `pair_id` `hello-<i:04d>`; the split is by `pair_id` order after a seeded shuffle; three parquet files written with `polars`. `recipe/test <out>`: reads the three files with `polars`, asserts the columns and the row counts, and that no `pair_id` is in two splits. `SKILL.md`: `tool: abstar@1.0.0`, `license: mit`, and the sections of DESIGN §2, with `## Reading it` showing the `snapshot_download` line for `brineylab/hello` at `v1.0.0` and a `polars.read_parquet` of `train.parquet`.

- [ ] **Step 2: Build, test, push, record, on a laptop**

```bash
git checkout -b hello && git add datasets/hello && git commit -m "hello: 300 synthetic antibody pairs, the repository's smoke dataset"
scripts/build hello ./out podman && scripts/test hello ./out podman
HF_TOKEN=... scripts/push hello ./out | tee /tmp/push.out        # inside the image: podman run --rm -e HF_TOKEN -v "$PWD":/work -v "$PWD/out":"$PWD/out" -w /work ghcr.io/brineylab/toolshed/abstar:1.0.0 python3 -I scripts/push hello ./out
{ scripts/test hello ./out podman; cat /tmp/push.out; } | scripts/record hello "$(grep '^commit:' /tmp/push.out | cut -d' ' -f2)" 0 podman "$(hostname)" "$(date -u +%FT%TZ)"
git add results/hello/1.0.0.txt && git commit -m "hello 1.0.0's record: its candidate passed on a laptop"
```

Expected: `brineylab/hello` exists on the Hub with branch `candidate-<tree>` holding the three parquet files and the card; `results/hello/1.0.0.txt` names that commit and lists the three files; `python3 -I scripts/check.py --hub datasets/hello` passes.

- [ ] **Step 3: `CONTRIBUTING.md`**

The shed's `CONTRIBUTING.md` transposed: the layout, the conventions (AGENTS.md's rules, in prose with the why), building where the dataset will be built (the `srun` line on a cluster's login node inside the image: `srun --partition=<p> --cpus-per-task=<n> --mem=<m> --time=<t> --container-image=ghcr.io#brineylab/toolshed/abstar:1.0.0 --container-mounts=/mnt/data:/mnt/data bash -c 'scripts/build <name> <outroot> && scripts/test <name> <outroot> && scripts/push <name> <outroot>'`, and the podman line), the record, versions, the pull request and the review questions (does the skill describe the files the record lists and state the recipe's inputs; does the record show the test passed where the build ran; is the version new; is the tool the one the record shows), and the Hub token.

- [ ] **Step 4: The pull request, the check, the merge, the promotion**

```bash
git push -u origin hello && gh pr create --title "hello 1.0.0" --body "The repository's smoke dataset, built and tested on a laptop; the record is in the pull request."
```

Expected: `check` passes (the version is new, the tool is in the shed, the Hub's candidate holds exactly the record's files). A member other than the builder reviews and merges with a merge commit; `promote` runs on the merge commit and tags `v1.0.0`; the candidate branch is gone.

- [ ] **Step 5: Read it back from anywhere**

Run, in a fresh Python environment with `huggingface_hub` and `polars`: `python3 -c "from huggingface_hub import snapshot_download; import polars as pl; p = snapshot_download('brineylab/hello', repo_type='dataset', revision='v1.0.0'); print(pl.read_parquet(p + '/train.parquet').shape)"`
Expected: `(240, 3)`. On bcr, from a notebook with `HF_HUB_CACHE=/mnt/data/datasets/hub-cache` once that directory exists: the same.

### Task 7: `oas-paired-human`

**Files:**
- Create: `datasets/oas-paired-human/SKILL.md`, `datasets/oas-paired-human/recipe/build`, `datasets/oas-paired-human/recipe/params.toml`, `datasets/oas-paired-human/recipe/test`, `datasets/oas-paired-human/recipe/sources.txt`
- Create, after the build: `results/oas-paired-human/1.0.0.txt`

**Interfaces:**
- Produces: `brineylab/oas-paired-human` at `v1.0.0`: `train.parquet`, `eval.parquet`, `test.parquet` (sharded as `train-00000-of-0000N.parquet` when a file would pass 2 GB), one row per pair: `pair_id`, `sequence_heavy`, `sequence_light` (nucleotide), `sequence_aa_heavy`, `sequence_aa_light`, abstar's annotation columns for each chain prefixed `heavy_` and `light_` (`v_call`, `d_call`, `j_call`, `cdr3_aa`, `junction_aa`, `productive`, and the rest abstar writes), `cluster` (the mmseqs cluster representative's `pair_id`), and the OAS metadata columns `study`, `subject`, `isotype_heavy`, `isotype_light`.

- [ ] **Step 1: The recipe's inputs**

`sources.txt`: the download lines OAS gives for its paired data filtered to `Species: human` (the bulk-download script from https://opig.stats.ox.ac.uk/webapps/oas/oas_paired/, one `wget` URL per line, the header lines dropped), committed as the pull's content; `params.toml`: `pulled = "<the date sources.txt was taken>"`, `species = "human"`, `identity = 0.9`, `coverage = 0.8`, `split = [0.9, 0.05, 0.05]`, `seed = 1`, `germline_database = "human"`, and `limit = 0` (a developer's dry run sets a positive number of pairs per source file; the published version has 0). These values are the plan's choices for the lab to confirm before the build; the skill states them.

- [ ] **Step 2: Write the recipe**

`recipe/build <out>` (Python, `polars`, running in `abstar@1.0.0`), in order, each stage under `<out>/.work/` so a rerun resumes: (1) download every URL in `sources.txt` with `urllib`, skipping files already present with the expected size; (2) read each OAS CSV (one JSON metadata line, then the table), keep pairs whose heavy and light `sequence` are present, drop exact duplicate pairs by `(sequence_heavy, sequence_light)`, write one FASTA of the heavy chains and one of the light with `pair_id` as the name, `pair_id` being `<study>-<row>`; (3) `mmseqs easy-cluster` on the concatenated `sequence_aa_heavy + "/" + sequence_aa_light` at `identity` and `coverage`, reading the cluster table into a `cluster` column; (4) split by cluster: shuffle the cluster representatives with `seed`, assign whole clusters to train, eval, and test by the `split` fractions of pairs, so no cluster spans splits; (5) `abstar run` on each FASTA with `--germline_database` and `-o parquet`, joining each chain's annotation back on `pair_id` with the `heavy_`/`light_` prefixes; (6) write the splits as parquet, sharded at 2 GB. `recipe/test <out>`: the files and columns; each split's row count at least `limit`-aware floors (for the published version: train over 1,000,000 pairs); no `pair_id` in two splits; no cluster in two splits (join on `cluster`); every row `productive` on both chains. The skill's `## Compute`: what the build took, filled in after Step 3.

- [ ] **Step 3: Build where it will be built**

On bcr's login node, inside the image on the CPU partition (Task 6's `srun` line with `--cpus-per-task=64 --mem=256G --time=24:00:00` and `<outroot>` under the builder's own directory on `/mnt/data`), or on coreweave-rtx6000's `hpc-low` with the same line and the GPU partition's spare CPUs. A dry run first with `limit = 1000` in a scratch copy of `params.toml` (not committed) to shake out the recipe in minutes; then the real build. Record the wall time, CPUs, memory, and disk in the skill.

- [ ] **Step 4: Test, push, record, pull request, review, merge, promote**

As Task 6's Steps 2 and 4, with `runner` `srun` and `host` the cluster's. The reviewer checks the skill's stated inputs against `params.toml` and `sources.txt`, the record's row counts, and that the test passed on the cluster.

- [ ] **Step 5: Read it back**

Run: the `snapshot_download` line for `brineylab/oas-paired-human` at `v1.0.0`, then `polars.scan_parquet(p + "/train*.parquet").select(pl.len()).collect()`.
Expected: the row count the record states. Update `docs/DESIGN.md`'s status line with the date and the counts.

### Task 8: The scratch repository for flyloft's tier two

**Files:**
- A second GitHub repository, `brineylab/datasets-dev`, a copy of this one at Task 6's merge, with `hub.toml`'s `org` set to a scratch Hub organization the lab creates for tests (`brineylab-dev` **(call)**), `hello` published there at `v1.0.0` through the same path, and the `HF_TOKEN` secret set with write on that org.

- [ ] **Step 1: Create it and publish `hello`**

`gh repo create brineylab/datasets-dev --public --description "A scratch copy of brineylab/datasets for flyloft's live tests"`, push this repository's `main` to it, change `hub.toml`, commit, and run Task 6's Steps 2 and 4 against it. Expected: `brineylab-dev/hello` on the Hub at `v1.0.0`; `check` and `promote` green on the scratch repository. flyloft's plan B names it.
