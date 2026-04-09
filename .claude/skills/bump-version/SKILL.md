---
name: bump-version
description: Bump the project version across all files, commit the change, and create a git tag. Use when the user says "bump version", "release version", "new version", or "tag release".
allowed-tools: Read, Edit, Grep, Bash(git *), AskUserQuestion, Skill
user-invocable: true
---

# Bump Version

Bump the project version, check dependencies, commit, and tag.

## Step 1: Read current version

1. Read `pyproject.toml` and extract the `version = "X.Y.Z"` value
2. Read `uav_api/api_app.py` and extract the `version="X.Y.Z"` value
3. If the two versions don't match, **warn the user** via `AskUserQuestion` before proceeding
4. Display the current version to the user

## Step 2: Prompt for new version

Use `AskUserQuestion` to ask the user for the new version string. Show the current version for reference. The user's input should look like semver (`X.Y.Z`).

## Step 3: Check for new dependencies

1. Grep for `import` and `from ... import` across all `.py` files in `uav_api/`
2. Filter out:
   - Python stdlib modules (os, sys, re, json, asyncio, subprocess, tempfile, pathlib, etc.)
   - Project-internal imports (`uav_api.*`)
3. Read `requirements.txt` and `pyproject.toml` `[dependencies]` section
4. Compare: any third-party package imported in code but missing from both files?
5. If missing packages found:
   - Use `AskUserQuestion` to show them and ask the user for versions to pin
   - Add to `pyproject.toml` under `dependencies` with `>=` minimum version
   - Add to `requirements.txt` with `==` pinned version
6. If no new dependencies, skip silently

## Step 4: Update version in both files

- Edit `pyproject.toml`: `version = "OLD"` → `version = "NEW"`
- Edit `uav_api/api_app.py`: `version="OLD"` → `version="NEW"`
- Always use the exact old string read in Step 1 to match

## Step 5: Commit

Invoke the `/commit-changes` skill using the `Skill` tool. This handles staging, message drafting, user confirmation, and committing.

Do NOT push to origin.

## Step 6: Create git tag

After the commit completes:
1. Run `git tag v<NEW_VERSION>` (tag name = `v` + version, e.g. `v0.2.0`)
2. Run `git log --oneline -1` to get the commit hash
3. Report the tag name and commit hash to the user

## Key file locations

| File | What | Pattern |
|------|------|---------|
| `pyproject.toml:10` | Version | `version = "X.Y.Z"` |
| `uav_api/api_app.py:130` | Version | `version="X.Y.Z"` |
| `pyproject.toml:25-36` | Dependencies | `>=` minimum versions |
| `requirements.txt` | Dependencies | `==` pinned versions |

## Rules

- Always read files before editing to get exact current values
- Never push to origin
- Tag name is always `v` + version string (e.g. `v0.2.0`)
- If versions are mismatched between files, warn user first
