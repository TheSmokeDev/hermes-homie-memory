# hermes-homie-memory

Read-only Homie vault recall for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

This is a standalone memory-provider plugin. It does not add a provider under
Hermes' in-tree `plugins/memory/` directory because Hermes contributor guidance
now asks new memory backends to ship as standalone plugin repos.

## What It Does

- Indexes a local Homie or Obsidian-compatible Markdown vault.
- Injects compact recall through Hermes' `MemoryProvider.prefetch()`.
- Exposes read-only tools:
  - `homie_memory_search`
  - `homie_memory_context`
  - `homie_memory_status`
- Keeps V1 read-only: no automatic durable-memory writes, no graph compiler,
  no BrowserOps, and no private Homie workspace data.

The provider is inspired by The Homie's public memory substrate: `SOUL.md`,
`USER.md`, `MEMORY.md`, `GOALS.md`, daily and weekly logs, concept pages, and
plain Markdown wikilinks. The Homie public framework is here:
https://github.com/TheSmokeDev/thehomie-framework

## Install

```bash
hermes plugins install TheSmokeDev/hermes-homie-memory
hermes memory setup
```

Choose `hermes-homie-memory` as the active memory provider and provide the
absolute path to your Homie or Obsidian-compatible vault.

Manual config is also supported:

```bash
hermes config set memory.provider hermes-homie-memory
```

Then set one of:

```bash
export HERMES_HOMIE_MEMORY_VAULT_PATH=/path/to/vault
# or, if you already use The Homie:
export HOMIE_VAULT_DIR=/path/to/vault
```

The provider also reads `$HERMES_HOME/hermes-homie-memory.json`:

```json
{
  "vault_path": "/path/to/vault",
  "max_prefetch_chars": 2500,
  "max_tool_chars": 8000
}
```

## Hermes Usage

```bash
hermes memory status
hermes hermes-homie-memory status
hermes hermes-homie-memory search "active project decisions"
```

In chat, Hermes may call:

- `homie_memory_search(query, limit, path_prefix)`
- `homie_memory_context(query, max_chars)`
- `homie_memory_status()`

## Vault Requirements

The vault is just Markdown. A minimal Homie-style vault has:

- `SOUL.md`
- `USER.md`
- `MEMORY.md`
- `GOALS.md`

The provider safely skips symlinks and hidden/system directories such as
`.git`, `.obsidian`, and `_state`. It never writes to the vault in V1.

## Development

```bash
python -m pip install -e ".[dev]"
pytest -q
python scripts/check_public_safety.py
```

## License

MIT.
