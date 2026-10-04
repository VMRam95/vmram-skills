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
    skill=source.name
    if skill not in ('agent-work', 'agent-watch'):
        raise RuntimeError('Unsupported common skill')
    changes=[]
    for client in CLIENTS:
        parent=home/client
        if not parent.is_dir():continue
        target=parent/skill
        if target.is_symlink() and target.resolve()==source:continue
        if skill=='agent-watch' and target.is_dir() and not target.is_symlink():
            files=('SKILL.md','scripts/mac_agent_capacity.py','scripts/agent-watch.30s.py')
            if all((target/name).is_symlink() and (target/name).resolve()==(source/name).resolve()
                   for name in files):continue
        if target.exists() or target.is_symlink():
            raise RuntimeError(f'Foreign installed skill preserved: {target}')
        changes.append(target)
    binary=home/'.local/bin/agent-work'
    if skill=='agent-work':
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
    parser.add_argument('--skill',choices=('agent-work','agent-watch'),default='agent-work')
    args=parser.parse_args()
    try:install(args.home,Path(__file__).resolve().parents[2]/args.skill,args.apply)
    except (OSError,RuntimeError) as exc:parser.exit(1,str(exc)+'\n')
