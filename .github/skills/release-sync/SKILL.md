---
name: release-sync
description: Synchronize dev and main branches for LAMB releases, including merging changes, creating version tags, and bumping version numbers in code. Use this skill when creating a new release, syncing branches, or tagging a version.
---

# Release Synchronization Skill

This skill guides the complete process of creating a new release for the LAMB project, including branch synchronization, version tagging, and code version bumping.

## When to Use This Skill

Use this skill when you need to:
- Create a new release version (e.g., v0.5, v0.6)
- Sync the `dev` branch with commits from `main`
- Merge `dev` branch changes into `main`
- Create and push version tags
- Update the version number displayed in the LAMB UI

## Prerequisites

Before starting, ensure:
- Clean working tree (no uncommitted changes)
- Push access to both `dev` and `main` branches
- Node.js is installed for running the version generation script

## Release Process

### Step 1: Fetch Latest Changes

Always start by fetching the latest state from remote:

```bash
git fetch origin
```

### Step 2: Sync Main → Dev

First, bring any commits from `main` that aren't in `dev`:

**Check what will be merged (dry-run):**
```bash
git checkout dev
git log --oneline dev..origin/main | head -20
git log --oneline dev..origin/main | wc -l
```

**Test for conflicts:**
```bash
git merge --no-commit --no-ff origin/main
# Review the staged changes
git merge --abort  # Abort the test merge
```

**Perform the actual merge:**
```bash
git merge origin/main
git push origin dev
```

### Step 3: Sync Dev → Main (Fast-Forward)

Next, bring `dev` commits into `main` using a fast-forward merge:

**Switch to main and update:**
```bash
git checkout main
git pull origin main
```

**Check what will be merged:**
```bash
git log --oneline main..origin/dev | head -20
git log --oneline main..origin/dev | wc -l
```

**Verify fast-forward is possible:**
```bash
git merge-base --is-ancestor main origin/dev && echo "Fast-forward possible" || echo "Fast-forward NOT possible"
```

**Perform the fast-forward merge:**
```bash
git merge --ff-only origin/dev
git push origin main
```

### Step 4: Create Version Tag

Determine the next version number and create the tag:

**Check previous tags:**
```bash
git tag --sort=-v:refname | head -5
```

**Create and push the tag:**
```bash
# Replace v0.X with the new version number
git tag -a v0.X -m "Release v0.X"
git push origin v0.X
```

### Step 5: Bump Version in Code

Update the version number displayed in the LAMB UI banner.

**Important Version Bumping Rules:**
- Version is defined in `frontend/svelte-app/scripts/generate-version.js`
- Run the generator script to create `src/lib/version.js`
- **Only commit the generator script**, NOT the generated `version.js` file
- The generated file is built during deployment

**Update version number:**

1. Edit `frontend/svelte-app/scripts/generate-version.js`
2. Change the version line: `version: '0.4'` → `version: '0.5'`
3. Regenerate the version file:

```bash
node frontend/svelte-app/scripts/generate-version.js
```

4. Stage and commit only the generator script:

```bash
git add frontend/svelte-app/scripts/generate-version.js
git commit -m "chore: bump version to 0.X"
git push origin main
```

### Step 6: Update Tag to Include Version Bump

Move the tag to point to the commit that includes the version bump:

```bash
# Delete old tag locally and remotely
git tag -d v0.X
git push origin :refs/tags/v0.X

# Create new tag on current commit
git tag -a v0.X -m "Release v0.X"
git push origin v0.X
```

### Step 7: Sync Version Bump Back to Dev

Ensure `dev` branch also has the version bump:

```bash
git checkout dev
git merge main --ff-only
git push origin dev
```

## Troubleshooting

### Merge Conflicts in Step 2

If the merge from `main` to `dev` has conflicts:

1. Resolve conflicts manually in the affected files
2. Stage resolved files: `git add <files>`
3. Complete the merge: `git commit`
4. Push: `git push origin dev`
5. Continue with remaining steps

### Fast-Forward Fails in Step 3

If `git merge --ff-only` fails:

- This means `main` has commits that `dev` doesn't have
- Verify you completed Step 2 correctly
- If `main` legitimately has new commits, use a regular merge instead:
  ```bash
  git merge origin/dev
  ```
  Note: This creates a merge commit instead of a clean fast-forward

### Tag Already Exists

If the tag already exists remotely, you'll need to delete it first:

```bash
git push origin :refs/tags/v0.X
```

## Quick Reference

Complete release in one sequence (after dry-run validation):

```bash
# Step 1-2: Sync main → dev
git checkout dev && git merge origin/main && git push origin dev

# Step 3: Sync dev → main
git checkout main && git pull origin main && \
  git merge --ff-only origin/dev && git push origin main

# Step 4: Create tag
git tag -a v0.X -m "Release v0.X" && git push origin v0.X

# Step 5: Bump version
# Edit: frontend/svelte-app/scripts/generate-version.js (version: '0.X')
node frontend/svelte-app/scripts/generate-version.js
git add frontend/svelte-app/scripts/generate-version.js
git commit -m "chore: bump version to 0.X" && git push origin main

# Step 6: Move tag
git tag -d v0.X && git push origin :refs/tags/v0.X
git tag -a v0.X -m "Release v0.X" && git push origin v0.X

# Step 7: Sync to dev
git checkout dev && git merge main --ff-only && git push origin dev
```

## Verification

After completing all steps, verify the final state:

```bash
# Check both branches are synchronized
git log --oneline --graph --all -5

# Verify tag points to correct commit
git show v0.X

# List recent tags
git tag --sort=-v:refname | head -5
```

**Expected result:** Both `main` and `dev` should be at the same commit with the tag `v0.X` pointing to that commit.

## Related Files

- **Version generator:** `frontend/svelte-app/scripts/generate-version.js`
- **Version documentation:** `CLAUDE.md` (Version Bumping section)
- **Generated version file:** `frontend/svelte-app/src/lib/version.js` (auto-generated, do not commit)

## Resources

For more information about the LAMB project's version bumping process, see the [Version Bumping section in CLAUDE.md](../../CLAUDE.md).
