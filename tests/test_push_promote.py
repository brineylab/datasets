import hashlib, json, os, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from helpers import ROOT, TINY, git
import check  # noqa: E402

STUBS = ROOT / "tests" / "stubs"
# Each script runs as `python3 -I` does, with the fake huggingface_hub first on sys.path, which -I would not take from PYTHONPATH.
LAUNCH = "import runpy, sys; sys.path.insert(0, sys.argv[1]); sys.argv = sys.argv[2:]; runpy.run_path(sys.argv[0], run_name='__main__')"

class PushPromoteTests(unittest.TestCase):
    """The real scripts in a temporary repository holding the tiny fixture, built; the Hub is the fake's JSON file."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.tmp)
        self.repo, self.out, self.hub = self.tmp / "repo", self.tmp / "out", self.tmp / "hub.json"
        (self.repo / "scripts").mkdir(parents=True)
        for s in ("push", "promote", "check.py"):
            shutil.copy(ROOT / "scripts" / s, self.repo / "scripts")
        shutil.copy(ROOT / "hub.toml", self.repo)
        shutil.copytree(TINY, self.repo / "datasets" / "tiny")
        git(self.repo, "init", "-q"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "tiny")
        self.tree = check.tree_hash(self.repo / "datasets/tiny/recipe")
        self.branch = "candidate-" + self.tree
        built = self.out / "tiny" / self.tree
        subprocess.run([str(TINY / "recipe" / "build"), str(built)], check=True)
        (built / ".built").touch(); (built / ".work").mkdir(); (built / ".work" / "source.csv").write_text("staged\n")

    def run_script(self, *args):
        env = {**os.environ, "HF_TOKEN": "hf_test", "FAKE_HUB": str(self.hub)}
        return subprocess.run([sys.executable, "-I", "-c", LAUNCH, str(STUBS), *map(str, args)], cwd=self.repo, env=env, capture_output=True, text=True)

    def state(self):
        return json.loads(self.hub.read_text())

    def sha(self, name):
        return hashlib.sha256((self.out / "tiny" / self.tree / name).read_bytes()).hexdigest()

    def test_push_creates_the_repo_replaces_the_candidate_and_prints_the_manifest(self):
        self.hub.write_text(json.dumps({"branches": {"main": "m" * 40, self.branch: "old"}}))
        r = self.run_script("scripts/push", "tiny", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        out, s = r.stdout.splitlines(), self.state()
        self.assertEqual(s["calls"][:3], [["create_repo", "brineylab/tiny"], ["delete_branch", self.branch], ["create_branch", self.branch]])
        self.assertEqual(out[:2], [f"file eval.txt 6 {self.sha('eval.txt')}", f"file train.txt 18 {self.sha('train.txt')}"])
        self.assertEqual(out[2], f"commit: {s['branches'][self.branch]}"); self.assertRegex(out[2], r"^commit: [0-9a-f]{40}$"); self.assertEqual(len(out), 3)
        self.assertEqual(s["uploaded"], ["eval.txt", "train.txt"])  # neither .built nor .work/
        self.assertIn(["upload_file", "README.md"], s["calls"]); self.assertNotIn("hf_test", r.stdout + r.stderr)

    def test_push_of_a_new_candidate_creates_its_branch(self):
        self.assertEqual(self.run_script("scripts/push", "tiny", self.out).returncode, 0)
        self.assertEqual([c[0] for c in self.state()["calls"][:3]], ["create_repo", "delete_branch", "create_branch"])

    def test_push_refuses_an_output_that_was_not_built(self):
        (self.out / "tiny" / self.tree / ".built").unlink()
        r = self.run_script("scripts/push", "tiny", self.out)
        self.assertEqual(r.returncode, 1); self.assertIn("is not built", r.stderr); self.assertFalse(self.hub.exists())

    def test_the_card_carries_the_license_and_the_skills_body(self):
        self.run_script("scripts/push", "tiny", self.out)
        card = self.state()["files"]["README.md"]
        self.assertTrue(card.startswith("---\nlicense: mit\npretty_name: tiny\n---\n")); self.assertIn("## Files", card)
        self.assertNotIn("hello@1.0.1", card)  # the skill's frontmatter stays in the skill

    def record(self, commit):
        (self.repo / "results/tiny").mkdir(parents=True)
        (self.repo / "results/tiny/1.0.0.txt").write_text(f"---\ndataset: tiny\nversion: 1.0.0\nhub: brineylab/tiny\nbranch: {self.branch}\n"
                                                         f"commit: {commit}\ntree: {self.tree}\nexit: 0\n---\ncommit: {commit}\n")

    def test_promote_tags_the_records_commit_and_deletes_the_branch(self):
        self.hub.write_text(json.dumps({"branches": {"main": "m" * 40, self.branch: "c" * 40}}))
        self.record("c" * 40)
        r = self.run_script("scripts/promote", "tiny", "1.0.0")
        self.assertEqual(r.returncode, 0, r.stderr)
        s = self.state()
        self.assertEqual(s["tags"]["v1.0.0"], "c" * 40); self.assertNotIn(self.branch, s["branches"])
        self.assertEqual(r.stdout.splitlines()[-1], f"promoted: brineylab/tiny v1.0.0 at {'c' * 40}")

    def test_promote_never_moves_an_existing_tag(self):
        self.hub.write_text(json.dumps({"branches": {self.branch: "c" * 40}, "tags": {"v1.0.0": "x" * 40}}))
        self.record("c" * 40)
        r = self.run_script("scripts/promote", "tiny", "1.0.0")
        self.assertEqual(r.returncode, 1); self.assertIn("v1.0.0 already exists", r.stderr)
        self.assertEqual(self.state()["tags"]["v1.0.0"], "x" * 40); self.assertIn(self.branch, self.state()["branches"])

    def test_promote_run_again_after_it_succeeded_passes(self):
        self.hub.write_text(json.dumps({"tags": {"v1.0.0": "c" * 40}}))
        self.record("c" * 40)
        r = self.run_script("scripts/promote", "tiny", "1.0.0")
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("already promoted", r.stdout)

if __name__ == "__main__":
    unittest.main()
