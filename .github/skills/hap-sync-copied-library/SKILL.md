---
name: hap-sync-copied-library
description: Use this skill to initialize, clean, and sync a local project into GitHub. It handles repo creation when missing and safe synchronization when a repo already exists.
---

# Skill Instructions

## Purpose

Use this skill when you want to copy a codebase into an existing repository, update a library snapshot, or align a target repo with a source directory. It helps you initialize a repo when needed, create it on GitHub if it is missing, and commit and push changes safely without overwriting sensitive data or breaking the remote history.

The GitHub organization/account used here: https://github.com/bennyskov

## Use when

- The local project is not yet a git repo.
- The repo exists locally but has no remote configured.
- The repo exists remotely but needs to be synchronized.
- A repo was created from a copied library and needs to be pushed.
- A new repo needs to be created from the current workspace.

## Safety rules

- Never commit secrets, API keys, environment files, token files, or credentials.
- Remove credentialed or generated files before pushing.
- Prefer `gh auth status` to verify authentication before creating or pushing a repo.
- If `GITHUB_TOKEN` is set incorrectly, clear it first: `unset GITHUB_TOKEN`.
- Use `--force-with-lease` only after a deliberate cleanup of sensitive content and after confirming the intended remote state.

## Standard flow

### 1. Verify GitHub auth

```bash
unset GITHUB_TOKEN
gh auth status
```

If the CLI is not logged in:

```bash
gh auth login -h github.com -w
```

If a stale token is causing `401 Bad credentials`, clear the environment variable again before retrying.

### 2. Initialize the local repository if needed

```bash
cd /path/to/project
git init -b main
```

Set local identity if missing:

```bash
git config user.name "bennyskov"
git config user.email "bennyskov@gmail.com"
```

### 3. Check whether the remote repository exists

```bash
gh repo view bennyskov/REPO_NAME --json name,visibility
```

If the repo is missing, create it from the current directory:

```bash
cd /path/to/project
gh repo create bennyskov/REPO_NAME --public --source=. --remote=origin --push --description "Project description"
```

If the repo already exists, add or fix the remote:

```bash
git remote add origin https://github.com/bennyskov/REPO_NAME.git
# or
# git remote set-url origin https://github.com/bennyskov/REPO_NAME.git
```

### 4. Commit and push

```bash
git add .
git commit -m "Initial commit for project"
git push -u origin main
```

If the repo is already tracking a remote and the branch is set, use:

```bash
git push -u origin main
```

### 5. Handle push protection from secret scanning

If GitHub rejects the push with `GH013` or `Push cannot contain secrets`, inspect the commit and remove sensitive files before retrying. Typical cleanup steps:

```bash
# find tracked secrets or token-like content
grep -RIlE 'sk-[A-Za-z0-9]|ghp_[A-Za-z0-9]|AIza[A-Za-z0-9_-]|OPENROUTER_API_KEY|ANTHROPIC_API_KEY|GITHUB_TOKEN|EMAIL_PASSWORD' . --exclude-dir=.git --exclude-dir=.venv --exclude-dir=.archive
```

Then remove the offending file(s), rewrite the branch, and push again:

```bash
rm -f path/to/offending-file
git checkout --orphan cleaned-main
git rm -rf --cached .
git add .
git commit -m "Initialize clean project workspace"
git branch -M main
git push --force-with-lease origin main
```

This is the correct pattern when earlier commits included credential material that GitHub secret scanning blocks.

## Repo sync for this HAP workspace

This workspace was initialized and synced using the same flow:

```bash
cd /Users/bennyskov/Projects/HAP
git init -b main
# optional: set git config user.name/user.email
# create repo if absent
# gh repo create bennyskov/HAP --public --source=. --remote=origin --push --description "HAP workspace for Hermes tooling and runtime maintenance"
# if push was blocked by secret scanning, remove the secret file, rewrite the branch, and push again with --force-with-lease
```

This skill is intended to cover both paths:

- create the repo when it does not exist
- sync the current local tree to the matching GitHub repo when it already exists
- clean and rewrite a branch when a secret was accidentally committed before the remote push is accepted
