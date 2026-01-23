# LAMB Installation Guide

This guide provides a complete, step-by-step process for installing the LAMB application from scratch on a macOS-like environment. It is intended to be used by an automated agent.

**Core Strategy:**
The installation requires four separate, long-running terminal processes:

1.  **Open WebUI Server:** Runs on port `8080`.
2.  **LAMB Knowledge Base (KB) Server:** Runs on port `9090`.
3.  **Main LAMB Backend Server:** Runs on port `9099` (dev mode).
4.  **Frontend Svelte Dev Server:** Runs on port `5173`.

The production server is running on a Ubuntu 22.04 server.
You have access to the server via SSH (I have added my ssh key using ssh-add so you can forward it to the server using the -A flag). The sudo user is `ubuntu`.

The installation guide is for a macOS-like environment but should work on any Linux distribution.

If you ever need an OPENAI_API_KEY, you can get it running the following command:

```bash
llm keys get openai
```

---

### Step 1: Initial Directory Setup

First, create and set permissions for the main project directory.

```bash
# Create the main directory with administrator privileges
sudo mkdir -p $LAMB_PROJECT_PATH

# Change ownership of the directory to the current user to avoid using sudo later
sudo chown $(whoami) $LAMB_PROJECT_PATH

# Navigate into the new directory
cd $LAMB_PROJECT_PATH
```

### Step 2: Clone the Source Code Repository

Clone the project from GitHub into the directory created above.

```bash
# Clone the repository
git clone https://github.com/Lamb-Project/lamb.git

# Navigate into the project root
cd $LAMB_PROJECT_PATH
```

### Step 3: Configure and Launch Open WebUI (Terminal 1)

Note: The working Open WebUI version used in this setup is v0.5.6. If you build the Open WebUI frontend, check out tag v0.5.6 to match this environment.

**Instructions:** Open a new terminal for this component.

1.  **Navigate to the correct directory:**

    ```bash
    cd $LAMB_PROJECT_PATH/open-webui/backend
    ```

2.  **Create and activate the Python virtual environment:**

    ```bash
    uv venv
    source .venv/bin/activate
    ```

3.  **Create the required `data` directory (Fix from video):**

    ```bash
    mkdir -p data
    ```

4.  **Install Python dependencies:**

    ```bash
    uv pip install -r requirements.txt
    ```

5.  **Launch the server:** This process must be kept running.
    ```bash
    # Run from open-webui/backend (no need to cd into a dev folder)
    PORT=8080 ./dev.sh
    ```
    _Expect this server to be running on `http://0.0.0.0:8080`._

---

### Step 4: Configure and Launch LAMB KB Server (Terminal 2)

**Instructions:** Open a new terminal for this component.

1.  **Navigate to the correct directory:**

    ```bash
    cd $LAMB_PROJECT_PATH/lamb-kb-server-stable/backend
    ```

2.  **Create and activate the Python virtual environment:**

    ```bash
    uv venv
    source .venv/bin/activate
    ```

3.  **Fix dependencies in `requirements.txt` before installing (only if missing):**

    ```bash
    # Newer revisions already include these. If not present, apply:
    sed -i '' 's/langchain-text-splitters==0.7.0/langchain-text-splitters>=0.3.0,<0.4.0/' requirements.txt
    grep -q '^markdown2\b' requirements.txt || echo "markdown2" >> requirements.txt
    ```

4.  **Install the corrected Python dependencies:**

    ```bash
    uv pip install -r requirements.txt
    ```

5.  **Create the required `static` directory (Fix from video):**

    ```bash
    mkdir -p static
    ```

6.  **Create the environment configuration file:**

    ```bash
    cp .env.example .env
    ```

7.  **Launch the server:** This process must be kept running.
    ```bash
    python start.py
    ```
    _Expect this server to be running on `http://0.0.0.0:9090`._

---

### Step 5: Configure and Launch Main LAMB Backend (Terminal 3)

**Instructions:** Open a new terminal for this component.

1.  **Navigate to the correct directory:**

    ```bash
    cd $LAMB_PROJECT_PATH/backend
    ```

2.  **Create and activate the Python virtual environment:**

    ```bash
    uv venv
    source .venv/bin/activate
    ```

3.  **Install Python dependencies:**

    ```bash
    uv pip install -r requirements.txt
    ```

4.  **Create and configure the `.env` file:**

    ```bash
    # Create from the example
    cp .env.example .env

    # Point these to YOUR actual clone location
    # If you followed this guide exactly, use /opt/lamb-project/lamb
    # If you cloned elsewhere, set accordingly.
    REPO_ROOT="$LAMB_PROJECT_PATH" 

    # Set the absolute path for the Open WebUI database
    sed -i '' "s|^OWI_PATH=.*|OWI_PATH=\"${REPO_ROOT}/open-webui/backend/data\"|" .env

    # Set the absolute path for the main LAMB database
    sed -i '' "s|^LAMB_DB_PATH=.*|LAMB_DB_PATH=${REPO_ROOT}|" .env

    # Ensure OpenWebUI base URL matches the server above
    sed -i '' "s|^OWI_BASE_URL=.*|OWI_BASE_URL=\"http://localhost:8080\"|" .env
    ```

    - Add a valid `OPENAI_API_KEY` in `.env` (you can retrieve one via `llm keys get openai`).

5.  **Launch the server (dev mode):** This process must be kept running.
    ```bash
    ./dev.sh
    ```
    _Expect this server to be running on `http://127.0.0.1:9099` (docs at `/docs`)._

---

### Step 6: Configure and Launch Frontend (Terminal 4)

**Instructions:** Open a new terminal for this component.

1.  **Navigate to the frontend app directory:**

    ```bash
    cd $LAMB_PROJECT_PATH/frontend/svelte-app
    ```

2.  **Create the frontend configuration file from the sample:**

    ```bash
    cp static/config.js.sample static/config.js
    ```

    - Ensure the URLs match your running services:
      - `baseUrl: 'http://localhost:9099/creator'` ← use absolute URL to avoid 404s from the FE dev server
      - `lambServer: 'http://localhost:9099'`
      - `openWebUiServer: 'http://localhost:8080'` ← the sample ships with `8090`; change it to `8080`.

3.  **Use a supported Node.js version (required by Vite/Svelte):**

    ```bash
    # Recommended: Node LTS (>=18, 20 LTS works well)
    # If you have nvm installed:
    . "$HOME/.nvm/nvm.sh" && nvm install --lts=iron && nvm use --lts=iron
    node -v && npm -v
    ```

4.  **Install Node.js dependencies:**

    ```bash
    npm install
    ```

5.  **Launch the frontend development server:** This process must be kept running.
    ```bash
    npm run dev -- --host
    ```
    _The frontend will be available at `http://localhost:5173`._

---

### Step 7: Final Verification

1.  Open a web browser and navigate to `http://localhost:5173`.
2.  Log in using the credentials from `backend/.env` (`OWI_ADMIN_EMAIL`, `OWI_ADMIN_PASSWORD`). Defaults: `admin@owi.com` / `admin`.
3.  Quick health checks:
    - Open WebUI: `curl http://localhost:8080/health` → 200
    - KB Server: open `http://localhost:9090/docs`
    - Backend: open `http://localhost:9099/docs` and `curl http://localhost:9099/status` → `{ "status": true }`
4.  The application dashboard should load. All components are now running and communicating correctly.

---

### Step 8: Restarting Services

Use these commands to stop and start all four services cleanly on macOS/Linux.

Stop all services by port (safe to run even if a service isn't running):

```bash
lsof -ti tcp:8080 | xargs kill || true   # Open WebUI
lsof -ti tcp:9090 | xargs kill || true   # KB Server
lsof -ti tcp:9099 | xargs kill || true   # LAMB Backend
lsof -ti tcp:5173 | xargs kill || true   # Frontend
```

Start each service (one terminal per service):

```bash
cd $LAMB_PROJECT_PATH/open-webui/backend
source .venv/bin/activate
PORT=8080 ./dev.sh
```

```bash
cd $LAMB_PROJECT_PATH/lamb-kb-server-stable/backend
source .venv/bin/activate
python start.py
```

```bash
cd $LAMB_PROJECT_PATH/backend
source .venv/bin/activate
./dev.sh
```

```bash
cd $LAMB_PROJECT_PATH/frontend/svelte-app
. "$HOME/.nvm/nvm.sh" && nvm use --lts=iron
npm run dev -- --host
```

Optional: start all in the background (logs go to .dev.log in each folder):

```bash
(cd $LAMB_PROJECT_PATH/open-webui/backend && source .venv/bin/activate && PORT=8080 ./dev.sh > .dev.log 2>&1 &)
(cd $LAMB_PROJECT_PATH/lamb-kb-server-stable/backend && source .venv/bin/activate && python start.py > .dev.log 2>&1 &)
(cd $LAMB_PROJECT_PATH/backend && source .venv/bin/activate && ./dev.sh > .dev.log 2>&1 &)
(cd $LAMB_PROJECT_PATH/frontend/svelte-app && . "$HOME/.nvm/nvm.sh" && nvm use --lts=iron >/dev/null && npm run dev -- --host 0.0.0.0 > .dev.log 2>&1 &)
```

Verify after restart:

```bash
curl -fsS http://localhost:8080/health && echo "Open WebUI: OK"
curl -fsS http://localhost:9090/docs >/dev/null && echo "KB Server: OK"
curl -fsS http://localhost:9099/docs >/dev/null && echo "Backend Docs: OK"
curl -fsS http://localhost:9099/status && echo
```

View logs when started in background:

```bash
tail -n 100 -f $LAMB_PROJECT_PATH/open-webui/backend/.dev.log
tail -n 100 -f $LAMB_PROJECT_PATH/lamb-kb-server-stable/backend/.dev.log
tail -n 100 -f $LAMB_PROJECT_PATH/backend/.dev.log
tail -n 100 -f $LAMB_PROJECT_PATH/frontend/svelte-app/.dev.log
```

---

### Step 9: Build Open WebUI Frontend (optional)

You can build the Open WebUI frontend contained in this repo for a production bundle.

Prereqs:

- Node LTS (use nvm):

```bash
. "$HOME/.nvm/nvm.sh" && nvm install --lts=iron && nvm use --lts=iron
```

Build steps:

```bash
cd $LAMB_PROJECT_PATH/open-webui
npm install
npm run build
```

Preview the built app:

```bash
cd $LAMB_PROJECT_PATH/open-webui
npm run preview
```

Notes implemented in this repo to make the build succeed:

- Added `svelte.config.js` using the static adapter and vite preprocess so TypeScript in `.svelte` compiles:

```js
// open-webui/svelte.config.js
import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: "build",
      assets: "build",
      fallback: "index.html",
    }),
  },
};
```

- Added `vite.config.ts` to force workers to ESM format (fixes Rollup IIFE error for `pyodide.worker.ts`):

```ts
// open-webui/vite.config.ts
import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [sveltekit()],
  worker: { format: "es" },
});
```

Troubleshooting:

- Error: “Could not resolve entry module index.html” → ensure `svelte.config.js` exists as above.
- Error: “Invalid value "iife" for option output.format … worker” → ensure `worker.format = 'es'` in `vite.config.ts`.
- Error: vite not found → run with `npx vite build` or `npm run build` (uses local vite).

Troubleshooting notes (observed locally):

- Open WebUI may log warnings (frontend build missing, pyarrow/telemetry messages). API still runs on 8080.
- If `npm install` fails with "Unsupported engine", switch to Node LTS via `nvm` and retry.
- If you used a different clone path (e.g., `/opt/lamb-project/lamb`), update `OWI_PATH` and `LAMB_DB_PATH` in `backend/.env` accordingly.
