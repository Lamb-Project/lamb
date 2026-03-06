# Cambios Docker y despliegue — Migración Monorepo

> Este documento explica TODOS los cambios necesarios en Docker, docker-compose, Caddy y backend relacionados con mover el frontend de `svelte-app/` al monorepo `packages/creator-app/`.

---

## Resumen rápido

| Cosa | ¿Cambia? | Por qué |
|------|----------|---------|
| **Output de build** (`frontend/build/`) | **NO** | creator-app compila al mismo sitio |
| **Backend** (`main.py`) | **NO** | Sigue sirviendo `../frontend/build` igual |
| **Caddy** (`Caddyfile`) | **NO** | Sirve `/var/www/frontend` (= `frontend/build/`) |
| **docker-compose `frontend-build`** | **SÍ** | Cambia working_dir y comando de build |
| **docker-compose `frontend` (dev)** | **SÍ** | Cambia working_dir y comando de dev |
| **docker-compose.prod.yaml** | **NO** | Solo monta `frontend/build` como volumen |

---

## Ficheros afectados

### 1. `docker-compose-example.yaml`

Tiene 2 servicios a cambiar: `frontend-build` y `frontend`.

#### Servicio `frontend-build` (compila la SPA)

```yaml
# ─── ANTES ───
  frontend-build:
    image: node:20-alpine
    working_dir: ${LAMB_PROJECT_PATH}/frontend/svelte-app
    volumes:
      - ${LAMB_PROJECT_PATH}:${LAMB_PROJECT_PATH}
    command: >
      sh -lc "apk add --no-cache git && \
      git config --global --add safe.directory ${LAMB_PROJECT_PATH} && \
      npm install && npm run build"

# ─── DESPUÉS ───
  frontend-build:
    image: node:20-alpine
    working_dir: ${LAMB_PROJECT_PATH}/frontend
    volumes:
      - ${LAMB_PROJECT_PATH}:${LAMB_PROJECT_PATH}
    command: >
      sh -lc "apk add --no-cache git && \
      git config --global --add safe.directory ${LAMB_PROJECT_PATH} && \
      npm install -g pnpm && pnpm install && pnpm --filter creator-app build"
```

**Cambios:**
1. `working_dir`: `frontend/svelte-app` → `frontend` (raíz del monorepo)
2. `command`: `npm install && npm run build` → `npm install -g pnpm && pnpm install && pnpm --filter creator-app build`

**Por qué `npm install -g pnpm` primero:** La imagen `node:20-alpine` trae npm pero no pnpm. Se instala pnpm globalmente y luego se usa para instalar dependencias del workspace y compilar.

**El output no cambia:** `pnpm --filter creator-app build` ejecuta el build de `packages/creator-app/`, que usa `svelte.config.js` con `pages: '../../build'` → genera `frontend/build/` exactamente igual que antes.

---

#### Servicio `frontend` (dev server con hot reload)

```yaml
# ─── ANTES ───
  frontend:
    image: node:20-alpine
    working_dir: ${LAMB_PROJECT_PATH}/frontend/svelte-app
    environment:
      - HOST=0.0.0.0
      - PROXY_TARGET=http://backend:9099
    volumes:
      - ${LAMB_PROJECT_PATH}:${LAMB_PROJECT_PATH}
    ports:
      - "5173:5173"
    depends_on:
      backend:
        condition: service_started
      frontend-build:
        condition: service_completed_successfully
    command: >
      sh -lc "apk add --no-cache git && \
      git config --global --add safe.directory ${LAMB_PROJECT_PATH} && \
      test -f static/config.js || cp static/config.js.sample static/config.js; \
      mkdir -p ${LAMB_PROJECT_PATH}/frontend/build/static/img && \
      mkdir -p ${LAMB_PROJECT_PATH}/frontend/build/static/md && \
      cp ${LAMB_PROJECT_PATH}/backend/static/img/lamb_icon.png ${LAMB_PROJECT_PATH}/frontend/build/static/img/ && \
      cp ${LAMB_PROJECT_PATH}/backend/static/md/lamb-news.md ${LAMB_PROJECT_PATH}/frontend/build/static/md/ && \
      npm run dev -- --host 0.0.0.0"

# ─── DESPUÉS ───
  frontend:
    image: node:20-alpine
    working_dir: ${LAMB_PROJECT_PATH}/frontend
    environment:
      - HOST=0.0.0.0
      - PROXY_TARGET=http://backend:9099
    volumes:
      - ${LAMB_PROJECT_PATH}:${LAMB_PROJECT_PATH}
    ports:
      - "5173:5173"
    depends_on:
      backend:
        condition: service_started
      frontend-build:
        condition: service_completed_successfully
    command: >
      sh -lc "apk add --no-cache git && \
      git config --global --add safe.directory ${LAMB_PROJECT_PATH} && \
      npm install -g pnpm && pnpm install && \
      test -f packages/creator-app/static/config.js || cp packages/creator-app/static/config.js.sample packages/creator-app/static/config.js; \
      mkdir -p ${LAMB_PROJECT_PATH}/frontend/build/static/img && \
      mkdir -p ${LAMB_PROJECT_PATH}/frontend/build/static/md && \
      cp ${LAMB_PROJECT_PATH}/backend/static/img/lamb_icon.png ${LAMB_PROJECT_PATH}/frontend/build/static/img/ && \
      cp ${LAMB_PROJECT_PATH}/backend/static/md/lamb-news.md ${LAMB_PROJECT_PATH}/frontend/build/static/md/ && \
      pnpm --filter creator-app dev -- --host 0.0.0.0"
```

**Cambios:**
1. `working_dir`: `frontend/svelte-app` → `frontend`
2. `command`:
   - Añadir `npm install -g pnpm && pnpm install` antes de todo
   - Ruta de `config.js`: `static/config.js` → `packages/creator-app/static/config.js`
   - Dev: `npm run dev -- --host 0.0.0.0` → `pnpm --filter creator-app dev -- --host 0.0.0.0`
3. Las líneas de `mkdir -p` y `cp` para static assets **no cambian** — usan rutas absolutas a `frontend/build/`

---

### 2. `docker-compose-workers.yaml`

**Exactamente los mismos cambios** que en `docker-compose-example.yaml`. Es una copia del example con workers habilitados (uvicorn con `--workers 4`). Los servicios `frontend-build` y `frontend` son idénticos.

---

### 3. `docker-compose.prod.yaml`

**NO necesita cambios.** Solo monta el volumen del build:
```yaml
- ${LAMB_PROJECT_PATH}/frontend/build:/var/www/frontend:ro
```
La ruta `frontend/build/` no cambia.

---

### 4. `Caddyfile`

**NO necesita cambios.** Caddy sirve archivos estáticos desde `/var/www/frontend` (que es `frontend/build/` montado por docker-compose.prod.yaml). La SPA sigue funcionando con el catch-all `try_files {path} /index.html`.

---

### 5. `backend/main.py`

**NO necesita cambios.** El backend sirve el frontend desde:
```python
frontend_build_dir = "../frontend/build"
```
Esta ruta es relativa a `backend/main.py` y apunta a la misma carpeta de siempre. No importa si el build vino de `svelte-app` o de `packages/creator-app` — el output es idéntico.

---

## Desarrollo local (sin Docker)

### Antes
```bash
cd frontend/svelte-app
npm install
npm run dev          # dev server en localhost:5173
npm run build        # genera frontend/build/
```

### Después
```bash
cd frontend
pnpm install         # instala todo el workspace
pnpm --filter creator-app dev    # dev server en localhost:5173
pnpm --filter creator-app build  # genera frontend/build/
```

O equivalente entrando al directorio:
```bash
cd frontend/packages/creator-app
pnpm dev             # también funciona desde dentro del package
pnpm build
```

---

## Diagrama de flujo de build

```
                                Docker                          Local
                                  │                               │
                    ┌─────────────┴────────────┐    ┌─────────────┴─────────────┐
                    │    frontend-build         │    │   developer machine       │
                    │    (node:20-alpine)       │    │                           │
                    │                           │    │                           │
                    │  working_dir: frontend/   │    │  cd frontend/             │
                    │                           │    │                           │
                    │  npm install -g pnpm      │    │  pnpm install             │
                    │  pnpm install             │    │  pnpm --filter            │
                    │  pnpm --filter            │    │    creator-app build      │
                    │    creator-app build      │    │                           │
                    └─────────────┬────────────┘    └─────────────┬─────────────┘
                                  │                               │
                                  ▼                               ▼
                          frontend/build/                  frontend/build/
                          ├── index.html                   (mismo output)
                          ├── app/
                          ├── favicon.png
                          └── config.js
                                  │
                    ┌─────────────┼──────────────────┐
                    │             │                   │
                    ▼             ▼                   ▼
              backend/main.py  Caddy              Caddy (prod)
              (dev: sirve     (prod: sirve        monta como
               ../frontend/   /var/www/frontend)  volumen :ro)
               build/)
```

---

## Tabla de verificación

Después de hacer los cambios, verificar:

| Check | Comando | Esperar |
|-------|---------|---------|
| Build con Docker funciona | `docker compose up frontend-build` | Compila sin errores, sale con exit 0 |
| `frontend/build/` tiene contenido | `ls frontend/build/index.html` | Existe |
| Dev server con Docker funciona | `docker compose up frontend` | Accesible en `localhost:5173` |
| Backend sirve la SPA | `docker compose up backend` + navegar a `localhost:9099` | Carga la app |
| Caddy en prod sirve | `docker compose -f docker-compose.prod.yaml up caddy` | Sirve la SPA correctamente |

---

## Cosas que NO cambian (para tranquilidad)

- La carpeta `frontend/build/` se genera en el mismo sitio
- El contenido del build es idéntico byte a byte
- Backend no necesita cambios — sirve la misma carpeta
- Caddy no necesita cambios — sirve el mismo volumen
- Las rutas de proxy del dev server (`/creator`, `/lamb`, `/static`) son las mismas
- El puerto 5173 del dev server es el mismo
- Los assets estáticos copiados a `frontend/build/static/` funcionan igual

---

## Posible optimización futura

La línea `npm install -g pnpm` se ejecuta cada vez que el contenedor se crea (los contenedores de Docker Compose son efímeros). Si esto molesta por tiempo, se puede:

1. **Crear una imagen custom** con pnpm preinstalado:
   ```dockerfile
   FROM node:20-alpine
   RUN npm install -g pnpm
   ```
   Y usarla en vez de `node:20-alpine`.

2. **O usar corepack** (viene con Node 20):
   ```yaml
   command: >
     sh -lc "corepack enable && corepack prepare pnpm@latest --activate && \
     pnpm install && pnpm --filter creator-app build"
   ```
   Esto no requiere `npm install -g pnpm`.

Esto es opcional — `npm install -g pnpm` añade ~5 segundos y funciona perfectamente.
