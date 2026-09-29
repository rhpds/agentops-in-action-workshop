#!/usr/bin/env python3
"""Render the adjacent Argo CD template; pipe stdout straight to oc apply."""
import getpass
import json
import os
from pathlib import Path
import re
import sys


def main():
    values = {key: os.environ.get(key, '') for key in (
        'PARTICIPANT', 'APPS_DOMAIN', 'MODEL_API_KEY', 'HERMES_API_SERVER_KEY'
    )}
    for key in ('PARTICIPANT', 'APPS_DOMAIN'):
        if not values[key]:
            sys.exit(f'Set {key} in the environment before rendering.')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]*[a-z0-9])?', values['PARTICIPANT']) or len(values['PARTICIPANT']) > 40:
        sys.exit('PARTICIPANT must be a lowercase DNS label, at most 40 characters.')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', values['APPS_DOMAIN']):
        sys.exit('APPS_DOMAIN must be a hostname without a scheme, port or path.')
    for key in ('MODEL_API_KEY', 'HERMES_API_SERVER_KEY'):
        if not values[key]:
            if not sys.stdin.isatty():
                sys.exit(f'Set {key}, or run with a terminal for a hidden prompt.')
            values[key] = getpass.getpass(f'{key}: ')
        if not values[key]:
            sys.exit(f'{key} cannot be empty.')
    source = Path(__file__).with_name('namespace-consolidation.yaml').read_text()
    # Every placeholder is inside a double-quoted YAML scalar. JSON escaping is
    # also valid there, including embedded quotes, backslashes and newlines.
    output = re.sub(r'\$\{([A-Z_]+)\}', lambda m: json.dumps(values[m[1]])[1:-1], source)
    sys.stdout.write(output)


if __name__ == '__main__':
    main()
