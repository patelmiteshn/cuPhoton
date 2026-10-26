# Contract for generated tools

## Deliverables

A reusable addition should include a typed adapter, MCP registration, numerical and validation tests, a short chat example, dependency notes, and a persisted description of its inputs/outputs and provenance. Include profile/allowlist changes only when activation is in scope. Do not claim a recipe is a newly registered MCP tool.

Before implementation, resolve these fields in prose or a small manifest:

- Name, description and source API/CLI with installed revision.
- Input schema: required values, units, coordinate order, array ranks/dtypes, accepted artifact kinds and numeric bounds.
- Output schema: artifact IDs/download routes, metrics with units, effective configuration, actual backend and error/status representation.
- Execution: synchronous or queued; job/status lookup; memory/pixel/batch/time limits; scheduler integration and side effects.
- Validation: synthetic fixture, numerical reference/invariant and tolerance, invalid-input cases, GPU requirement and chat smoke test.

## Implementation rules

Use opaque artifact IDs for arrays, FITS and images. Resolve them through the established store and verify type/existence; never convert an untrusted ID into an arbitrary path. Extend artifact metadata where scientific semantics need more than shape/dtype. Large arrays belong in files, not model context.

Validate sizes and total allocations before loading/allocating large arrays. Reject malformed types (including booleans where integers are required), nonfinite parameters, path traversal and unsupported shapes. Follow component-specific masked-pixel/nonfinite behavior rather than rejecting valid masked data indiscriminately.

Use explicit public API calls or a fixed executable and argument list for a documented CLI. Do not create a general `eval`, `exec`, shell-command or arbitrary-import MCP endpoint. Loading reviewed source definitions in the existing helper loader is not permission to execute chat-supplied code in the server. Keep imports free of pipeline execution.

Return structured failures with the failing stage and useful remediation. Do not hide backend fallback; a request requiring GPU should fail clearly when GPU execution is unavailable. Write per-run outputs to unique locations and avoid overwriting user data. Retain only intended artifact download routes.

## Behavioral checks

| Example request | Expected behavior |
| --- | --- |
| “Create a synthetic scene and give me a labeled image.” | Reuse `make_scene` and rendering tools with their discovered schemas; no new adapter needed. |
| “Add a reusable tool that summarizes residuals for a saved array.” | Inspect artifact schema; implement bounded numeric statistics with defined units/mask policy; test known arrays and invalid IDs; register only after tests. |
| “Fit dipoles in my FITS file.” | Establish selected HDU, aligned difference plane, candidates, stamp dimensions and variance/mask policy; do not invent missing candidates. |
| “Try three kernel sigmas and compare.” | Compose scheduled runs, wait for actual completion, compare measured reports; respect scheduler capacity and retain run IDs across turns. |
| “Create a tool” in a session with only the existing 12 tools | Explain the missing development capabilities and produce a concrete specification/patch if possible; do not claim installation. |
| “Make every Python function callable from public chat.” | Propose scoped adapters for the actual research need; do not expose unrestricted interpreter execution. |

Test the new tool through MCP discovery and invocation as well as its underlying Python function. Schema generation, profile inclusion, process reload and artifact URL access can each fail independently of numerical correctness.
