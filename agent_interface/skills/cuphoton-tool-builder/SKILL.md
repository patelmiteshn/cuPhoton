---
name: cuphoton-tool-builder
description: Build cuPhoton MCP tools from research chat requests.
metadata:
  hermes:
    tags: [cuphoton, mcp, astronomy, tool-building]
    category: scientific-computing
---

# cuPhoton Tool Builder

## When to Use

Use when a researcher asks Hermes to add, adapt, or reuse a cuPhoton capability through chat: FITS inspection, reprojection, subtraction, dipole fitting, classification, detector analysis, or reusable diagnostic workflows. Also use when a request reveals a missing MCP capability. Ordinary requests already covered by a tool should use that tool directly.

## Procedure

### Establish the available capabilities

Inspect the current session's actual MCP schemas, available file/terminal tools, active Hermes profile, and cuPhoton checkout. Read [the setup reference](references/hermes-integration.md) for this deployment. Do not infer tool availability from library documentation or from another agent's tool list.

Identify the requested scientific outcome, supplied inputs, required output, and whether the user wants a one-time result or a reusable tool. Infer routine defaults from existing adapters. Ask only for missing scientific choices that change the result, such as mask bits, variance units, target WCS, checkpoint, or candidate coordinates.

Choose the smallest sufficient path:

| Capability | Action |
| --- | --- |
| Already exposed by MCP | Call the tool using its current schema. |
| Achievable with existing tools | Compose their calls, passing returned artifact IDs. Save a reusable recipe if requested. |
| Documented cuPhoton API/CLI exists but is not exposed | Implement a narrow typed MCP adapter and tests. |
| Requires new scientific behavior | Identify the missing algorithm or input explicitly; implement only within the requested scope and with a meaningful numerical acceptance criterion. |
| No permitted file/code execution tools | Use available tools for the supported portion and provide a concrete patch/specification for the missing capability. Say it is not installed; never simulate execution. |

### Ground the implementation

Read [the cuPhoton guide](references/cuphoton-contracts.md), then the relevant component document and implementation in the installed checkout. Prefer that version's public API or documented CLI. Check callable signatures, CLI help, optional dependencies, and return types before writing the adapter. Record the checkout revision; upstream `main` can differ from the installed version.

Define a compact contract: tool name and purpose; typed inputs with units, shapes, coordinate order and limits; output artifact kinds and metrics; backend requirement; runtime/resource bounds; side effects; and success/failure behavior. Reuse artifact storage and scheduler infrastructure where applicable. Read [the adapter contract](references/tool-contract.md) before implementing a new tool.

### Build and verify

Keep the numerical function separately testable from MCP registration. Create the smallest adapter at the component boundary; avoid changing the solver or executing an entire example script on import. Use the existing environment and dependencies where possible.

Test a small deterministic synthetic case against the underlying API or an independently known invariant. Test malformed inputs and the relevant shape, coordinate, mask, artifact-type and resource boundaries. Check serialization, artifact persistence, and error reporting. If GPU behavior is requested, test on the target GPU and record the actual backend; a CPU test does not establish GPU support.

For queued work, return a job ID and inspect terminal status before reporting measurements. A timeout or submission receipt is not completion. Do not blindly resubmit an uncertain job. Preserve failed-run evidence and stop retries when the same cause persists.

### Register and make it usable in chat

Follow the verified deployment's registration path, including the MCP server import, tool allowlist, and Hermes toolset selection. Keep changes reversible and preserve unrelated model, authentication and server configuration. Do not enable unrestricted code execution in a shared public chat as a side effect of installing a skill. Use an authorized development session or a deliberately scoped builder service.

Restart/reload only the affected MCP process when supported; avoid interrupting active experiments. Open a fresh Hermes turn, confirm the new schema is discoverable, invoke a small end-to-end example through chat, and inspect the persisted output. If deployment cannot be performed, deliver tested files and the exact remaining integration steps, explicitly separating local validation from live availability.

Return a concise outcome: capability created or reused, example chat request, measured test result, output links/IDs, and any remaining limitation. Persist reusable recipes and implementation provenance because this dashboard starts a fresh conversation for each question.

## Pitfalls

- A skill supplies instructions; it does not create permissions, tools, GPU support, or automatic hot reload.
- `run_pipeline` is the fixed synthetic notebook workflow, not a general FITS ingestion or arbitrary Python endpoint.
- The existing visualization helpers use CPU NumPy/SciPy. A CUDA-hosted tool is not necessarily GPU accelerated.
- Preserve WCS, masks, variance semantics, identifiers, dtype and units across stages. Do not silently invent observational inputs or scientific labels.
- Optimizer convergence does not establish model adequacy. Report residuals and uncertainty validity separately.
- Inspect images only when the session actually receives their pixels. A PNG link or numeric summary is not visual inspection.

## Verification

Completion requires an importable implementation, valid MCP schema, passing meaningful numerical/validation tests, and—when claiming availability—a successful call from the intended Hermes profile after reload. Include actual backend, input identity, configuration, revision, outputs and test evidence. Mark unavailable GPU tests or live deployment checks as pending.
