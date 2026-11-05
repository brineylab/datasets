import os, shutil, subprocess, tempfile, unittest
from pathlib import Path
from helpers import ROOT, TINY, git
import check  # noqa: E402

STUBS = ROOT / "tests" / "stubs"

class ScriptTests(unittest.TestCase):
    """The real scripts in a temporary repository holding the tiny fixture as datasets/tiny, committed; podman is the stub."""
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, self.tmp)
        self.repo, self.out = self.tmp / "repo", self.tmp / "out"
        (self.repo / "scripts").mkdir(parents=True)
        for s in ("build", "test", "record", "check.py"):
            shutil.copy(ROOT / "scripts" / s, self.repo / "scripts")
        shutil.copy(ROOT / "hub.toml", self.repo)
        shutil.copytree(TINY, self.repo / "datasets" / "tiny")
        git(self.repo, "init", "-q"); git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "tiny")
        self.tree = check.tree_hash(self.repo / "datasets" / "tiny" / "recipe")

    def run_script(self, script, *args, input=None):
        env = {**os.environ, "PATH": f"{STUBS}:{os.environ['PATH']}", "TESTS_TMP": str(self.tmp)}
        return subprocess.run(["bash", f"scripts/{script}", *map(str, args)], cwd=self.repo, env=env, input=input, capture_output=True, text=True)

    def test_build_refuses_uncommitted_changes(self):
        with open(self.repo / "datasets/tiny/recipe/params.toml", "a") as f: f.write("more = 2\n")
        r = self.run_script("build", "tiny", self.out)
        self.assertEqual(r.returncode, 1); self.assertIn("datasets/tiny has uncommitted changes", r.stderr)
        self.assertFalse((self.out / "tiny").exists())

    def test_build_refuses_when_git_cannot_say_the_inputs_are_committed(self):
        shutil.rmtree(self.repo / ".git")
        r = self.run_script("build", "tiny", self.out)
        self.assertEqual(r.returncode, 1); self.assertIn("cannot tell whether datasets/tiny is committed", r.stderr)
        self.assertFalse((self.out / "tiny").exists())

    def test_build_refuses_an_output_built_with_another_tool(self):
        self.assertEqual(self.run_script("build", "tiny", self.out).returncode, 0)
        self.assertEqual((self.out / "tiny" / self.tree / ".built").read_text(), "hello@1.0.1\n")
        skill = self.repo / "datasets/tiny/SKILL.md"
        skill.write_text(skill.read_text().replace("hello@1.0.1", "hello@1.0.2").replace("version: 1.0.0", "version: 1.0.1"))
        git(self.repo, "commit", "-qam", "the tool moves")
        r = self.run_script("build", "tiny", self.out)
        self.assertEqual(r.returncode, 1); self.assertIn("was built with hello@1.0.1, not the skill's hello@1.0.2", r.stderr)

    def test_build_refuses_a_dataset_holding_a_credential_before_running(self):
        (self.repo / "datasets/tiny/recipe/notes").write_text("hf_" + "a" * 34 + "\n")
        git(self.repo, "add", "-A"); git(self.repo, "commit", "-qm", "leak")
        r = self.run_script("build", "tiny", self.out)
        self.assertEqual(r.returncode, 1); self.assertIn("recipe/notes holds what looks like a credential (hf_)", r.stdout)
        self.assertFalse((self.out / "tiny").exists())

    def test_build_writes_the_version_under_the_tree_and_skips_the_second_time(self):
        r = self.run_script("build", "tiny", self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), f"built: {self.out}/tiny/{self.tree}")
        self.assertTrue((self.out / "tiny" / self.tree / "train.txt").exists())
        self.assertIn("(skipped)", self.run_script("build", "tiny", self.out).stdout)

    def test_build_takes_a_relative_outroot(self):
        r = self.run_script("build", "tiny", "out")
        self.assertEqual(r.stdout.strip(), f"built: {self.repo}/out/tiny/{self.tree}")

    def test_build_with_podman_wraps_the_recipe_in_the_tools_image(self):
        self.assertEqual(self.run_script("build", "tiny", self.out, "podman").returncode, 0)
        args = (self.tmp / "podman.args").read_text()
        self.assertIn("ghcr.io/brineylab/toolshed/hello:1.0.1", args)
        self.assertIn(f"datasets/tiny/recipe/build {self.out}/tiny/{self.tree}", args)
        self.assertTrue((self.out / "tiny" / self.tree / ".built").exists())

    def test_test_passes_the_recipes_verdict_through(self):
        self.run_script("build", "tiny", self.out)
        r = self.run_script("test", "tiny", self.out)
        self.assertEqual(r.returncode, 0); self.assertIn("train.txt 3 rows", r.stdout)
        (self.out / "tiny" / self.tree / "eval.txt").unlink()
        self.assertEqual(self.run_script("test", "tiny", self.out).returncode, 1)
        r = self.run_script("test", "tiny", self.out, "podman")
        self.assertEqual(r.returncode, 1); self.assertIn("hello:1.0.1", (self.tmp / "podman.args").read_text())

    def test_test_refuses_an_output_that_was_not_built(self):
        r = self.run_script("test", "tiny", self.out)
        self.assertEqual(r.returncode, 1); self.assertIn("is not built", r.stderr)

    def test_record_writes_the_format_and_refuses_a_credential(self):
        out = f"train.txt 3 rows, eval.txt 1 row\nfile train.txt 18 {'c' * 64}\ncommit: {'a' * 40}\n"
        r = self.run_script("record", "tiny", "a" * 40, "0", "podman", "laptop", "2026-11-05T00:00:00Z", input=out)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, "results/tiny/1.0.0.txt"), r.stderr)
        path = self.repo / "results/tiny/1.0.0.txt"
        self.assertEqual(path.read_text(), f"---\ndataset: tiny\nversion: 1.0.0\nhub: brineylab/tiny\nbranch: candidate-{self.tree}\n"
                         f"commit: {'a' * 40}\ntree: {self.tree}\ntool: hello@1.0.1\nrunner: podman\nhost: laptop\n"
                         f"started: 2026-11-05T00:00:00Z\nexit: 0\n---\n{out}")
        self.assertEqual(check.parse_record(path)["files"], [("train.txt", 18, "c" * 64)])
        r = self.run_script("record", "tiny", "b" * 40, "0", "podman", "laptop", "now", input="hf_" + "b" * 34)
        self.assertEqual(r.returncode, 1); self.assertIn("credential", r.stderr)
        self.assertIn("a" * 40, path.read_text())  # the refused output wrote nothing

    def test_record_refuses_a_commit_that_is_not_forty_hex_and_an_exit_that_is_not_a_number(self):
        self.assertEqual(self.run_script("record", "tiny", "main", "0", "podman", "h", "now", input="").returncode, 2)
        self.assertEqual(self.run_script("record", "tiny", "a" * 40, "ok", "podman", "h", "now", input="").returncode, 2)
        self.assertFalse((self.repo / "results").exists())

if __name__ == "__main__":
    unittest.main()
