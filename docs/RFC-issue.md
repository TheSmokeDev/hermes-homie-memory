# Hermes RFC Issue Draft

Title:

```text
[Show & Tell/RFC] hermes-homie-memory: local Homie vault memory provider
```

Body:

```markdown
## Summary

I maintain `hermes-homie-memory`, a standalone Hermes memory-provider plugin
that gives Hermes read-only recall over a local Homie / Obsidian-compatible
Markdown vault.

This is intentionally a standalone provider, not a PR adding a new directory
under `plugins/memory/`, because Hermes contributor guidance says new memory
providers should ship out-of-tree.

## Current release

- Repository: https://github.com/TheSmokeDev/hermes-homie-memory
- Release: https://github.com/TheSmokeDev/hermes-homie-memory/releases/tag/v0.1.0
- Provider name: `hermes-homie-memory`
- Install shape: `hermes plugins install TheSmokeDev/hermes-homie-memory`

## What it adds

- Read-only indexing of a local Homie / Obsidian-compatible Markdown vault
- `prefetch(query)` context injection with a configurable character cap
- Tools: `homie_memory_search`, `homie_memory_context`, `homie_memory_status`
- Safe path-prefix filtering and symlink/system-directory skips
- No automatic memory writes in V1

## Validation

- Unit tests cover config parsing, temp-vault indexing, ranking, context caps,
  missing vault behavior, JSON tool responses, and read-only sync behavior.
- Public-safety scan checks for private paths, local env-file mentions,
  planning/tracker references, and common secret markers before release.

## Why standalone

The provider is useful for users who keep long-term agent memory in plain
Markdown and want Hermes to recall it without adopting a hosted memory service.
It keeps release gates, tests, and docs in its own repo and avoids adding a
new in-tree memory backend to Hermes.

## Request

Would maintainers be open to one of these?

1. A docs PR adding `hermes-homie-memory` to a community/standalone provider
   example section.
2. A docs PR that documents the general standalone memory-provider install
   pattern, using `hermes-homie-memory` as one example.
3. No listing yet, but feedback on what additional validation or security
   evidence would be required before considering it.
```
