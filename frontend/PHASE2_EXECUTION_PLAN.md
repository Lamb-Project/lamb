# Plan de ejecución: Phases 1-2 — Bugs + Migración Monorepo

> Estado actual: scaffold creado (packages/ui/ y packages/creator-app/ con configs), svelte-app/ intacta funcionando.
> Este documento es el plan paso a paso para ejecutar la migración.

---

## Parte 0 — Entender qué hay y por qué

### ¿Qué archivos necesita cada package de pnpm?

Un package de pnpm es simplemente una carpeta con `package.json`. Pero según su tipo necesita cosas distintas:

#### `@lamb/ui` (librería — no es una app web)

```
packages/ui/
├── package.json        ← OBLIGATORIO: nombre, exports, dependencias
├── src/                ← Código fuente: componentes, stores, services
│   ├── index.js        ← Punto de entrada que re-exporta todo
│   ├── components/     ← Svelte components compartidos
│   ├── stores/         ← Stores compartidos (userStore, configStore)
│   ├── services/       ← Services compartidos (auth, config)
│   ├── i18n/           ← Setup de i18n + traducciones base
│   └── styles/         ← CSS compartido (theme)
└── [opcional] tsconfig.json, .gitignore, .prettierrc
```

La clave de `package.json` → `"exports"` dice qué se puede importar:
```json
"exports": { ".": "./src/index.js" }
// permite: import { Nav, userStore } from '@lamb/ui'
```

**No se compila a `dist/` todavía** — Vite en las apps consumidoras la resuelve directamente desde `src/`. El campo `"svelte": "./src/index.js"` le dice a Vite que trate el source como código Svelte.

#### `creator-app` (app SvelteKit — sí es una app web)

```
packages/creator-app/
├── package.json        ← OBLIGATORIO: nombre, scripts (dev/build), dependencias
├── svelte.config.js    ← OBLIGATORIO: configura el adapter (dónde va el build output)
├── vite.config.js      ← OBLIGATORIO: plugins, proxy de dev, optimizeDeps
├── jsconfig.json       ← Necesario: aliases ($lib, $components), type checking
├── src/                ← OBLIGATORIO: todo el código de la app
│   ├── routes/         ← Páginas de SvelteKit
│   ├── lib/            ← Componentes, services, stores, locales
│   ├── app.html        ← Template HTML base
│   ├── app.css         ← Estilos globales
│   └── hooks.server.js ← Hooks de servidor SvelteKit
├── static/             ← Assets estáticos (favicon, config.js, imágenes)
├── scripts/            ← generate-version.js
└── [config] .prettierrc, .prettierignore, .gitignore, eslint.config.js
```

### ¿De dónde sale el código?

**Todo sale de `svelte-app/`** — es copia directa. El scaffold que creó tu compañero solo preparó los archivos de configuración (`package.json`, `svelte.config.js`, `vite.config.js`), no el código fuente.

### ¿Es copia 1:1?

Casi. El source (`src/`, `static/`, `scripts/`) se copia tal cual. Las diferencias son:

| Archivo | svelte-app | creator-app (scaffold) | Diferencia |
|---------|-----------|------------------------|------------|
| `svelte.config.js` | `pages: '../build'` | `pages: '../../build'` | Ruta relativa cambia por estar un nivel más profundo |
| `vite.config.js` | No tiene `@lamb/ui` | Tiene `@lamb/ui` en optimizeDeps y noExternal | Añade soporte para la librería compartida |
| `package.json` | No tiene `@lamb/ui` | Tiene `"@lamb/ui": "workspace:*"` | Enlaza la librería local |
| `.prettierrc` | Contenido completo | `"extends": "../../.prettierrc"` | Hereda de un root que NO EXISTE todavía |
| `eslint.config.js` | Existe | **NO EXISTE** en el scaffold | Falta |
| `vitest-setup-client.js` | Existe | **NO EXISTE** | Falta |

---

## Parte 1 — Corregir bugs del scaffold (ANTES de migrar)

> Estos son errores en archivos ya creados que romperán el build. Se corrigen primero.

### 1.1 — BUG-F1: Quitar `$app/environment` de `@lamb/ui`

`$app/environment` solo funciona dentro de una app SvelteKit, no en una librería. Hay que cambiarlo en 3 archivos:

**Archivos:**
- `packages/ui/src/services/authService.js` (línea 1)
- `packages/ui/src/services/configService.js` (línea 1)
- `packages/ui/src/i18n/index.js` (línea 3)

**Cambio:** Reemplazar:
```javascript
import { browser } from '$app/environment';
```
Por:
```javascript
const browser = typeof window !== 'undefined';
```

- [ ] Corregido

### 1.2 — BUG-F2: Unificar versión de `svelte-i18n`

**Archivo:** `packages/ui/package.json`

**Cambio:** En `dependencies`, cambiar:
```json
"svelte-i18n": "^3.7.4"
```
A:
```json
"svelte-i18n": "^4.0.1"
```
(Para que coincida con la versión de `creator-app` y de `svelte-app`)

- [ ] Corregido

### 1.3 — BUG-F3: Corregir export de styles

**Archivo:** `packages/ui/package.json`

**Cambio:** En `exports`, cambiar:
```json
"./styles": "./src/styles/index.css"
```
A:
```json
"./styles": "./src/styles/theme.css"
```

- [ ] Corregido

### 1.4 — BUG-F4: Reemplazar en.json inválido

**Archivo:** `packages/ui/src/i18n/base/en.json`

**Cambio:** Reemplazar el texto plano por JSON válido mínimo:
```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "loading": "Loading...",
    "error": "Error",
    "ok": "OK"
  }
}
```
(Se completará con keys reales cuando se extraigan los locales en la Parte 2)

- [ ] Corregido

### 1.5 — BUG-F5: Quitar `tsc` del build de `@lamb/ui`

**Archivo:** `packages/ui/package.json`

**Cambio:** En `scripts`, cambiar:
```json
"build": "svelte-package && tsc"
```
A:
```json
"build": "svelte-package"
```

- [ ] Corregido

### 1.6 — BUG-F6: `.prettierrc` de creator-app referencia root inexistente

**Archivo:** `packages/creator-app/.prettierrc`

Actualmente contiene `"extends": "../../.prettierrc"` pero no existe `frontend/.prettierrc`.

**Cambio:** Reemplazar por el contenido real de `svelte-app/.prettierrc`:
```json
{
  "useTabs": true,
  "singleQuote": true,
  "trailingComma": "none",
  "printWidth": 100,
  "plugins": ["prettier-plugin-svelte", "prettier-plugin-tailwindcss"],
  "overrides": [
    {
      "files": "*.svelte",
      "options": {
        "parser": "svelte"
      }
    }
  ]
}
```

- [ ] Corregido

### 1.7 — BUG-F7: `.npmrc` de creator-app tiene contenido incorrecto

**Archivo:** `packages/creator-app/.npmrc`

Actualmente contiene líneas de `.gitignore` (`node_modules`, `.DS_Store`). Debería ser igual que `svelte-app/.npmrc`:
```
engine-strict=true
```

- [ ] Corregido

### 1.8 — BUG-B1: Montar module routers en main.py

**Archivo:** `backend/main.py`

Después de `discover_modules()` en el lifespan, añadir:
```python
from lamb.modules import get_all_modules
for module in get_all_modules():
    for router in module.get_routers():
        app.include_router(router, prefix=f"/lamb/v1/modules/{module.name}")
```

> No afecta a nada hoy (ChatModule devuelve []) pero es necesario para Phase 4.

- [ ] Corregido

### 1.9 — BUG-B2: Import consistente en lti_router.py

**Archivo:** `backend/lamb/lti_router.py`

Mover los imports de línea 152-153 al top del archivo junto a `get_all_modules` (línea 26):
```python
from lamb.modules import get_all_modules, get_module
from lamb.modules.base import LTIContext
```

Y eliminar los `from lamb.modules import get_module` / `from lamb.modules.base import LTIContext` dentro de la función.

- [ ] Corregido

---

## Parte 2 — Migración del código (la migración real)

> Ahora sí, mover svelte-app a creator-app dentro del monorepo.

### 2.1 — Copiar el source completo

```bash
cd frontend

# Copiar código fuente
cp -r svelte-app/src/* packages/creator-app/src/

# Copiar assets estáticos
cp -r svelte-app/static packages/creator-app/

# Copiar scripts de build
cp -r svelte-app/scripts packages/creator-app/

# Copiar archivos de config que faltan en el scaffold
cp svelte-app/eslint.config.js packages/creator-app/
cp svelte-app/vitest-setup-client.js packages/creator-app/
```

**¿Qué NO copiar?**
- `node_modules/` — se regenera con `pnpm install`
- `.svelte-kit/` — se regenera automáticamente
- `package-lock.json` — pnpm usa su propio lockfile
- `.dev.pid`, `stream.txt` — archivos temporales

- [ ] Completado

### 2.2 — Verificar archivos de config del scaffold vs originales

Después de copiar el source, estos archivos del scaffold ya están adaptados para monorepo y **NO deben sobrescribirse**:

| Archivo scaffold | ¿Sobrescribir con el de svelte-app? | Por qué |
|---|---|---|
| `package.json` | **NO** | Ya tiene `@lamb/ui` y scripts adaptados |
| `svelte.config.js` | **NO** | Ya tiene `pages: '../../build'` (ruta monorepo) |
| `vite.config.js` | **NO, pero revisar** | Tiene `@lamb/ui` en optimizeDeps. Falta el workspace de vitest `server` — ver paso 2.3 |
| `jsconfig.json` | **NO** | Igual al original (sin custom aliases de svelte.config) |
| `.gitignore` | **NO** | Suficiente |
| `.prettierignore` | **NO** | Suficiente |

Estos SÍ se copiaron en 2.1 porque no existían en el scaffold:
| Archivo | Copiado de svelte-app |
|---|---|
| `eslint.config.js` | ✅ |
| `vitest-setup-client.js` | ✅ |

- [ ] Verificado

### 2.3 — Actualizar vite.config.js con workspace de vitest faltante

El `vite.config.js` del scaffold solo tiene el workspace de test `client`. El original de svelte-app tiene además un workspace `server` y un `setupFiles` en client. Añadir lo que falta.

**Archivo:** `packages/creator-app/vite.config.js`

Actualizar la sección `test.workspace` para que incluya:
```javascript
test: {
    workspace: [
        {
            extends: './vite.config.js',
            plugins: [svelteTesting()],
            test: {
                name: 'client',
                environment: 'jsdom',
                clearMocks: true,
                include: ['src/**/*.svelte.{test,spec}.{js,ts}'],
                exclude: ['src/lib/server/**'],
                setupFiles: ['./vitest-setup-client.js']
            }
        },
        {
            extends: './vite.config.js',
            test: {
                name: 'server',
                environment: 'node',
                include: ['src/**/*.{test,spec}.{js,ts}'],
                exclude: ['src/**/*.svelte.{test,spec}.{js,ts}']
            }
        }
    ]
}
```

- [ ] Completado

### 2.4 — Instalar dependencias

```bash
cd frontend
pnpm install
```

Esto:
1. Instala las dependencias de `@lamb/ui`
2. Instala las dependencias de `creator-app`
3. Crea un symlink de `@lamb/ui` → `packages/ui/` dentro de `creator-app/node_modules/`

Si `pnpm` no está instalado:
```bash
npm install -g pnpm
```

- [ ] Completado

### 2.5 — Verificar que el build funciona TAL CUAL (sin cambiar imports)

```bash
cd frontend
pnpm --filter creator-app build
```

El objetivo es que `creator-app` compile exactamente como lo hacía `svelte-app`, sin tocar ningún import todavía. El código sigue usando `$lib/stores/userStore.js`, `$lib/services/authService.js`, etc. — y eso está bien porque esos archivos se copiaron en 2.1.

**Si falla,** comprobar:
- Que `src/app.html` existe
- Que `static/config.js` existe (o copiar `config.js.sample` a `config.js`)
- Que las rutas en `svelte.config.js` son correctas

**Si compila, verificar:**
```bash
ls -la frontend/build/
# Debe contener index.html, app/, archivos JS/CSS
```

- [ ] Build OK

### 2.6 — Verificar dev mode

```bash
cd frontend/packages/creator-app
pnpm run dev
```

Acceder a `http://localhost:5173` — debe verse la app igual que antes.

- [ ] Dev mode OK

---

## Parte 3 — Extraer código compartido a `@lamb/ui` (DESPUÉS de que funcione)

> Solo hacer esto cuando la Parte 2 esté verde. Esta parte es opcional para que Phase 2 funcione — se puede hacer gradualmente.

### 3.1 — Copiar componentes compartidos al package ui

```bash
cd frontend

# Copiar los componentes reales (reemplazando los stubs vacíos)
cp svelte-app/src/lib/components/Nav.svelte packages/ui/src/components/
cp svelte-app/src/lib/components/Footer.svelte packages/ui/src/components/
cp svelte-app/src/lib/components/LanguageSelector.svelte packages/ui/src/components/
```

> IMPORTANTE: Estos componentes probablemente importen de `$lib/...` internamente. Necesitarás revisar sus imports para que funcionen desde `@lamb/ui` (sin acceso a `$lib`). Solo mover los que no tengan dependencias profundas del creator-app, o adaptarlos.

- [ ] Completado

### 3.2 — Reemplazar userStore en @lamb/ui con el real

El `userStore.js` en `packages/ui/src/stores/` es un placeholder simplificado (20 líneas). El real en `svelte-app/src/lib/stores/userStore.js` tiene 158 líneas con localStorage, login, logout, etc.

**Opción A (recomendada por ahora):** No mover todavía. Dejar que `creator-app` use su propio `$lib/stores/userStore.js` copiado en 2.1. Mover stores a `@lamb/ui` cuando realmente haya un segundo consumidor (module-chat).

**Opción B:** Copiar el real, pero hay que cambiar `import { browser } from '$app/environment'` por `const browser = typeof window !== 'undefined'` (mismo bug que BUG-F1).

- [ ] Decidido qué opción

### 3.3 — Extraer traducciones base a @lamb/ui

Revisar `svelte-app/src/lib/locales/en.json` e identificar keys comunes (`common.*`, `auth.*`, `nav.*`). Copiar solo esas a `packages/ui/src/i18n/base/en.json`. Repetir para `es.json`, `ca.json`, `eu.json`.

> Esto es trabajo manual de curación de keys. No es urgente — el sistema funciona sin extraerlas.

- [ ] Completado (o pospuesto a cuando haya segundo consumidor)

---

## Parte 4 — Actualizar Docker / CI

> Solo necesario si usas Docker o CI para compilar el frontend.

### 4.1 — Actualizar docker-compose

En los archivos `docker-compose-example.yaml` y `docker-compose-workers.yaml`:

**Servicio `frontend-build`:**
```yaml
# ANTES:
working_dir: ${LAMB_PROJECT_PATH}/frontend/svelte-app
command: sh -lc "npm install && npm run build"

# DESPUÉS:
working_dir: ${LAMB_PROJECT_PATH}/frontend
command: sh -lc "npm install -g pnpm && pnpm install && pnpm --filter creator-app build"
```

**Servicio `frontend` (dev mode):**
```yaml
# ANTES:
working_dir: ${LAMB_PROJECT_PATH}/frontend/svelte-app
command: sh -lc "... npm run dev -- --host 0.0.0.0"

# DESPUÉS:
working_dir: ${LAMB_PROJECT_PATH}/frontend
command: sh -lc "npm install -g pnpm && pnpm install && pnpm --filter creator-app dev -- --host 0.0.0.0"
```

> NOTA: Las líneas de `mkdir` y `cp` de static assets dentro del command del servicio `frontend` siguen funcionando porque usan rutas absolutas a `frontend/build/`.

- [ ] Completado

### 4.2 — Verificar que el backend sigue sirviendo correctamente

El build output sigue siendo `frontend/build/`. El backend (`main.py`) no necesita cambios.

```bash
# Verificar
ls frontend/build/index.html
```

- [ ] Verificado

---

## Resumen de archivos: qué se creó, qué se copia, qué se modifica

### Archivos del scaffold que SÍ son necesarios y están bien:
| Archivo | Para qué sirve |
|---|---|
| `pnpm-workspace.yaml` | Le dice a pnpm dónde están los packages |
| `packages/ui/package.json` | Define `@lamb/ui` como paquete (exports, dependencias) |
| `packages/ui/src/index.js` | Punto de entrada de la librería |
| `packages/ui/src/stores/` | Placeholders de stores compartidos |
| `packages/ui/src/services/` | Placeholders de services compartidos |
| `packages/ui/src/i18n/` | Setup de i18n compartido |
| `packages/ui/src/components/index.js` | Re-exports de componentes (apuntará a los reales después de 3.1) |
| `packages/creator-app/package.json` | Define la app con `@lamb/ui` como dependencia workspace |
| `packages/creator-app/svelte.config.js` | Adapter con ruta corregida `../../build` |
| `packages/creator-app/vite.config.js` | Proxy + soporte para `@lamb/ui` |
| `packages/creator-app/jsconfig.json` | Igual que el original |

### Archivos del scaffold que tienen bugs (corregir en Parte 1):
| Archivo | Bug |
|---|---|
| `packages/ui/src/services/authService.js` | `$app/environment` |
| `packages/ui/src/services/configService.js` | `$app/environment` |
| `packages/ui/src/i18n/index.js` | `$app/environment` |
| `packages/ui/package.json` | svelte-i18n ^3 (debe ser ^4), export styles apunta a index.css, build con tsc |
| `packages/ui/src/i18n/base/en.json` | No es JSON válido |
| `packages/creator-app/.prettierrc` | Extiende root inexistente |
| `packages/creator-app/.npmrc` | Contenido incorrecto |

### Archivos que NO están en el scaffold y se copian de svelte-app:
| Archivo | Destino |
|---|---|
| `src/*` (routes, lib, app.css, app.html, hooks.server.js) | `packages/creator-app/src/` |
| `static/*` | `packages/creator-app/static/` |
| `scripts/generate-version.js` | `packages/creator-app/scripts/` |
| `eslint.config.js` | `packages/creator-app/` |
| `vitest-setup-client.js` | `packages/creator-app/` |

### Archivos que NO hay que copiar/sobrescribir:
| Archivo | Por qué |
|---|---|
| `svelte-app/package.json` | El scaffold ya tiene uno adaptado |
| `svelte-app/svelte.config.js` | El scaffold tiene la ruta `../../build` corregida |
| `svelte-app/vite.config.js` | El scaffold incluye `@lamb/ui` (pero actualizar vitest config) |
| `svelte-app/node_modules/` | Se regenera |
| `svelte-app/.svelte-kit/` | Se regenera |
| `svelte-app/package-lock.json` | pnpm usa pnpm-lock.yaml |

---

## Checklist final

### Parte 1 — Bugs (15 min)
- [ ] 1.1 — `$app/environment` → `typeof window` en 3 archivos de @lamb/ui
- [ ] 1.2 — svelte-i18n ^3 → ^4 en @lamb/ui
- [ ] 1.3 — export styles: index.css → theme.css
- [ ] 1.4 — en.json con JSON válido
- [ ] 1.5 — Quitar tsc del build
- [ ] 1.6 — .prettierrc con contenido real
- [ ] 1.7 — .npmrc con contenido correcto
- [ ] 1.8 — Montar module routers en main.py
- [ ] 1.9 — Imports consistentes en lti_router.py

### Parte 2 — Migración (30 min)
- [ ] 2.1 — Copiar src/, static/, scripts/, eslint, vitest-setup
- [ ] 2.2 — Verificar que no se sobrescriben configs del scaffold
- [ ] 2.3 — Actualizar vitest config en vite.config.js
- [ ] 2.4 — pnpm install
- [ ] 2.5 — Build funciona
- [ ] 2.6 — Dev mode funciona

### Parte 3 — Extraer a @lamb/ui (opcional, gradual)
- [ ] 3.1 — Mover Nav, Footer, LanguageSelector
- [ ] 3.2 — Decidir qué stores mover
- [ ] 3.3 — Extraer traducciones base

### Parte 4 — Docker/CI
- [ ] 4.1 — Actualizar docker-compose
- [ ] 4.2 — Verificar backend sirve build

---

## Orden de ejecución recomendado

```
Parte 1 (bugs)  →  Parte 2 (migración)  →  verificar que todo funciona
                                             │
                                 ┌───────────┴───────────┐
                                 │                       │
                          Parte 3 (opcional)      Parte 4 (si usas Docker)
                          extraer a @lamb/ui      actualizar compose
```

La Parte 3 se puede hacer gradualmente — no es necesaria para que funcione. El sistema funciona perfectamente con todo en `creator-app` y `@lamb/ui` con placeholders. La extracción real a `@lamb/ui` tiene valor cuando exista un segundo consumidor (Phase 3: module-chat).
