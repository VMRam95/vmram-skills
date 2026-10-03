#!/usr/bin/env python3
"""Link a single canonical skill for installed clients; never replace foreign files."""
import argparse
from pathlib import Path
import os

CLIENTS = ['.agents/skills','.codex/skills','.claude/skills','.config/devin/skills',
           '.config/opencode/skills','.cursor/skills','.gemini/skills','.copilot/skills']


def install(home, source, apply=False):
    source=Path(source).resolve(strict=True)
    if not (source/'SKILL.md').is_file():raise RuntimeError('Canonical skill source is missing')
    changes=[]
    for client in CLIENTS:
        parent=home/client
        if not parent.is_dir():continue
        target=parent/'agent-work'
        if target.is_symlink() and target.resolve()==source:continue
        if target.exists() or target.is_symlink():
            raise RuntimeError(f'Foreign installed skill preserved: {target}')
        changes.append(target)
    binary=home/'.local/bin/agent-work'
    if binary.exists() or binary.is_symlink():
        if not binary.is_symlink() or binary.resolve()!=source/'scripts/agent-work':
            raise RuntimeError(f'Foreign command preserved: {binary}')
    else:changes.append(binary)
    for target in changes:
        print(('LINK ' if apply else 'PLAN ')+str(target))
        if apply:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.symlink_to(source/'scripts/agent-work' if target==binary else source)
    return changes


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply',action='store_true')
    parser.add_argument('--home',type=Path,default=Path.home())
    args=parser.parse_args()
    try:install(args.home,Path(__file__).resolve().parents[1],args.apply)
    except (OSError,RuntimeError) as exc:parser.exit(1,str(exc)+'\n')
