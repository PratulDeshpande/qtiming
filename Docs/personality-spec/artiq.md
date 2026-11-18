# ARTIQ personality specification (exposed cursor)

Normative for the reference executor (`src/qtiming/exec/artiq.py`) and the graph builder
(`src/qtiming/dispatch/artiq.py`, P6). Golden traces: `tests/personality/artiq/golden/*.json`.
Status: frozen for P4; changes go through the decision log (plan Section 21.2).

## Model

Two clocks. The **cursor** is the timestamp (`now_mu`) stamped on outgoing events. The **CPU clock**
is when the kernel code actually runs. Dispatch never moves a stamped timestamp when the CPU is
late: that is why ARTIQ underflows and why a free-time-point model would be unsound (plan A.7).

## Dispatch rules

| Statement | Rule |
| --- | --- |
| `delay(d)` | `cursor += d`; `cpu += cpu_issue` |
| output event (`Gate`) | `cpu += cpu_issue`; `issue = cpu`; stamped `T = cursor`; then the commit check; then `cursor += dur` |
| input window (`Measure`) | `cursor += dur`; the CPU blocks: `cpu = max(cpu + cpu_issue, cursor + theta_in2cpu)`; `valid = cpu` |
| kernel `if` | `cpu += cpu_issue`; the taken arm's statements run on the CPU chain |
| `barrier` | no effect (there is one cursor) |

`cpu_issue` is the contract's `issue_cost.cpu_issue`, taking `ns`, else `hi_ns`, else `lo_ns`.

## Commit check and silent drops (on each output event)

1. **Underflow (raised).** `slack = T - issue`. If `commit_lead` is set and `slack < commit_lead`:
   violation `underflow` with shortfall `commit_lead - slack`; the run stops.
   `commit_lead` is required but unpublished: if it is absent the executor raises `E-EXEC-PARAM`
   instead of guessing (`--assume timeline.commit_lead=<ns>`).
2. **Lane assignment (SED).** Split `T` into `coarse, fine = divmod(T, coarse_mu)`. Try lanes from
   the current one: a lane is usable if it holds nothing pending (`top <= issue // coarse_mu`) or
   `coarse > top`. If none is usable: silent drop `sequence`.
3. **Collision.** An event on the same channel and coarse cycle as an earlier event with a different
   fine part: silent drop `collision`.
4. **Busy.** `T` earlier than the channel's busy-until time: silent drop `busy`.

A drop is logged and the event vanishes from the trace of effects; it is not raised.

## Named parameters

| Parameter | Default | Provenance |
| --- | --- | --- |
| `capacity.lanes` | 8 | gateware `sed_lanes`, ARTIQ manual |
| `capacity.coarse_mu` | 8 | coarse clock, typical |
| `timeline.commit_lead` | absent | unpublished; obligations that need it are UNKNOWN |
| `issue_cost.cpu_issue` | absent upper bound | none published; kernel-compiler dependent |
| `latency in2cpu` (input to CPU) | upper bound absent | ARTIQ manual gives no number |
| `capacity.sed_spread_enable`, `lane_fifo_depth` | `false`, unknown | the "nearly full" rule is not modelled |

## Not modelled

`with parallel` (cursor rewinding, which is what makes `sequence` and `busy` drops reachable in
real kernels), `at_mu`, DMA, the "nearly full" lane rule.

## Golden cases (hand-computed)

Seven cases: a pulse sequence with ample slack, underflow with shortfall, negative slack after an
input read, a delay that restores slack, a kernel `if` taking each arm, and a `collision` drop.

## Sources

ARTIQ manual (RTIO, SED, `break_realtime`, timestamps); per-number source strings in
`src/qtiming/contract/instances/artiq.toml`.
