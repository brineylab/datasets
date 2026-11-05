import unittest, tempfile, shutil, subprocess
from pathlib import Path
from helpers import ROOT, git

class ChangedDatasetsTests(unittest.TestCase):
    def test_names_each_changed_dataset_once_and_skips_a_removed_one(self):
        repo = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, repo)
        (repo / "scripts").mkdir(); shutil.copy(ROOT / "scripts" / "changed-datasets", repo / "scripts")
        for d in ("a", "b", "gone"):
            (repo / "datasets" / d).mkdir(parents=True); (repo / "datasets" / d / "SKILL.md").write_text(d)
        git(repo, "init", "-q"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "1")
        (repo / "datasets/a/SKILL.md").write_text("a2"); (repo / "datasets/a/x").write_text("x")
        shutil.rmtree(repo / "datasets/gone"); (repo / "README.md").write_text("r")
        git(repo, "add", "-A"); git(repo, "commit", "-qm", "2")
        r = subprocess.run(["bash", str(repo / "scripts/changed-datasets"), "HEAD~1", "HEAD"], capture_output=True, text=True, check=True)
        self.assertEqual(r.stdout, "a\n")

if __name__ == "__main__":
    unittest.main()
