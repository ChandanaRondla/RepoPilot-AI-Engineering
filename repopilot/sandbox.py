"""Container-isolated pytest runner. Requires installed Docker and a local image.

Docker isolation is defense-in-depth, not a perfect security boundary. Do not run
untrusted repositories on sensitive hosts; prefer disposable CI VMs.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import re

_IMAGE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9_./:@-]{0,127}$')

def run_isolated_pytest(root: Path, *, image: str = 'python:3.12-slim',
                        timeout: int = 90, target: str = 'tests') -> dict:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError('Root must be a directory')
    path = (root / target).resolve()
    if not path.is_relative_to(root) or not path.exists():
        raise ValueError('Target must exist within repository')
    if not _IMAGE.fullmatch(image) or not 1 <= timeout <= 600:
        raise ValueError('Invalid image or timeout')
    cmd = ['docker', 'run', '--rm', '--network', 'none', '--read-only',
           '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges',
           '--pids-limit', '128', '--memory', '512m', '--cpus', '1',
           '--tmpfs', '/tmp:rw,noexec,nosuid,size=64m',
           '--mount', f'type=bind,src={root},dst=/workspace,readonly',
           '-w', '/workspace', image, 'python', '-m', 'pytest', '-q',
           str(path.relative_to(root))]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return {'passed': p.returncode == 0, 'exit_code': p.returncode,
                'stdout': p.stdout[-12000:], 'stderr': p.stderr[-6000:]}
    except FileNotFoundError:
        return {'passed': False, 'exit_code': None, 'error': 'Docker unavailable'}
    except subprocess.TimeoutExpired:
        return {'passed': False, 'exit_code': None, 'error': 'Timeout'}
