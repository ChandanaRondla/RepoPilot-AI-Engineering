"""Opt-in test execution with strict path and timeout checks.

WARNING: Executing tests runs repository code. Only use on trusted repositories
or in an externally sandboxed CI worker. This module is not a sandbox.
"""
from __future__ import annotations
from pathlib import Path
import subprocess
import sys
from typing import Any


def run_pytest(root: Path, *, timeout: int = 60, target: str = 'tests', trusted: bool = False) -> dict[str, Any]:
    if not trusted:
        raise PermissionError('Test execution requires trusted=True and a trusted or externally sandboxed repository')
    if not 1 <= timeout <= 600:
        raise ValueError('timeout must be between 1 and 600 seconds')
    root = root.resolve()
    if not root.is_dir():
        raise ValueError('Repository root does not exist')
    target_path = (root / target).resolve()
    if not target_path.is_relative_to(root) or not target_path.exists():
        raise ValueError('Test target must exist within repository')
    try:
        result = subprocess.run([sys.executable, '-m', 'pytest', '-q', str(target_path)],
                                cwd=root, capture_output=True, text=True, timeout=timeout, check=False)
        return {'exit_code': result.returncode, 'passed': result.returncode == 0,
                'stdout': result.stdout[-12000:], 'stderr': result.stderr[-6000:]}
    except subprocess.TimeoutExpired:
        return {'exit_code': None, 'passed': False, 'timed_out': True, 'stdout': '', 'stderr': 'Test execution timed out'}
