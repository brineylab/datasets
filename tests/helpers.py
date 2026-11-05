import contextlib, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
TINY = FIXTURES / "datasets" / "tiny"
sys.path.insert(0, str(ROOT / "scripts"))

def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                          check=True, capture_output=True, text=True).stdout

@contextlib.contextmanager
def copy_of(fixture):
    """A copy of a fixture directory, under a temporary directory and with the fixture's name, removed afterwards."""
    tmp = Path(tempfile.mkdtemp())
    try:
        yield Path(shutil.copytree(fixture, tmp / fixture.name))
    finally:
        shutil.rmtree(tmp)
