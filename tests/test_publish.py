"""The data's two branches (2026-11-10): `data` without sources/, which jsDelivr serves whole, and `sources`.
tools/data-branch.sh puts both in ./data-branch, tools/publish.sh sends each back to its own."""
import json
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org", "GIT_COMMITTER_NAME": "t",
       "GIT_COMMITTER_EMAIL": "t@example.org", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}
ENV.pop("GITHUB_REPOSITORY", None)       # no purge asked of jsDelivr from a test


def run(cwd, *command):
    return subprocess.run(command, cwd=cwd, env=ENV, check=True, capture_output=True, text=True).stdout


def put(directory, name, body):
    path = os.path.join(directory, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(body, f)


class Branches(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.origin = os.path.join(self.tmp.name, "origin.git")
        run(self.tmp.name, "git", "init", "-q", "--bare", "-b", "main", self.origin)
        seed = self.clone("seed")
        run(seed, "git", "commit", "-q", "--allow-empty", "-m", "main")
        run(seed, "git", "push", "-q", "origin", "HEAD:main")

    def tearDown(self):
        self.tmp.cleanup()

    def clone(self, name):
        """A checkout of main as a run's job has it, with this repository's tools."""
        path = os.path.join(self.tmp.name, name)
        run(self.tmp.name, "git", "clone", "-q", self.origin, path)
        os.symlink(os.path.join(ROOT, "tools"), os.path.join(path, "tools"))
        return path

    def files(self, branch):
        return set(run(self.origin, "git", "ls-tree", "-r", "--name-only", branch).split())

    def test_sources_leave_the_data_branch_and_come_back_to_the_tools(self):
        # As the branch was: everything on `data`.
        first = self.clone("first")
        run(first, "tools/data-branch.sh")
        data = os.path.join(first, "data-branch")
        put(data, "platforms/switch/popular.json", {"schema": 1, "generated": "2026-11-09", "games": {}})
        put(data, "sources/titledb/US.json", {"schema": 1, "generated": "2026-11-09", "source": "t", "license": "l", "games": {}})
        run(data, "git", "add", "-A")
        run(data, "git", "commit", "-q", "-m", "as it was")
        run(data, "git", "push", "-q", "origin", "HEAD:data")
        self.assertIn("sources/titledb/US.json", self.files("data"))

        # The first run after: sources/ goes to its branch, `data` keeps the rest and the index of both.
        job = self.clone("job")
        run(job, "tools/data-branch.sh")
        data = os.path.join(job, "data-branch")
        self.assertTrue(os.path.exists(os.path.join(data, "sources/titledb/US.json")))      # no `sources` branch yet: as it is
        put(data, "sources/wikipedia/daily.json", {"schema": 1, "generated": "2026-11-10", "source": "w", "license": "l", "pages": {}})
        run(job, "tools/publish.sh", "data-branch", "data: 2026-11-10")
        self.assertEqual(self.files("sources"), {"sources/titledb/US.json", "sources/wikipedia/daily.json"})
        self.assertEqual(self.files("data"), {"index.json", "platforms/switch/popular.json"})
        index = json.loads(run(self.origin, "git", "show", "data:index.json"))
        self.assertIn("sources/wikipedia/daily.json", index["files"])                       # the index lists every file, the sources' too
        self.assertEqual(run(self.origin, "git", "rev-list", "--count", "sources").strip(), "1")   # one commit, no history

        # The next run reads both, and a run that changes only a source leaves `data` as it is.
        nxt = self.clone("next")
        run(nxt, "tools/data-branch.sh")
        data = os.path.join(nxt, "data-branch")
        self.assertTrue(os.path.exists(os.path.join(data, "sources/wikipedia/daily.json")))
        self.assertTrue(os.path.exists(os.path.join(data, "platforms/switch/popular.json")))
        before = run(self.origin, "git", "rev-parse", "data").strip()
        os.remove(os.path.join(data, "sources/titledb/US.json"))                           # a source's file gone goes from its branch
        run(nxt, "tools/publish.sh", "data-branch", "data: 2026-11-11")
        self.assertEqual(self.files("sources"), {"sources/wikipedia/daily.json"})
        self.assertNotEqual(run(self.origin, "git", "rev-parse", "data").strip(), before)   # the index changed with it
        self.assertEqual(self.files("data"), {"index.json", "platforms/switch/popular.json"})

        # Nothing changed: nothing pushed, on either branch.
        again = self.clone("again")
        run(again, "tools/data-branch.sh")
        heads = run(self.origin, "git", "rev-parse", "data", "sources")
        self.assertIn("nothing changed", run(again, "tools/publish.sh", "data-branch", "data: 2026-11-12"))
        self.assertEqual(run(self.origin, "git", "rev-parse", "data", "sources"), heads)

    def test_a_wrong_source_is_put_back_from_its_branch(self):
        import sys
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import schemas
        job = self.clone("job")
        run(job, "tools/data-branch.sh")
        data = os.path.join(job, "data-branch")
        good = {"schema": 1, "generated": "2026-11-10", "source": "w", "license": "l", "pages": {}}
        put(data, "sources/wikipedia/daily.json", good)
        run(job, "tools/publish.sh", "data-branch", "data: 2026-11-10")
        put(data, "sources/wikipedia/daily.json", {"schema": 1})
        put(data, "sources/wikipedia/new.json", {"schema": 1})
        schemas.put_back(data, "sources/wikipedia/daily.json")
        schemas.put_back(data, "sources/wikipedia/new.json")
        with open(os.path.join(data, "sources/wikipedia/daily.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), good)                                            # as its branch had it
        self.assertFalse(os.path.exists(os.path.join(data, "sources/wikipedia/new.json")))  # new: removed


if __name__ == "__main__":
    unittest.main()
