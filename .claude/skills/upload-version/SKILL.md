---
name: upload-version
description: Build and upload the Python package to PyPI using setuptools and twine. Use when the user says "upload version", "publish package", "upload to pypi", or "release to pypi".
allowed-tools: Read, Bash(python3 *), Bash(pip *), Bash(twine *), Bash(rm *), Bash(ls *), AskUserQuestion
user-invocable: true
---

# Upload Version

Build the package with setuptools and upload it to PyPI with twine.

## Step 1: Read current version

1. Read `pyproject.toml` and extract the `version = "X.Y.Z"` value
2. Display the version to the user: "Building and uploading version X.Y.Z"

## Step 2: Check prerequisites

1. Run `pip show build` and `pip show twine` to check both are installed
2. If either is missing, use `AskUserQuestion` to ask the user for permission to install:
   - "The `build` and/or `twine` packages are not installed. Install them with `pip install build twine`?"
   - Options: "Yes, install them" / "No, abort"
3. If user approves, run `pip install build twine`
4. If user declines, stop and report that the upload was cancelled

## Step 3: Clean old dist

Run `rm -rf dist/` to remove any stale build artifacts.

## Step 4: Build

Run `python3 -m build` from the project root. This produces a `.whl` and `.tar.gz` in `dist/`.

If the build fails, report the error and stop.

## Step 5: List artifacts

Run `ls dist/` and display the filenames to the user so they can confirm what will be uploaded.

## Step 6: Prompt for PyPI token

Use `AskUserQuestion` to ask the user:
- Question: "Paste your PyPI API token (starts with `pypi-`):"
- This is a free-text input — do NOT provide predefined options with the token embedded
- Use two options: "I've set TWINE_PASSWORD env var" and "Enter token manually" — if they choose manual, ask them to type/paste it via the "Other" free-text option

## Step 7: Upload

Run the twine upload command:
- If user provided a token: `twine upload dist/* --username __token__ --password <TOKEN>`
- If user set env var: `twine upload dist/* --username __token__`

If twine reports an error (e.g. 403, version already exists), display the error clearly.

## Step 8: Report

On success, display:
- Package name and version uploaded
- Link: `https://pypi.org/project/uav_api/<VERSION>/`

## Key file locations

| File | What |
|------|------|
| `pyproject.toml:10` | Version string |
| `dist/` | Build output directory |

## Rules

- Always clean `dist/` before building to avoid uploading stale artifacts
- Never store or log the PyPI token — it is used only in the twine command
- If the build fails, do not attempt upload
- Do not push git tags or commits — that is the `bump-version` skill's job
