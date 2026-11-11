"""Strict standalone CLI for the separate DFA conditioning API."""
import argparse
import json
import re
import sys
from .audit import loads, MAX_BYTES
from .automaton import automaton_report


def strict_loads(text):
    # Reuse the existing bounded duplicate/depth guard, then enforce the new
    # exact interface's lexical integer contract before any JSON number is used.
    loads(text)
    def integer(token):
        if re.fullmatch(r'0|[1-9][0-9]*', token) is None:
            raise ValueError('only nonnegative integer JSON number tokens are allowed')
        return int(token)
    def bad(token):
        raise ValueError('floating-point JSON number tokens are not allowed')
    return json.loads(text, parse_int=integer, parse_float=bad, parse_constant=bad)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--input', required=True)
    args = p.parse_args(argv)
    try:
        if args.input == '-':
            text = sys.stdin.read(MAX_BYTES + 1)
        else:
            with open(args.input, encoding='utf8') as f:
                text = f.read(MAX_BYTES + 1)
        out = automaton_report(strict_loads(text))
        print(json.dumps(out, allow_nan=False, separators=(',', ':')))
    except (ValueError, TypeError, KeyError, OSError, OverflowError, RecursionError) as e:
        print('automaton error: ' + str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
