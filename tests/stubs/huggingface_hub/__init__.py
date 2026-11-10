"""A stand-in for huggingface_hub: an HfApi whose Hub is a JSON file, $FAKE_HUB, so a test reads what a script did.

The state: repos, branches (name to commit), tags (name to commit), files (path to text, the card's),
uploaded (the paths upload_folder sent), trees (commit to {path: blob id}; a commit it lacks holds nothing), and calls, in order.
"""
import fnmatch, hashlib, json, os, uuid
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

class RepoFile:
    def __init__(self, path, blob_id): self.path, self.blob_id = path, blob_id

class CommitOperationDelete:
    def __init__(self, path_in_repo): self.path_in_repo = path_in_repo

class CommitOperationCopy:
    def __init__(self, src_path_in_repo, path_in_repo, src_revision=None):
        self.src_path_in_repo, self.path_in_repo, self.src_revision = src_path_in_repo, path_in_repo, src_revision

def _commit(s, branch, tree):
    s["branches"][branch] = oid = uuid.uuid4().hex + "0" * 8
    s["trees"][oid] = tree
    return CommitInfo(oid)

def _tree(s, rev):
    return dict(s["trees"].get(s["branches"].get(rev) or s["tags"].get(rev) or rev, {}))

class HfApi:
    def __init__(self, token=None):
        self.token, self.path = token, Path(os.environ["FAKE_HUB"])

    def _change(self, call, f=None):
        s = json.loads(self.path.read_text()) if self.path.exists() else {}
        for k in ("repos", "calls", "uploaded"): s.setdefault(k, [])
        for k in ("branches", "tags", "files", "trees"): s.setdefault(k, {})
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

    def upload_folder(self, *, repo_id, folder_path, revision=None, ignore_patterns=None, delete_patterns=None, **kw):
        def f(s):
            root = Path(folder_path)
            paths = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
            s["uploaded"] = [p for p in paths if not any(fnmatch.fnmatch(p, pat) for pat in ignore_patterns or [])]
            tree = {p: b for p, b in _tree(s, revision).items()  # as the Hub's: .gitattributes is never deleted
                    if p == ".gitattributes" or not any(fnmatch.fnmatch(p, pat) for pat in delete_patterns or [])}
            tree.update({p: hashlib.sha1((root / p).read_bytes()).hexdigest() for p in s["uploaded"]})
            return _commit(s, revision, tree)
        return self._change(["upload_folder", revision], f)

    def upload_file(self, *, path_or_fileobj, path_in_repo, repo_id, revision=None, **kw):
        def f(s):
            s["files"][path_in_repo] = text = path_or_fileobj.decode() if isinstance(path_or_fileobj, bytes) else Path(path_or_fileobj).read_text()
            return _commit(s, revision, {**_tree(s, revision), path_in_repo: hashlib.sha1(text.encode()).hexdigest()})
        return self._change(["upload_file", path_in_repo], f)

    def list_repo_refs(self, repo_id, *, repo_type=None, **kw):
        return self._change(["list_repo_refs", repo_id], lambda s: GitRefs(s["branches"], s["tags"]))

    def create_tag(self, repo_id, *, tag, revision=None, repo_type=None, **kw):
        def f(s):
            if tag in s["tags"]:
                raise HfHubHTTPError(f"409 Conflict: tag {tag} already exists", response=Response(409))
            s["tags"][tag] = revision
        self._change(["create_tag", tag], f)

    def list_repo_tree(self, repo_id, *, revision=None, recursive=False, repo_type=None, **kw):
        return self._change(["list_repo_tree", revision], lambda s: [RepoFile(p, b) for p, b in sorted(_tree(s, revision).items())])

    def create_commit(self, repo_id, operations, *, commit_message, revision=None, parent_commit=None, repo_type=None, **kw):
        def f(s):
            if parent_commit and s["branches"].get(revision) != parent_commit:
                raise HfHubHTTPError(f"412 Precondition Failed: {revision} is not at {parent_commit}", response=Response(412))
            tree = _tree(s, revision)
            for op in operations:
                if isinstance(op, CommitOperationDelete):
                    del tree[op.path_in_repo]
                else:
                    tree[op.path_in_repo] = _tree(s, op.src_revision)[op.src_path_in_repo]
            return _commit(s, revision, tree)
        return self._change(["create_commit", revision], f)
