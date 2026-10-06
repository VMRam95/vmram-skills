"""Interrupting only the wait for capacity keeps a prepared stack (real CLI, fixture profile)."""
import json, os, signal, subprocess, sys, tempfile, time, unittest
from pathlib import Path

from support import SCRIPTS, init_git_fixture, profile


class QueuedInterruptTests(unittest.TestCase):
    def test_sigint_while_validate_waits_keeps_the_job(self):
        cli = [sys.executable, "-B", str(SCRIPTS / "agent_work.py")]
        env = dict(os.environ, AGENT_LOCAL_OWNER="queued-interrupt")
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw).resolve()
            root = init_git_fixture(parent)
            profile_path, data = profile(root)
            data["budgets"]["test"] = {"ram_gb": 100000, "cpu_cores": 1}  # never admitted
            profile_path.write_text(json.dumps(data))
            state = parent / "state"
            started = subprocess.run(cli + ["start", "--profile", str(profile_path), "--root", str(root),
                                            "--task", "queued-interrupt", "--state-dir", str(state),
                                            "--wait", "120"], capture_output=True, text=True, env=env)
            self.assertEqual(0, started.returncode, started.stderr)
            job = json.loads(started.stdout[started.stdout.index("{"):])["id"]
            waiting = subprocess.Popen(cli + ["validate", "--job", job, "--state-dir", str(state), "--wait", "120"],
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
            journal = state / "jobs" / job / "job.json"
            deadline = time.monotonic() + 60
            while json.loads(journal.read_text())["state"] != "queued" and time.monotonic() < deadline:
                time.sleep(0.5)
            waiting.send_signal(signal.SIGINT)
            waiting.communicate(timeout=120)
            current = json.loads(journal.read_text())
            self.assertEqual("queued", current["state"])
            self.assertTrue(current["adapter"]["prepared"])
            resumed = subprocess.run(cli + ["exec", "--job", job, "--state-dir", str(state), "--budget", "up",
                                            "--wait", "60", "--", "true"], capture_output=True, text=True, env=env)
            self.assertEqual(0, resumed.returncode, resumed.stderr)
            closed = subprocess.run(cli + ["close", "--job", job, "--state-dir", str(state)],
                                    capture_output=True, text=True, env=env)
            self.assertEqual(0, closed.returncode, closed.stderr)


if __name__ == "__main__":
    unittest.main()
