# Hermes deployment and integration

## Observed baseline

Inspected on 2026-10-25 at local cuPhoton revision `987111ee0cbfa0c8b3f322a9782f5c821f3430b8`. This is a deployment snapshot, not a promise about future versions. Reinspect these files before editing:

- `agent_interface/mcp_server.py`: FastMCP server `cuphoton`; registers `list_runs`, `run_pipeline`, then `imaging_tools.register(mcp)`.
- `agent_interface/imaging_tools.py`: ten helpers: `gaussian2d`, `make_scene`, `write_fits`, `stretch_gray`, `stretch_div`, `label_panel`, `panel`, `panel_kernel`, `residual_colorbar`, `show_row`. Read signatures directly.
- `agent_interface/configure_spark.py`: derives a tool include-list from the two pipeline tools and `imaging_tools.NAMES`. Writes the default Hermes config and a dedicated dashboard profile. Do not rerun it merely to add a skill: it rewrites that profile and installs/restarts the service.
- `agent_interface/chat_jobs.py`: launches `hermes_stream.py chat --quiet --oneshot --toolsets cuphoton --max-turns 8` using `HERMES_HOME=agent_interface/hermes-profile`.
- `agent_interface/hermes_stream.py`: streams Hermes callbacks; changing skills alone does not change its enabled tools.
- `agent_interface/README.md`: deployment, numerical interpretation and verification notes.

The documented deployment root is `/home/nvidia/Desktop/image_understanding/cuPhoton` on Darknight Spark. The service is `cuphoton-dashboard`; loopback port 8765 serves the dashboard. The authenticated internet gateway exposes the same chat. Live host connectivity was unavailable when this skill was authored.

## Install the skill

On the target host, copy this complete `cuphoton-tool-builder` directory into the active profile's `skills/` directory. For the dashboard this is normally:

`/home/nvidia/Desktop/image_understanding/cuPhoton/agent_interface/hermes-profile/skills/cuphoton-tool-builder/`

The CLI's default `~/.hermes/skills/` is a separate destination. Resolve `HERMES_HOME` first; installing only in the default profile may not affect dashboard chat. Preserve an existing skill before replacing it.

Verify discovery using the installed Hermes version's skills interface. Official Hermes documents `skills_list`, `skill_view`, and skill slash commands, but the custom dashboard invokes the CLI through its own adapter: test that surface rather than assuming slash-command parsing or automatic skill loading works there.

## Enable actual tool development

The current `cuphoton` toolset exposes experiment operations, not file editing, code execution, or tool registration. Installing this skill therefore does not by itself enable autonomous tool creation.

Choose an implementation route appropriate to the authorized scope:

1. A trusted development Hermes session with the installed version's file/terminal and skills tools plus the `cuphoton` MCP tools. Inspect `hermes chat --help` and available toolsets before changing flags; do not guess toolset names.
2. A separately implemented builder MCP service that stages generated adapters in a bounded workspace, runs tests in an isolated worker, and promotes validated versions through a controlled registry. This service is an architectural option, not an existing capability. It must enforce paths, budgets and activation rules in code, not only prompts.

Do not silently broaden the public dashboard's permissions. If the user requested chat-based development, prepare the integration patch and explain which chat surface gains which capabilities before activating a material privilege expansion.

## Register an adapter in the existing server

For a new science adapter, create a separate module with typed functions and a registration function following the existing FastMCP pattern. Import/register it from `mcp_server.py`. Keep the original `imaging_tools.NAMES` set restricted to source-script helpers: it is also used by AST extraction and adding unrelated names breaks that loader.

Extend the configured `mcp_servers.cuphoton.tools.include` list for each intended profile and update the configuration generator so a later setup run retains the tools. Preserve every unrelated config field. Back up changed config and adapter files. This is static process registration; source changes are not live until the MCP process restarts.

Long GPU operations must use scheduler integration with explicit job dispatch and result/status handling; the existing scheduler accepts the notebook run, not arbitrary jobs. Do not claim a new GPU tool uses it until that dispatch is implemented and tested. Keep model switching, resource ownership and active experiments coordinated.

After registration, use a fresh session or `/reload-mcp` where supported, discover the schema, and invoke a small test. Restore backed-up files/config and restart only affected processes if activation fails. Do not erase run artifacts during rollback.

## Sources

- [Hermes skills](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/skills.md)
- [Hermes MCP integration](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/mcp.md)
- Local deployment files listed above are authoritative for this dashboard; upstream Hermes docs describe the general product.
