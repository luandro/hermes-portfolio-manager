# Hermes Plugin API Notes

Reference for the Hermes plugin system as used by the Portfolio Manager plugin.

## Required Files

A Hermes plugin consists of two required files:

- `plugin.yaml` — declarative plugin manifest at the repo root.
- `__init__.py` — Python package entry point inside the plugin package directory, exporting a `register(ctx)` function.

## plugin.yaml Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | Plugin identifier (e.g. `portfolio-manager`). |
| `version` | string | Semantic version (e.g. `0.1.0`). |
| `description` | string | Human-readable summary of the plugin. |
| `author` | string | Author or organization name. |
| `kind` | string | Plugin kind. Use `standalone` for self-contained plugins. |
| `provides_tools` | list\[string\] | Tool names the plugin registers with Hermes. |

## Tool Registration API

Plugins register tools during `register(ctx)` by calling `ctx.register_tool()` for each tool:

```python
ctx.register_tool(
    name="portfolio_ping",       # unique tool name
    toolset="portfolio-manager", # logical grouping
    schema={...},                # OpenAI function-calling schema dict
    handler=_handler_fn,         # async or sync callable
    check_fn=None,               # optional pre-check callable
    emoji="",                    # optional display emoji
)
```

The `name` must be unique across all loaded plugins. The `schema` follows the OpenAI function-calling convention. The `handler` is invoked when Hermes routes a tool call to this plugin.

## Tool Schema Format

Each tool schema is a dict with the following structure:

```python
{
    "name": "tool_name",
    "description": "What this tool does.",
    "parameters": {
        "type": "object",
        "properties": { ... },
        "required": [ ... ],
    },
}
```

Properties use JSON Schema types (`string`, `integer`, `boolean`). Enum constraints are supported via `"enum": [...]`.

## Handler Signature

Each handler receives a single `params: dict` argument and returns a dict:

```python
def _handle_portfolio_ping(params: dict) -> dict:
    return {"status": "ok", "tool": "portfolio_ping", "message": "pong"}
```

Handlers must return a JSON-serializable dict. The convention is to include `status`, `tool`, `message`, and optionally `data`, `summary`, and `reason` keys.

## Return Format

Handlers use two conceptual return helpers:

- `tool_result` — a successful result dict with `status: "ok"` and relevant data.
- `tool_error` — an error result dict with `status: "error"` and a descriptive message.

In practice, these are plain dicts returned from handlers:

```python
# tool_result pattern
{"status": "ok", "tool": "portfolio_ping", "message": "pong", "data": {...}}

# tool_error pattern
{"status": "error", "tool": "portfolio_ping", "message": "something went wrong", "reason": "..."}
```

## Skill Discovery

Plugins register skills via `ctx.register_skill()` in the same `register()` function:

```python
ctx.register_skill(
    name="portfolio-status",
    path=skill_path,       # Path to SKILL.md
    description="...",     # Human-readable description
)
```

Skills are discovered from a `skills/` directory. The plugin checks the repo-root `skills/` directory first, falling back to the plugin-local `skills/` directory. Each skill is a subdirectory containing a `SKILL.md` file.

## Plugin Reload or Restart Procedure

Hermes does not support hot-reload of plugins. To apply plugin changes:

1. Install the updated plugin package into the Hermes virtual environment.
2. Restart the Hermes agent process to pick up the new plugin code.

There is no in-process reload mechanism. A full restart is required for changes to `plugin.yaml`, tool schemas, or handler logic to take effect.

## Source References

- `plugin.yaml` — plugin manifest at repo root.
- `portfolio_manager/__init__.py` — `register()` function that registers all tools and skills.
- `portfolio_manager/schemas.py` — OpenAI function-calling schema definitions for every tool.
- `portfolio_manager/tools.py` — handler implementations for MVP 1 and MVP 2 tools.
- `portfolio_manager/maintenance_tools.py` — handler implementations for MVP 4 maintenance tools.
- `portfolio_manager/skills/` — skill directories containing `SKILL.md` files.
