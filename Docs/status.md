# Status and limits

qtiming is alpha (version `0.1.0`). The same list is in the repository `README.md`.

* A verdict is only as good as the contract numbers behind it. Numbers a vendor has not published
  are left absent, so the obligations that need them come out UNKNOWN, never guessed.
* IBM gate durations come from an UNOFFICIAL snapshot; the IBM feed-forward latency
  (`ff.default`, 0 to 600 ns) is a vendor claim, so IBM verdicts are PROVED-UNDER, not PROVED.
* No real IBM hardware evidence is in the repository. `tests/fixtures/evidence/` is synthetic.
* The DC (dynamic controllability) checker `solve/synth/stnu_dc.py` is flagged UNVERIFIED; see
  [DC rules](theory/dc-rules.md). It is not used to verify programs, only for synthesis.
* Not checked by this build, and listed on every report: O4a, O6, O8, O9, O7 for SYNC with a spread bound.
