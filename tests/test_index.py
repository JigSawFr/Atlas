"""tools/index.py: each data file listed with its day, size and hash, the
index itself left out, nothing that changes when the files do not."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import index  # noqa: E402


class Index(unittest.TestCase):
    def test_index(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "prices"))
            os.makedirs(os.path.join(d, ".git"))
            for path, body in (("popular.json", '{"schema":1,"generated":"2026-10-29","games":{}}'),
                               ("prices/FR.json", '{"schema":1,"generated":"2026-10-30","games":{}}'),
                               ("index.json", "{}"), ("notes.txt", "x"), (".git/x.json", "{}")):
                with open(os.path.join(d, path), "w") as f:
                    f.write(body)
            got = index.index(d)
            self.assertEqual(sorted(got["files"]), ["popular.json", "prices/FR.json"])
            self.assertEqual(got["files"]["prices/FR.json"]["generated"], "2026-10-30")
            self.assertEqual(got["files"]["popular.json"]["bytes"], 48)
            self.assertEqual(len(got["files"]["popular.json"]["sha256"]), 16)
            # The same files, the same index.
            self.assertEqual(json.dumps(index.index(d)), json.dumps(got))


if __name__ == "__main__":
    unittest.main()
