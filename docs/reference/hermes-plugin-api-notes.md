# Hermes Plugin API Notes

Reference for building plugins for the Hermes agent system.

## Required Files

A directory plugin needs both of these in the same folder:

- **`plugin.yaml`** — manifest declaring the plugin's identity and capabilities
- **`__init__.py`** — Python module exporting a `register(ctx)` function

Discovery sources (later sources override earlier on name collision):

1. Bundled plugins — `<repo>/plugins/<name>/`
2. User plugins — `~/.hermes/plugins/<name>/`
3. Project plugins — `./.hermes/plugins/<name>/` (requires `HERMES_ENABLE_PROJECT_PLUGINS` env var)
4. Pip plugins — packages exposing the `hermes_agent.plugins` entry-point group

Flat layout: `<root>/<plugin-name>/plugin.yaml` — key is `<plugin-name>`.

Category layout: `<root>/<category>/<plugin-name>/plugin.yaml` — key is `<category>/<plugin-name>` (depth capped at 2).

## plugin.yaml Fields

```yaml
name: my-plugin          # Required. Plugin identifier.
version: "1.0.0"         # Optional. Semantic version string.
description: "..."       # Optional. Human-readable description.
author: "..."            # Optional. Author name.
kind: standalone         # Optional. One of: standalone (default), backend, exclusive.
provides_tools:          # Optional. List of tool names this plugin registers.
  - my_tool_a
  - my_tool_b
provides_hooks:          # Optional. List of hook names this plugin registers.
  - post_tool_call
requires_env:            # Optional. List of env vars or {var, purpose} dicts.
  - MY_API_KEY
```

`kind` semantics:

- **standalone** — hooks/tools of its own; opt-in via `plugins.enabled` config.
- **backend** — pluggable backend for a core tool (e.g. image_gen). Bundled backends auto-load; user-installed still gated by `plugins.enabled`.
- **exclusive** — category with exactly one active provider (e.g. memory). Selection via `<category>.provider` config key.

## Tool Registration API

Inside `register(ctx)`, call `ctx.register_tool()` for each tool:

```python
def register(ctx) -> None:
    ctx.register_tool(
        name="my_tool",                  # Unique tool name
        toolset="my_plugin",             # Toolset grouping
        schema={...},                    # OpenAI function-calling schema
        handler=my_handler,              # Callable: (args: dict, **kwargs) -> str
        check_fn=None,                   # Optional availability check callable
        requires_env=None,               # Optional list of required env vars
        is_async=False,                  # Set True for async handlers
        description="",                  # Optional human description
        emoji="",                        # Optional emoji for UI display
    )
```

## Tool Schema Format

Schema follows the OpenAI function-calling format:

```python
MY_TOOL_SCHEMA = {
    "name": "my_tool",
    "description": "Does something useful.",
    "parameters": {
        "type": "object",
        "properties": {
            "input_text": {
                "type": "string",
                "description": "The text to process.",
            },
            "count": {
                "type": "integer",
                "description": "How many times to process.",
            },
        },
        "required": ["input_text"],
    },
}
```

The registry wraps this in `{"type": "function", "function": schema}` before sending to the model.

## Handler Signature

```python
def my_handler(args: dict, **kwargs) -> str:
    """Handle a tool call. Must return a JSON string."""
    input_text = args.get("input_text", "")
    # ... do work ...
    return tool_result(success=True, output=result)
```

Key points:

- Receives `args` (dict of parameter values from the model) plus optional `**kwargs` (e.g. `parent_agent`, `task_id`, `session_id`).
- Must return a JSON string (`str`).
- If `is_async=True` was set during registration, the handler can be `async def` — the registry bridges it automatically.

## Return Format

All tool handlers must return a JSON string. Use the helper functions from `tools.registry`:

```python
from tools.registry import tool_result, tool_error

# Success
return tool_result(success=True, count=42)
# => '{"success": true, "count": 42}'

return tool_result({"key": "value"})
# => '{"key": "value"}'

# Error
return tool_error("file not found")
# => '{"error": "file not found"}'

return tool_error("bad input", code=404)
# => '{"error": "bad input", "code": 404}'
```

Uncaught exceptions in handlers are caught by the registry and returned as `{"error": "Tool execution failed: <type>: <message>"}`.

## Skill Discovery

Skills are auto-discovered from `~/.hermes/skills/` directories containing a `SKILL.md` file. These appear in the system prompt's `<available_skills>` index.

Plugins can also register private skills via `ctx.register_skill()`:

```python
ctx.register_skill(
    name="my_skill",                          # No colons allowed
    path=Path(__file__).parent / "skills" / "my_skill" / "SKILL.md",
    description="Does X",                     # Optional
)
```

Plugin skills are referenced as `<plugin_name>:<skill_name>` and do NOT appear in the flat skills directory or the system prompt index — they are opt-in explicit loads only.

## Plugin Reload or Restart Procedure

There is no hot reload. To activate a new or modified plugin:

1. Place the plugin directory in `~/.hermes/plugins/<name>/` with `plugin.yaml` and `__init__.py`.
2. Enable it: `hermes plugins enable <name>` (adds to `plugins.enabled` in config).
3. Restart the Hermes session. The plugin loader runs at startup via `discover_and_load()`.

For long-lived sessions, `discover_and_load(force=True)` can rescan without a full restart, but this is an internal API — the standard path is a restart.

## Source References

These are the Hermes agent source files that define the plugin system:

- `~/.hermes/hermes-agent/hermes_cli/plugins.py` — `PluginManifest`, `PluginContext`, `PluginManager`, discovery and loading logic.
- `~/.hermes/hermes-agent/tools/registry.py` — `ToolRegistry`, `tool_result()`, `tool_error()`, dispatch logic.
- `~/.hermes/hermes-agent/plugins/spotify/__init__.py` — Example tool-only plugin using `ctx.register_tool()`.
- `~/.hermes/hermes-agent/plugins/spotify/plugin.yaml` — Example manifest with `kind: backend` and `provides_tools`.
- `~/.hermes/hermes-agent/plugins/disk-cleanup/__init__.py` — Example hook + slash-command plugin using `ctx.register_hook()` and `ctx.register_command()`.
