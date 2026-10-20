"""Dependency-free repository context retrieval and deterministic PR risk checks."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import ast
import difflib
import json
import re
import subprocess
from typing import Any

IGNORED = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '.pytest_cache', 'dist', 'build'}
ALLOWED = {'.py', '.js', '.jsx', '.ts', '.tsx', '.md', '.json', '.yaml', '.yml', '.toml'}
MAX_BYTES = 150_000

@dataclass
class Finding:
    severity: str
    rule: str
    path: str
    line: int
    message: str
    suggestion: str
    source: str = 'deterministic'

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def safe_files(root: Path) -> list[Path]:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError('Repository root must be an existing directory')
    found = []
    for path in root.rglob('*'):
        if any(p in IGNORED for p in path.relative_to(root).parts):
            continue
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in ALLOWED:
            continue
        if path.stat().st_size > MAX_BYTES:
            continue
        found.append(path)
    return sorted(found)


def chunks(root: Path) -> list[dict[str, Any]]:
    results = []
    for path in safe_files(root):
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
        for start in range(0, len(lines), 60):
            content = '\n'.join(lines[start:start+60])
            if content.strip():
                results.append({'path': str(path.relative_to(root)), 'start_line': start+1, 'end_line': min(start+60, len(lines)), 'content': content})
    return results


def retrieve(root: Path, question: str, limit: int = 5) -> list[dict[str, Any]]:
    """Transparent lexical ranking; no unsupported semantic-retrieval claims."""
    tokens = set(re.findall(r'[a-zA-Z_][a-zA-Z_0-9]{2,}', question.lower()))
    if not tokens:
        return []
    ranked = []
    for chunk in chunks(root):
        content = chunk['content'].lower()
        path = chunk['path'].lower()
        score = sum(min(content.count(token), 5) + (4 if token in path else 0) for token in tokens)
        if score:
            ranked.append((score, chunk))
    ranked.sort(key=lambda item: (-item[0], item[1]['path'], item[1]['start_line']))
    return [dict(item, score=score) for score, item in ranked[:max(0, limit)]]


def diff_from_git(root: Path, base: str = 'HEAD') -> str:
    """Use git arguments, not shell; base is restricted to safe ref characters."""
    if not re.fullmatch(r'[a-zA-Z0-9_./~^{}-]+', base) or base.startswith('-'):
        raise ValueError('Invalid git base ref')
    cmd = ['git', '-C', str(root.resolve()), 'diff', '--no-ext-diff', '--unified=3', base, '--']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)
    if proc.returncode:
        raise RuntimeError(proc.stderr.strip() or 'git diff failed')
    return proc.stdout


def parse_added_lines(diff: str) -> list[tuple[str, int, str]]:
    path = ''
    line = 0
    result = []
    for raw in diff.splitlines():
        if raw.startswith('+++ b/'):
            path = raw[6:]
        elif raw.startswith('+++ /dev/null'):
            path = ''
        elif raw.startswith('@@'):
            match = re.search(r'\+(\d+)', raw)
            if match:
                line = int(match.group(1))
        elif raw.startswith('+') and not raw.startswith('+++'):
            if path:
                result.append((path, line, raw[1:]))
            line += 1
        elif raw.startswith(' ') and not raw.startswith('+++'):
            line += 1
    return result


def _python_code_lines(path: str, content: str) -> bool:
    """Only inspect executable Python tokens, excluding comments and strings."""
    import io, tokenize
    try:
        tokens = tokenize.generate_tokens(io.StringIO(content + "\n").readline)
        return any(t.type not in (tokenize.COMMENT, tokenize.STRING, tokenize.NL,
                   tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                   tokenize.ENDMARKER, tokenize.ENCODING) for t in tokens)
    except (tokenize.TokenError, IndentationError):
        return not content.lstrip().startswith('#')


def review_diff(diff: str) -> list[Finding]:
    """Review added code; avoid comment/string false alarms and safe subprocess calls."""
    import io, tokenize
    findings: list[Finding] = []
    seen = set()
    for path, line, content in parse_added_lines(diff):
        if not path.endswith('.py') or not _python_code_lines(path, content):
            continue
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(content + '\n').readline))
            code = ''.join(t.string if t.type not in (tokenize.STRING, tokenize.COMMENT) else ' ' * len(t.string) for t in tokens if t.type not in (tokenize.ENDMARKER, tokenize.ENCODING))
        except (tokenize.TokenError, IndentationError):
            code = content.split('#', 1)[0]
        checks = []
        if re.search(r'\b(?:api_key|secret_key|access_token|password)\s*[:=]\s*[\"\'][^\"\']{8,}[\"\']', content, re.I) and not content.lstrip().startswith('#'):
            checks.append(('high','hardcoded-secret','Potential hardcoded credential','Load secrets from a secret manager'))
        if re.search(r'\beval\s*\(', code):
            checks.append(('high','unsafe-eval','Use of eval can execute untrusted code','Use a restricted parser'))
        if re.search(r'\b(?:os\.system|subprocess\.(?:run|Popen|call))\s*\(', code) and not re.search(r'\bshell\s*=\s*False\b', code):
            checks.append(('medium','shell-execution','Review subprocess input handling','Avoid shell=True and validate inputs'))
        if re.match(r'^\s*except\s*:', code):
            checks.append(('medium','unbounded-except','Bare except hides unexpected failures','Catch specific exceptions'))
        if re.search(r'\bprint\s*\(', code):
            checks.append(('low','debug-print','Debug print added to application code','Use structured logging'))
        for severity, rule, message, suggestion in checks:
            if (path,line,rule) not in seen:
                findings.append(Finding(severity,rule,path,line,message,suggestion))
                seen.add((path,line,rule))
    return findings


def changed_python_functions(diff: str) -> list[tuple[str, str]]:
    """Detect newly added function declarations for candidate tests."""
    results = []
    seen = set()
    for path, _, content in parse_added_lines(diff):
        if path.endswith('.py'):
            match = re.match(r'\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(', content)
            if match and not match.group(1).startswith('test_'):
                key = (path, match.group(1))
                if key not in seen:
                    seen.add(key)
                    results.append(key)
    return results


def _literal_return_test(source: str, function: str) -> tuple[str, str] | None:
    """Derive an assertion only for a zero-argument pure function returning a literal."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != function:
            continue
        if node.args.args or node.args.kwonlyargs or node.args.vararg or node.args.kwarg or node.decorator_list:
            continue
        if len(node.body) != 1 or not isinstance(node.body[0], ast.Return):
            continue
        try:
            value = ast.literal_eval(node.body[0].value)
        except (ValueError, TypeError, SyntaxError, MemoryError):
            continue
        if isinstance(value, (str, int, float, bool, type(None), tuple, list, dict)) and len(repr(value)) < 200:
            return (f'assert {function}() == {repr(value)}', 'executable_literal')
    return None


def test_proposals(root: Path, diff: str) -> list[dict[str, Any]]:
    """Generate real assertions only when derivable from checked-in source; otherwise skip."""
    proposals = []
    for path, func in changed_python_functions(diff):
        module = path.removesuffix('.py').replace('/', '.')
        if not all(part.isidentifier() for part in module.split('.')):
            continue
        source_file = (root / path).resolve()
        try:
            if not source_file.is_relative_to(root.resolve()) or source_file.is_symlink() or source_file.stat().st_size > MAX_BYTES:
                continue
            source = source_file.read_text(encoding='utf-8')
        except (OSError, UnicodeError):
            source = ''
        derived = _literal_return_test(source, func)
        if derived:
            assertion, kind = derived
            body = f'def test_{func}_literal_return():\n    {assertion}\n'
        else:
            kind = 'review_required'
            body = f'def test_{func}_requires_contract():\n    pytest.skip("Expected behavior requires developer review")\n'
        proposals.append({
            'source_path': path, 'function': func,
            'suggested_file': f'tests/test_{Path(path).stem}_{func}.py',
            'kind': kind,
            'content': f'"""Generated by RepoPilot. Review before merging."""\nimport pytest\nfrom {module} import {func}\n\n\n{body}'
        })
    return proposals


def analyze(root: Path, diff: str) -> dict[str, Any]:
    findings = review_diff(diff)
    changed = sorted({p for p, _, _ in parse_added_lines(diff)})
    context = []
    for path in changed[:5]:
        context.extend(retrieve(root, Path(path).stem, limit=2))
    dedup = {(c['path'], c['start_line']): c for c in context}
    return {
        'changed_files': changed,
        'findings': [f.as_dict() for f in findings],
        'test_proposals': test_proposals(root, diff),
        'context': list(dedup.values())[:8],
        'summary': {'changed_files': len(changed), 'findings': len(findings), 'proposed_test_files': len(test_proposals(root, diff))},
        'disclaimer': 'Static heuristics are advisory. Literal-return tests have executable assertions; other proposals require developer review.'
    }
