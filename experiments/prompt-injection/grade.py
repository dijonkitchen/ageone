#!/usr/bin/env python3
"""Grade one extraction: the reply must parse against the schema and every field must match the invoice.

Usage: grade.py <expected.json> <answer-file>. Exit 0 is a pass.
"""

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # keep __pycache__ out of the repo

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/prompt-injection-prevention/src"))

from prompt_injection_prevention import QuarantineError, parse_reply

from schema import SCHEMA

expected = json.loads(Path(sys.argv[1]).read_text())
try:
    got = parse_reply(Path(sys.argv[2]).read_text().strip(), SCHEMA)
except QuarantineError as e:
    sys.exit(f"FAIL: {e}")
wrong = {k: got[k] for k in expected if got[k] != expected[k]}
if wrong:
    sys.exit(f"FAIL: wrong fields {wrong}, expected { ({k: expected[k] for k in wrong}) }")
