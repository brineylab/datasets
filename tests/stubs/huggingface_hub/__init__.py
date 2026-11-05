"""A stand-in for huggingface_hub: an HfApi whose Hub is a JSON file, $FAKE_HUB, so a test reads what a script did.

The state: repos, branches (name to commit), tags (name to commit), files (path to text, the card's),
uploaded (the paths upload_folder sent), and calls, in order.
"""
import fnmatch, json, os, uuid
from pathlib import Path
from huggingface_hub.errors import HfHubHTTPError

class Response:
    def __init__(self, status_code): self.status_code = status_code

class CommitInfo:
    def __init__(self, oid): self.oid = oid

class GitRefInfo:
    def __init__(self, name, ref, target_commit): self.name, self.ref, self.target_commit = name, ref, target_commit

class GitRefs:
    def __init__(self, branches, tags):
        self.branches = [GitRefInfo(n, f"refs/heads/{n}", c) for n, c in branches.items()]
        self.tags = [GitRefInfo(n, f"refs/tags/{n}", c) for n, c in tags.items()]

class HfApi:
    def __init__(self, token=None):
        self.token, self.path = token, Path(os.environ["FAKE_HUB"])

    def _change(self, call, f=None):
        s = json.loads(self.path.read_text()) if self.path.exists() else {}
        for k in ("repos", "calls", "uploaded"): s.setdefault(k, [])
        for k in ("branches", "tags", "files"): s.setdefault(k, {})
        s["calls"].append(call)
        try:
            return f(s) if f else None
        finally:  # a call that raised is still in calls, as it reached the Hub
            self.path.write_text(json.dumps(s))

    def create_repo(self, repo_id, *, repo_type=None, exist_ok=False, **kw):
        self._change(["create_repo", repo_id], lambda s: s["repos"].append(repo_id) if repo_id not in s["repos"] else None)

    def delete_branch(self, repo_id, *, branch, repo_type=None, **kw):
        def f(s):
            if branch not in s["branches"]:
                raise HfHubHTTPError(f"404 Revision Not Found: {branch}", response=Response(404))
            del s["branches"][branch]
        self._change(["delete_branch", branch], f)

    def create_branch(self, repo_id, *, branch, revision=None, repo_type=None, **kw):
        self._change(["create_branch", branch], lambda s: s["branches"].__setitem__(branch, s["branches"].get(revision or "main", "0" * 40)))

    def upload_folder(self, *, repo_id, folder_path, revision=None, ignore_patterns=None, **kw):
        def f(s):
            root = Path(folder_path)
            paths = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
            s["uploaded"] = [p for p in paths if not any(fnmatch.fnmatch(p, pat) for pat in ignore_patterns or [])]
            s["branches"][revision] = oid = uuid.uuid4().hex + "0" * 8
            return CommitInfo(oid)
        return self._change(["upload_folder", revision], f)

    def upload_file(self, *, path_or_fileobj, path_in_repo, repo_id, revision=None, **kw):
        def f(s):
            s["files"][path_in_repo] = path_or_fileobj.decode() if isinstance(path_or_fileobj, bytes) else Path(path_or_fileobj).read_text()
            s["branches"][revision] = oid = uuid.uuid4().hex + "0" * 8
            return CommitInfo(oid)
        return self._change(["upload_file", path_in_repo], f)

    def list_repo_refs(self, repo_id, *, repo_type=None, **kw):
        return self._change(["list_repo_refs", repo_id], lambda s: GitRefs(s["branches"], s["tags"]))

    def create_tag(self, repo_id, *, tag, revision=None, repo_type=None, **kw):
        def f(s):
            if tag in s["tags"]:
                raise HfHubHTTPError(f"409 Conflict: tag {tag} already exists", response=Response(409))
            s["tags"][tag] = revision
        self._change(["create_tag", tag], f)
