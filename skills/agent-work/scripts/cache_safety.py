"""Admission checks for exact project-allowlisted caches; no resource discovery/GC."""
import os
from pathlib import Path
import subprocess


def within(path, root):
    return path == root or root in path.parents


def safe_cache(root, relative):
    root = Path(root)
    path = root / relative
    if not within(path, root) or path == root or path.resolve() != path or any(p.is_symlink() for p in (path, *path.parents)):
        return 'linked or outside cache'
    if not path.exists():
        return 'absent'
    if path.is_mount():
        return 'mount'
    if path.is_dir():
        for base, dirs, files in os.walk(path, followlinks=False):
            for name in dirs + files:
                child = Path(base) / name
                # pnpm links to this worktree's packages; rmtree unlinks them,
                # preserving their targets. Links outside this worktree stay protected.
                if child.is_mount() or name == '.git' or (child.is_symlink() and not within(child.resolve(), root)):
                    return 'shared symlink, mount or nested repository'
    command = ['git', '-C', str(root)]
    files = subprocess.run([*command, 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '--', str(relative)],
                           capture_output=True, text=True, timeout=30, check=True).stdout
    if files:
        return 'tracked or non-ignored files'
    ignored = subprocess.run([*command, 'check-ignore', '-q', '--', str(relative)], capture_output=True, timeout=10)
    if ignored.returncode not in (0, 1):
        raise RuntimeError('Cannot establish Git ignore policy')
    if ignored.returncode != 0:
        return 'not explicitly ignored'
    return ''
