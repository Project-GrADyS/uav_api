---
name: commit-changes
description: Stage all changes, create a descriptive commit message, and commit locally
allowed-tools: Bash(git *), AskUserQuestion
user-invocable: true
---

# Commit Changes

Analyze current changes, create a commit with a descriptive message.

## Instructions

1. **Inspect changes**:
   - Run `git status` to see all modified and untracked files
   - Run `git diff` to see unstaged changes
   - Run `git diff --cached` to see already-staged changes
   - Run `git log --oneline -5` to see recent commit message style

2. **Stage changes**:
   - Stage relevant files by name with `git add <file> ...`
   - Do NOT stage files that look like secrets or credentials (.env, credentials.json, etc.)

3. **Draft commit message**:
   - Summarize the nature of the changes (new feature, bug fix, refactor, docs update, etc.)
   - Keep the first line concise (under 72 characters), focused on the "why" not the "what"
   - Add a blank line and bullet points for details if multiple files/areas changed
   - Follow the style of recent commits in the repository

4. **Confirm with user**:
   - Use `AskUserQuestion` to show the proposed commit message and ask the user to confirm or provide an edited version
   - If the user provides edits, use the updated message

5. **Commit**:
   - Use a HEREDOC to pass the confirmed message:
     ```
     git commit -m "$(cat <<'EOF'
     Commit message here

     EOF
     )"
     ```
   - Do NOT push to origin

6. **Report** the commit hash and branch to the user.
