---
name: update-changelog
description: Add a new release entry to CHANGELOG.md by scanning commits since the last release. Use when the user says "update changelog", "add changelog entry", "changelog for release", or as part of cutting a release.
allowed-tools: Read, Edit, Write, Bash(git log*), Bash(git tag*), Bash(git for-each-ref*), Bash(git describe*), AskUserQuestion
user-invocable: true
---

# Update Changelog

Generate a new `CHANGELOG.md` entry from git history, in Keep a Changelog format.

## Step 1: Determine the version and commit range

1. Read the target version from `pyproject.toml` (`version = "X.Y.Z"`).
2. Read the top versioned heading in `CHANGELOG.md` (the most recent release).
3. Determine the previous release tag: `git for-each-ref --sort=-creatordate --format='%(refname:short)' refs/tags | head -1`.
4. Commit range to scan = `<previous-tag>..HEAD`. If the target version already has
   a section in `CHANGELOG.md`, warn the user (re-running would duplicate it) and
   ask whether to regenerate it.

## Step 2: Gather and parse commits

1. Run `git log <range> --no-merges --format='%h %s'`.
2. Classify each commit by its prefix into a Keep a Changelog group:
   | Commit prefix | Changelog group |
   |---------------|-----------------|
   | `feat/`, `feature/` | Added |
   | `fix/`, `bugfix/` | Fixed |
   | `refactor/`, `perf/`, behavior changes | Changed |
   | removals (deleted files/endpoints) | Removed |
   | `deprecate/` | Deprecated |
   | security fixes | Security |
3. **Drop noise:** version-bump commits (`chore/bump`, `Bump version`), merge
   commits, `.gitignore`/pycache/dist housekeeping, and pure-internal doc commits
   that have no user-facing effect.

## Step 3: Draft user-facing entries

- Rewrite commit subjects as **user-facing** statements, not raw git text
  (e.g. `fix/fixing bug in set_yaw_rate endpoint` → "`GET /movement/set_yaw_rate`
  no longer sends an incorrect typemask; continuous yaw works as documented").
- Collapse related commits into one bullet.
- **Flag breaking changes**: prefix the bullet with `**BREAKING:**` and put it
  under `Changed` (or `Removed`). Confirm any breaking change with the user.
- Omit empty groups.

## Step 4: Confirm with the user

Use `AskUserQuestion` to show the drafted entry (grouped) and let the user
confirm, edit, or drop bullets before writing.

## Step 5: Insert into CHANGELOG.md

1. Insert the new `## [X.Y.Z] - YYYY-MM-DD` section directly **below the intro**
   and **above the previous release** (newest-first). Date = today
   (or the release tag's date if already tagged).
2. Add a compare link at the bottom:
   `[X.Y.Z]: https://github.com/Project-GrADyS/uav_api/compare/v<prev>...v<X.Y.Z>`
3. Preserve the existing heading/format exactly (sub-groups in the order
   Added, Changed, Deprecated, Removed, Fixed, Security).
4. If `CHANGELOG.md` does not exist yet, create it with the standard header and
   this first entry.

## Step 6: Report

Summarize the version, groups written, and any bullets dropped as noise.

## Key file locations

| File | What |
|------|------|
| `CHANGELOG.md` | The changelog; new section goes near the top, links at bottom |
| `pyproject.toml` | Source of the target version string |

## Rules

- Never invent changes — every bullet must trace to a real commit in the range.
- Keep entries user-facing: describe behavior/endpoints/flags, not refactors of
  internal files.
- Always flag breaking changes explicitly and confirm them with the user.
- Newest release on top; never reorder or rewrite existing released sections.
- Do not commit or tag — that is `bump-version`/`commit-changes`' job.
