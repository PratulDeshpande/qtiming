# Pre-registration

`prereg-2026.yaml` is the pre-registration file of plan 17.3. It is a DRAFT: every number in it is
an illustrative placeholder taken from the plan, and `registered`, `git_commit` and the contract
hashes are empty. Nothing has been registered, and no git tag exists.

## Procedure (a human step)

1. The researcher and the advisor replace every placeholder (thresholds, run counts, seeds, the
   `analysis` section) with the values they commit to.
2. Freeze the code that the evaluation will run, then fill in `git_commit` and the hashes:
   `git rev-parse HEAD` and `sha256sum src/qtiming/contract/instances/*`
   (`qtiming-bench run` also records them in each run's `manifest.json`).
3. Commit the file, then create an annotated tag BEFORE any evaluation run:
   `git tag -a prereg-1 -m "pre-registration, version 1"`. This is deliberately not done by any
   script in this repository.
4. Only then run the commands under `commands:` in the YAML. Any change after the tag is reported
   in the paper as a deviation (plan 17.3, P17 deviation list).

`benchmarks/expected.json` is a regression snapshot of the checker, not ground truth, and is not
part of the registered claims.
