# Dynamarq: intentionally empty

The plan (17.1) lists about 10 Dynamarq programs as an external family "where available". They
are third-party programs and were not available offline when this suite was generated, and this
repository does not invent substitutes for them. Look-alike programs would defeat the point of
the family (reducing benchmark bias with code the qtiming authors did not write).

When the real programs are obtained, add each as `<name>.qasm` here and record its source URL,
commit, licence and retrieval date in `meta.json`, then rerun `qtiming-bench run` and
`qtiming-bench check --update`.
