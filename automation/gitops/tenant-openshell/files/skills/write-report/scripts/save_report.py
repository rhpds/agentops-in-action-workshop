#!/usr/bin/env python3
"""Save stdin as a new timestamped Markdown report, without overwriting files."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


def save_report(content, title, directory=Path('/reports')):
    if not content.strip():
        raise ValueError('Report content must not be empty')
    directory.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')[:80] or 'report'
    while True:
        stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S-%fZ')
        path = directory / f'{stamp}_{slug}.md'
        try:
            with path.open('x', encoding='utf-8') as report:
                report.write(content)
                if not content.endswith('\n'):
                    report.write('\n')
            return path
        except FileExistsError:
            continue


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--title', default='report')
    args = parser.parse_args()
    try:
        print(save_report(sys.stdin.read(), args.title))
    except (OSError, ValueError) as error:
        print(f'Could not save report: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
