# Measured refinement

Every phase records start/end, elapsed seconds, actual exit, retries, log and supervisor
journal. Admission records physical capacity and queue wait. Version manifests hash
HEAD, remote base, WIP and working source without printing file contents or credentials.
Closed jobs keep their metrics and evidence; closure releases capacity, not history.

Use report for local HTML and machine-readable JSON. Compare accepts only the same
project/profile and discovered case inventory, the same measured phases, full clean
passes and verified closure. It reports phase deltas, not an invented speedup.
The complete phase execution inventory, including repeated phases, must match;
failed or interrupted auxiliary commands make that run unsuitable as a baseline.
Record source changes and capacity alongside results. Repeat comparable successful complete
runs before claiming improvement; faster failing or smaller runs do not count.

Admission charges pending phase growth against measured physical usage. A ready
allocation remains charged until a newer physical sample includes it; this avoids
double charging running stacks while covering simultaneous starts. Pending test
growth stays reserved through the entire test phase. Calibrate phase growth budgets
from real stacks rather than silently reducing the safety reserve.
The macOS physical sampler is shared with agent-watch; no logical session count is a
substitute for pressure, CPU idle and actual process trees. Other operating systems
need an explicit physical sampler; this implementation fails instead of guessing.

Fifteen tooling fixture lanes prove scheduler/resource isolation for that fixture.
They do not prove fifteen full production stacks fit in memory. Acceptance must include
the real project stack, complete case coverage, neighbor survival and cleanup.
