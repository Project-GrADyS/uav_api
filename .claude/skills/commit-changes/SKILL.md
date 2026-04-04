---
name: commit-changes
description: Stage all changes, create a descriptive commit message, and push to origin
allowed-tools: Bash(git *)
user-invocable: true
---

# Commit and Push Changes

Analyze current changes, create a commit with a descriptive message, and push to origin.

## Instructions

1. **Inspect changes**:
   - Run `git status` to see all modified and untracked files
   - Run `git diff` to see unstaged changes
   - Run `git diff --cached` to see already-staged changes
   - Run `git log --oneline -5` to see recent commit message style

2. **Stage changes**:
   - Stage relevant files by name with `git add <file> ...`
   - Do NOT stage files that look like secrets or credentials (.env, credentials.json, etc.)

3. **Write commit message**:
   - Summarize the nature of the changes (new feature, bug fix, refactor, docs update, etc.)
   - Keep the first line concise (under 72 characters), focused on the "why" not the "what"
   - Add a blank line and bullet points for details if multiple files/areas changed
   - Follow the style of recent commits in the repository
   - Use a HEREDOC to pass the message:
     ```
     git commit -m "$(cat <<'EOF'
     Commit message here

     Co-Authored-By: Claude <noreply@anthropic.com>
     EOF
     )"
     ```

4. **Push to origin**:
   - Run `git push origin` to push the current branch

5. **Report** the commit hash and pushed branch to the user.
