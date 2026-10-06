# Profile and adapter contract

A private project profile is JSON with schema 1, project, hooks (prepare, up, health,
discover, test, close, verify), budgets up/test (ram_gb, cpu_cores), reserve (ram_gb,
cpu_cores, disk_gb), and optional positive timeouts per hook. Each hook is an argv
array, never a shell string. Placeholders: python, root, job, profile_dir, phase,
task. Hooks are trusted project tooling, not untrusted task text.

Optional: `backfill_seconds` (queue bound, default 900) and `audit`, an argv with
placeholders python, profile_dir and root that prints a JSON list of project
resources: `{kind, name, job, owner, retained, detail}`. `job` is the agent-work
job ID or null; `retained` is the recorded reason a resource is kept on purpose
(e.g. uncommitted work with its backup path) or null. It must be read-only.

Preparation invokes the canonical project manager, fetches the declared remote
base before a new branch, journals resources immediately and saves `adapter.prepared`
and `adapter.repositories` with worktree/base per repo. A closed generation never
adopts retained WIP: its next generation must explicitly preserve/import the source.
Managers validate stable owner plus reservation generation before each mutation.
`up` provisions only that generation and `health` proves the application is ready.
Adapters that reload edited sources publish `adapter.served_source_manifest`
using the common `git_manifest` after checking the source before and after loading.
When that manifest changes, the core admits the `up` growth budget before calling
`health`; a queued reload preserves its stack and resumes the same generation.
Health must seal the newly served version and preserve data. Source changes clear
the previous validation/delivery gate; a normal unchanged health check needs no
additional startup growth.

`discover` saves adapter.catalog_evidence pointing at JSON with required_suites and
catalog [{suite, id}]. IDs must be unique, deterministic and include project/mode
where the test framework executes distinct cases. Discovery cannot start services
or replace missing tests with a passing count.

`test` invokes the canonical full runner and writes adapter.test_evidence. Required
schema: schema=1, scope=full, required_suites, catalog, catalog_sha256, results
[{suite,id,status,attempts,errors}], suites [{name,exit_code,errors,skipped,pending}],
errors and aborted. Hash is SHA256 of JSON sorted keys, compact separators. All
results must have status passed, attempts 1 and empty errors. Missing or unreadable
native reporters fail. A unit test fixture is not evidence for a product adapter.

`close` stops registered own services/browser/groups, releases the exact manager
reservation and cleans safe regenerable dependencies. Preserve source, commits,
configuration, data, volumes and evidence. `verify` checks actual postconditions and
sets adapter.cleanup_verified only after success. Both hooks are attempted. No kill
by port/name, no force database disconnect, no force worktree removal.

Adapters update only their `adapter` field atomically, preserving all other fields.
The core holds a per-job operation lock; the global capacity lock protects only brief
admission updates. Adapter identity/tokens remain in mode-600 private journals.
Cleanup uses frozen hooks even if the profile JSON was edited; retain the corresponding
adapter source until that generation is closed. Never change adapter code under a
running generation. Real project sources may be private; don't publish profiles or
journals in a public skills repository.

Delivery manifests list changed_repositories, prs [{repository,repo,number}] and
screenshots [{path,sha256,inspected:true,demonstrates}]. The profile declares
github_login and optionally mobile_first. `deliver` reads the active GitHub account,
open PR heads/bases and exact tested source; it checks the actual PNG files and their
provenance. Inspection is still the agent's visual responsibility, not a claim inferred
from file existence. Commit before full validation so the tested HEAD matches the PR.
