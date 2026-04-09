---
name: sync-docs
description: Synchronize project documentation with the current codebase. Use when the user says "sync docs", "update docs", "update documentation", "sync documentation", or after making code changes that affect endpoints, architecture, CLI args, or file structure.
allowed-tools: Read, Glob, Grep, Edit, Write, Bash(git diff*), Bash(git log*), Bash(git status*), Bash(pip show*), AskUserQuestion
user-invocable: true
---

# Sync Documentation

Detect drift between code and documentation, then update docs to match current code state.

## Phase 1: Detect what changed

1. Run `git diff HEAD~5 --name-only` to find recently changed files
2. Categorize changes by area: routers, copter.py, args.py, api_app.py, classes/, pyproject.toml, flight_examples/
3. If no recent changes exist, do a full drift scan (all code vs all docs)

## Phase 2: Read current code state (scoped to changes)

Only read files relevant to detected changes:

| Change area | What to extract |
|-------------|-----------------|
| `routers/*.py` | Endpoint signatures, query/body params, response shapes, error codes |
| `args.py` | Argument names, defaults, types, help text |
| `api_app.py` | Lifespan tasks, router registrations, metadata tags |
| `copter.py` | Method signatures, naming convention consistency |
| `classes/*.py` | Pydantic model fields and types |
| `pyproject.toml` | Dependencies, version |

## Phase 3: Read current docs

Read all doc files to compare against code:
- `CLAUDE.md` — project structure, entry points, CLI args, testing
- `README.md` — features, installation, CLI args, extra features, examples
- `.claude/docs/specification.md` — endpoint specs (params, responses, errors)
- `.claude/docs/architectural_patterns.md` — design patterns, background tasks, conventions

## Phase 4: Identify drift

Compare code vs docs across these dimensions:

| Dimension | Code source | Doc targets |
|-----------|------------|-------------|
| Endpoints (names, methods, params, responses) | `routers/*.py` | specification.md, README.md |
| CLI arguments (names, defaults, types) | `args.py` | CLAUDE.md, README.md |
| Project structure (new/removed/renamed files) | `Glob **/*.py` | CLAUDE.md, README.md |
| Dependencies | `pyproject.toml` | CLAUDE.md (tech stack) |
| Background tasks / lifespan | `api_app.py` | architectural_patterns.md |
| Entry point line numbers | `api_app.py`, `copter.py` | CLAUDE.md, architectural_patterns.md |
| External tool requirements (subprocess calls) | router code | README.md (installation notes) |

## Phase 5: Evaluate document structure

Check each doc file against these rules:
- **~150 lines max per file** — if a file exceeds this, propose splitting by responsibility
- **One responsibility per file** — if a file mixes unrelated concerns, propose splitting
- **New code areas need new docs** — if a new router/subsystem was added, create a new `.claude/docs/` file rather than appending
- When splitting, update cross-references in `CLAUDE.md` "Additional Documentation" section
- All agent-facing docs go in `.claude/docs/`; `README.md` is the sole user-facing file

## Phase 6: Present changes to user

Use `AskUserQuestion` to show:
- Summary of detected drift, grouped by doc file
- Any proposed file splits or new file creations
- Let the user confirm or adjust before editing

## Phase 7: Apply updates

- Use `Edit` for modifying existing files; `Write` only for creating new files
- Preserve each file's existing structure and writing style
- For specification.md: maintain section format (endpoint heading → params table → response → errors)
- For README.md: user-friendly tone; include install instructions for external tools (e.g. `sudo apt install fswebcam`)
- For CLAUDE.md: keep tables concise
- For architectural_patterns.md: only update if patterns actually changed

## Phase 8: Verify

- `Grep` for stale references (old endpoint names, removed params, renamed files)
- Report what was updated and any remaining issues

## Rules

- **Never invent docs for code you haven't read** — always read source first
- **External CLI tools** referenced in code (subprocess calls) must include installation instructions in README
- **Don't touch flight_examples/ docs** in README unless example files themselves changed
- **Ask before splitting or creating files** — never restructure docs without user confirmation
- **When unsure if a change is meaningful, ask** — don't guess
