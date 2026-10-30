"""tools/alert.sh: what it says, and when nothing (gh replaced by a script
that keeps what it was asked)."""
import os
import subprocess
import tempfile
import unittest

ALERT = os.path.join(os.path.dirname(__file__), "..", "tools", "alert.sh")


def run(outcomes="", job="success", alerts=""):
    """(stdout, the gh commands asked, one a line) of alert.sh."""
    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "gh.log")
        gh = os.path.join(tmp, "gh")
        with open(gh, "w") as f:
            f.write(f'#!/bin/bash\nprintf "%s\\n" "$*" >> "{log}"\n')
        os.chmod(gh, 0o755)
        alerts_file = os.path.join(tmp, "alerts.md")
        with open(alerts_file, "w") as f:
            f.write(alerts)
        env = {**os.environ, "PATH": tmp + os.pathsep + os.environ["PATH"], "OUTCOMES": outcomes,
               "JOB_STATUS": job, "ALERTS": alerts_file, "GITHUB_SERVER_URL": "https://example.org",
               "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "1"}
        out = subprocess.run(["bash", ALERT, "daily"], env=env, capture_output=True, text=True, check=True).stdout
        asked = open(log).read() if os.path.exists(log) else ""
    return out, asked


class Alert(unittest.TestCase):
    def test_nothing_wrong(self):
        out, asked = run("sources=success steam=success gog=skipped")
        self.assertIn("nothing to say", out)
        self.assertEqual(asked, "")

    def test_failure(self):
        _, asked = run("sources=success steam=failure")
        self.assertIn("**steam** failed", asked)
        self.assertIn("issue create", asked)

    def test_cancelled_source(self):
        """A source's job that ran out of time (run 41057856336): an alert too."""
        _, asked = run("sources=cancelled trends=success")
        self.assertIn("**sources** was cancelled or ran out of time", asked)

    def test_job_and_alerts(self):
        _, asked = run(job="cancelled", alerts="**sources (steam-store-JP)** ended in **cancelled**\n")
        self.assertIn("The job ended in **cancelled**", asked)
        self.assertIn("steam-store-JP", asked)


if __name__ == "__main__":
    unittest.main()
