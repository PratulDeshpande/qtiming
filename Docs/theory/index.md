# Theory index

Statuses (exactly these words): `proved`, `proof-sketch`, `conjecture`, `tested-only`,
`reduced-statement`. Each theorem has a section `## T<n>` in [theorems.md](theorems.md) with a
`Status:` line that must equal the one below; `tests/unit/theory/test_theorem_index.py` enforces this
and that every theorem id cited under `src/` is listed here. Definitions: [definitions.md](definitions.md).
Other write-ups: [sc-derivation.md](sc-derivation.md), [T4-windowing.md](T4-windowing.md),
[dc-rules.md](dc-rules.md) (STNU DC rules, status UNVERIFIED, not a theorem).

| ID | File | Status | Backing tests | Cited in code |
| --- | --- | --- | --- | --- |
| T1 | theorems.md | proof-sketch | `tests/property/test_soundness.py`, `tests/property/test_tier_properties.py`, `tests/unit/solve/test_appendix_a.py`; known false-proof defect, see section | not cited |
| T2 | theorems.md | proof-sketch | `tests/unit/solve/test_smt.py`, `tests/property/test_vertex_lemma.py` | `src/qtiming/solve/smt.py` |
| T3 | theorems.md | proof-sketch | none direct; false for QUA as written | not cited |
| T4 | theorems.md (argument in T4-windowing.md) | proof-sketch | `tests/differential/test_window_vs_whole.py`, `tests/unit/graph/test_window.py` | `src/qtiming/graph/window.py` |
| T5 | theorems.md | reduced-statement | `tests/unit/solve/synth/test_synth_relax.py` (5 cases, 2-node chain) | `src/qtiming/solve/synth/rigid.py` |
| T6 | theorems.md | reduced-statement | `tests/unit/solve/synth/test_synth_relax.py` (4 cases) | `src/qtiming/solve/synth/relax.py` |
| T7 | theorems.md | conjecture | none | not cited |
| T8 | theorems.md | tested-only | `tests/differential/test_graph_vs_executor.py`, `tests/personality/` | not cited |
| T9 | sc-derivation.md, theorems.md | proved | `tests/unit/solve/synth/test_synth_sc.py` | not cited (`solve/synth/sc.py` cites plan 12.4) |
| T10 | theorems.md (vertex lemma) | proved | `tests/property/test_vertex_lemma.py` | `src/qtiming/bench/truth.py`, `src/qtiming/verdict/minimise.py` |
