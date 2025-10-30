# Version Information System

## Overview

LAMB frontend automatically displays version information including the git commit hash in the footer and navigation bar.

## How It Works

1. **Version Generation Script**: `scripts/generate-version.js`
   - Runs automatically before `npm run dev` and `npm run build`
   - Extracts git information (commit hash, branch, date)
   - Generates `src/lib/version.js` with version data

2. **Version Display**:
   - **Footer**: Shows `v0.1 (eec3df3)` format
   - **Nav**: Shows `v0.1` badge
   - **Tooltip**: Hover over version for full details (version, commit, branch, build date)

3. **Generated File**: `src/lib/version.js`
   - Auto-generated (included in `.gitignore`)
   - Contains `VERSION_INFO` export with version data

## Usage

### Automatic (Recommended)

The version file is generated automatically during build:

```bash
npm run dev    # Generates version, then starts dev server
npm run build  # Generates version, then builds for production
```

### Manual Generation

Generate version info manually:

```bash
node scripts/generate-version.js
```

This is useful when:
- Running in Docker containers without git
- Need to refresh version info without rebuilding

## Docker Workflow

Since Docker containers (node:20-alpine) don't have git installed:

1. Generate version file on host machine before starting containers:
   ```bash
   cd /opt/lamb/frontend/svelte-app
   node scripts/generate-version.js
   ```

2. The file is volume-mounted into containers
3. Containers use the pre-generated version file

## Version File Format

```javascript
export const VERSION_INFO = {
  "version": "0.1",           // Semantic version
  "commit": "eec3df3",        // Short git commit hash
  "branch": "dev",            // Current git branch
  "commitDate": "2025-10-30", // Last commit date
  "buildDate": "2025-10-30"   // Build/generation date
};
```

## Fallback Behavior

If git is not available (e.g., in Docker):
- `commit`: "unknown"
- `branch`: "unknown"
- `commitDate`: "unknown"
- Script exits with warning but continues build

## Updating Version

To update the displayed version number:

1. Edit `scripts/generate-version.js`:
   ```javascript
   const version = {
     version: '0.2',  // Change this
     // ...
   };
   ```

2. Regenerate version file:
   ```bash
   node scripts/generate-version.js
   ```

## Components Using Version Info

- `src/lib/components/Footer.svelte` - Footer display
- `src/lib/components/Nav.svelte` - Navigation badge
- Any component can import: `import { VERSION_INFO } from '$lib/version.js';`
