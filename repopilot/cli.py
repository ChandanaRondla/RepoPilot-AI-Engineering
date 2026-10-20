import argparse
import json
from pathlib import Path
from .core import analyze, diff_from_git, retrieve
from .llm import review_with_llm
from .workflow import run_review, ReviewPolicy
from .quality import evaluate
from .test_runner import run_pytest


def main():
    parser = argparse.ArgumentParser(description='RepoPilot repository-aware PR assistant')
    parser.add_argument('--repo', default='.', help='Local repository path')
    sub = parser.add_subparsers(dest='command', required=True)
    search = sub.add_parser('search', help='Find relevant repository context')
    search.add_argument('question')
    search.add_argument('--limit', type=int, default=5)
    review = sub.add_parser('review', help='Review a unified diff and propose tests')
    review.add_argument('--diff-file', help='Unified diff file (otherwise git diff from base)')
    review.add_argument('--base', default='HEAD', help='Git diff base revision')
    review.add_argument('--output', help='Optional JSON report output')
    review.add_argument('--llm', action='store_true', help='Request optional model-assisted review (requires OPENAI_API_KEY)')
    review.add_argument('--model', default='gpt-4o-mini', help='OpenAI-compatible model ID')
    gate = sub.add_parser('gate', help='Apply a deterministic policy gate and human approval requirement')
    gate.add_argument('--diff-file', required=True)
    gate.add_argument('--block-at', choices=['low','medium','high','critical'], default='high')
    gate.add_argument('--no-approval', action='store_true')
    bench = sub.add_parser('evaluate', help='Evaluate labeled review cases in a JSON file')
    bench.add_argument('cases_file')
    test = sub.add_parser('test', help='Run pytest on a trusted repository (not sandboxed)')
    test.add_argument('--trusted', action='store_true', required=True)
    test.add_argument('--timeout', type=int, default=60)
    test.add_argument('--target', default='tests')
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    if args.command == 'search':
        result = retrieve(root, args.question, args.limit)
    elif args.command == 'evaluate':
        result = evaluate(json.loads(Path(args.cases_file).read_text(encoding='utf-8')))
    elif args.command == 'test':
        result = run_pytest(root, trusted=args.trusted, timeout=args.timeout, target=args.target)
    elif args.command == 'gate':
        diff = Path(args.diff_file).read_text(encoding='utf-8')
        result = run_review(root, diff, ReviewPolicy(block_at=args.block_at, require_approval=not args.no_approval))
    else:
        diff = Path(args.diff_file).read_text(encoding='utf-8') if args.diff_file else diff_from_git(root, args.base)
        result = analyze(root, diff)
        if args.llm:
            result['model_review'] = review_with_llm(diff, result['context'], model=args.model)
        if args.output:
            Path(args.output).write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
