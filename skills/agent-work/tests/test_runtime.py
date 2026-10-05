import errno
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

from support import run_workspace, set_owner
import process_runtime as runtime


class HeldProcess:
    def __init__(self):
        self.pid = 987654
        self.killed = False

    def poll(self):
        return None if not self.killed else -signal.SIGKILL

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return -signal.SIGKILL


class SignalRaceTests(unittest.TestCase):
    def attempt(self, survivors):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'process.json'
            set_owner('signal-race')
            record = {'owner': runtime.owner(), 'lease': 'generation', 'identity': 'identity',
                      'pid': 987654, 'start': 'observed birth', 'status': 'active',
                      'resources': [{'status': 'active'}]}
            runtime.atomic_json(path, record)
            with patch.object(runtime, 'members', side_effect=[[record['pid']], survivors, survivors]), \
                    patch.object(runtime, 'verified', return_value=True), \
                    patch.object(runtime.os, 'killpg', side_effect=PermissionError(errno.EPERM, 'denied')):
                if survivors:
                    with self.assertRaises(PermissionError):
                        runtime.stop(path, lease='generation')
                    self.assertEqual('active', json.loads(path.read_text())['status'])
                else:
                    runtime.stop(path, lease='generation')
                    self.assertEqual('released', json.loads(path.read_text())['status'])

    def test_naturally_finished_group_after_verification_is_closed(self):
        self.attempt([])

    def test_denied_signal_with_survivors_preserves_the_claim(self):
        self.attempt([987654])

    def test_cancel_before_publication_releases_journal_before_stopping_held_process(self):
        with run_workspace('runtime-publication-cancel') as parent:
            path = parent / 'process.json'
            held = HeldProcess()
            set_owner('publication-race')
            with patch.object(runtime.subprocess, 'Popen', return_value=held), \
                    patch.object(runtime.time, 'sleep', side_effect=KeyboardInterrupt('cancelled')):
                with self.assertRaises(KeyboardInterrupt):
                    runtime.launch(path, [sys.executable, '-c', 'raise SystemExit(99)'], parent,
                                   lease='generation')
            record = json.loads(path.read_text())
            self.assertEqual('released', record['status'])
            self.assertEqual('released', record['resources'][0]['status'])
            self.assertNotIn('pid', record)
            self.assertTrue(held.killed)
            self.assertNotIn(held.pid, runtime._HANDLES)
            previous = signal.getsignal(signal.SIGTERM)
            try:
                with patch.object(runtime.subprocess, 'Popen') as child:
                    self.assertEqual(1, runtime.supervise(record['identity'], path,
                                                          [sys.executable, '-c', 'pass']))
                    child.assert_not_called()
            finally:
                signal.signal(signal.SIGTERM, previous)
