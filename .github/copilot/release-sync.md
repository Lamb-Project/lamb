# Release Sync: Synchronizing Dev and Main Branches

This skill guides you through the process of synchronizing the `dev` and `main` branches and creating a new release tag for the LAMB project.

## Overview

The LAMB project follows a dual-branch workflow where:
- `dev` branch is used for active development
- `main` branch is the stable production branch
- Releases are tagged on `main` and version numbers are bumped in code

## Prerequisites

- Clean working tree (no uncommitted changes)
- Access to push to both `dev` and `main` branches
- Node.js installed (for version generation script)

## Process

### Step 1: Fetch Latest Changes

```bash
git fetch origin
```

### Step 2: Sync Main Commits to Dev

First, bring any commits from `main` that aren't in `dev`:

```bash
# Switch to dev branch
git checkout dev

# Check commits in main not in dev (dry-run)
git log --oneline dev..origin/main | head -20
git log --oneline dev..origin/main | wc -l

# Test merge for conflicts (dry-run)
git merge --no-commit --no-ff origin/main

# If successful, abort the test merge
git merge --abort

# Perform the actual merge
git merge origin/main

# Push to remote
git push origin dev
```

### Step 3: Sync Dev Commits to Main (Fast-Forward)

Next, bring dev commits into main using fast-forward merge:

```bash
# Switch to main branch
git checkout main

# Pull latest main
git pull origin main

# Check commits in dev not in main (dry-run)
git log --oneline main..origin/dev | head -20
git log --oneline main..origin/dev | wc -l

# Verify fast-forward is possible
git merge-base --is-ancestor main origin/dev && echo "Fast-forward possible" || echo "Fast-forward NOT possible"

# Perform fast-forward merge
git merge --ff-only origin/dev

# Push to remote
git push origin main
```

### Step 4: Create Release Tag

Determine the next version number (check previous tags):

```bash
# Check latest tags
git tag --sort=-v:refname | head -5

# Create new annotated tag (e.g., v0.5)
git tag -a v0.5 -m "Release v0.5"

# Push tag to remote
git push origin v0.5
```

### Step 5: Bump Version Number in Code

Update the version displayed in the LAMB UI:

```bash
# Edit the version number in the generator script
# File: frontend/svelte-app/scripts/generate-version.js
# Change: version: '0.4' -> version: '0.5'

# Regenerate the version file
node frontend/svelte-app/scripts/generate-version.js

# Stage only the generator script (NOT version.js)
git add frontend/svelte-app/scripts/generate-version.js

# Commit the version bump
git commit -m "chore: bump version to 0.5"

# Push to main
git push origin main
```

### Step 6: Update Tag to Include Version Bump

Move the tag to the commit that includes the version bump:

```bash
# Delete old tag locally and remotely
git tag -d v0.5
git push origin :refs/tags/v0.5

# Create new tag on current commit
git tag -a v0.5 -m "Release v0.5"
git push origin v0.5
```

### Step 7: Sync Version Bump Back to Dev

```bash
# Switch to dev and fast-forward merge
git checkout dev
git merge main --ff-only

# Push to remote
git push origin dev
```

## Important Notes

### Version Bumping Rules

Per [CLAUDE.md](../../CLAUDE.md):
- Version lives in `frontend/svelte-app/scripts/generate-version.js`
- Run `node frontend/svelte-app/scripts/generate-version.js` to regenerate `src/lib/version.js`
- **Only commit the generator script change, NOT the generated file**
- The generated `version.js` file is built during deployment and should not be committed

### Conflict Resolution

If the merge in Step 2 fails with conflicts:
1. Resolve conflicts manually
2. Stage resolved files: `git add <files>`
3. Complete the merge: `git commit`
4. Continue with the remaining steps

### Fast-Forward Failures

If fast-forward in Step 3 fails:
- This means `main` has commits that `dev` doesn't have
- You may need to merge instead: `git merge origin/dev`
- This creates a merge commit instead of a clean fast-forward
- Consider if this is expected or if Step 1 was skipped

## Quick Reference Commands

```bash
# Full release process (after testing)
git checkout dev && git merge origin/main && git push origin dev
git checkout main && git pull origin main && git merge --ff-only origin/dev && git push origin main
git tag -a v0.X -m "Release v0.X" && git push origin v0.X

# Update version number in code
# Edit: frontend/svelte-app/scripts/generate-version.js (version: '0.X')
node frontend/svelte-app/scripts/generate-version.js
git add frontend/svelte-app/scripts/generate-version.js
git commit -m "chore: bump version to 0.X"
git push origin main

# Move tag to version bump commit
git tag -d v0.X && git push origin :refs/tags/v0.X
git tag -a v0.X -m "Release v0.X" && git push origin v0.X

# Sync back to dev
git checkout dev && git merge main --ff-only && git push origin dev
```

## Verification

After completing all steps:

```bash
# Verify both branches are at the same commit
git log --oneline --graph --all -5

# Verify tag points to the right commit
git show v0.X

# Check tag list
git tag --sort=-v:refname | head -5
```

Expected result: Both `main` and `dev` should be at the same commit with the tag pointing to that commit.
