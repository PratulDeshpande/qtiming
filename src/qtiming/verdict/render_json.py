"""JSON rendering (plan 13.2 plus a `counterexamples` array)."""

from __future__ import annotations

import json
from fractions import Fraction

from .model import Verdict, to_dict


def render_json(v: Verdict, dt_ns: Fraction) -> str:
    return json.dumps(to_dict(v, dt_ns), indent=2)
