import tempfile
from pathlib import Path
import unittest

from install_agent_work import install


class InstallationTests(unittest.TestCase):
    def test_one_source_is_linked_for_installed_clients_and_command(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw).resolve()
            source = home / 'source/agent-work'
            source.mkdir(parents=True)
            (source / 'SKILL.md').write_text('canonical')
            for client in ('.codex/skills', '.claude/skills'):
                (home / client).mkdir(parents=True)
            planned = install(home, source)
            self.assertEqual(3, len(planned))
            self.assertFalse(any(path.exists() for path in planned))
            install(home, source, True)
            self.assertEqual(source, (home / '.codex/skills/agent-work').resolve())
            self.assertEqual(source, (home / '.claude/skills/agent-work').resolve())
            self.assertEqual(source / 'scripts/agent-work', (home / '.local/bin/agent-work').resolve())
            self.assertEqual([], install(home, source, True))

    def test_foreign_skill_or_command_prevents_all_installation_writes(self):
        for foreign in ('.claude/skills/agent-work', '.local/bin/agent-work'):
            with self.subTest(path=foreign), tempfile.TemporaryDirectory() as raw:
                home = Path(raw).resolve()
                source = home / 'source/agent-work'; source.mkdir(parents=True)
                (source / 'SKILL.md').write_text('canonical')
                for client in ('.codex/skills', '.claude/skills'):
                    (home / client).mkdir(parents=True)
                path = home / foreign; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('foreign')
                with self.assertRaisesRegex(RuntimeError, 'Foreign'):
                    install(home, source, True)
                self.assertEqual('foreign', path.read_text())
                self.assertFalse((home / '.codex/skills/agent-work').exists())

    def test_managed_monitor_keeps_existing_auxiliary_files(self):
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw).resolve()
            source = home / 'source/agent-watch'; source.mkdir(parents=True)
            (source / 'SKILL.md').write_text('canonical')
            (source / 'scripts').mkdir()
            legacy = home / '.claude/skills/agent-watch'
            (legacy / 'scripts').mkdir(parents=True)
            for name in ('SKILL.md', 'scripts/mac_agent_capacity.py', 'scripts/agent-watch.30s.py'):
                if name != 'SKILL.md': (source / name).write_text('canonical')
                (legacy / name).symlink_to(source / name)
            (legacy / 'raycast').mkdir()
            sentinel = legacy / 'raycast/shortcut.sh'; sentinel.write_text('keep')
            (home / '.codex/skills').mkdir(parents=True)
            install(home, source, True)
            self.assertEqual(source, (home / '.codex/skills/agent-watch').resolve())
            self.assertEqual('keep', sentinel.read_text())
            self.assertFalse((home / '.local/bin/agent-work').exists())
            self.assertEqual([], install(home, source, True))


if __name__ == '__main__':
    unittest.main()
