# Phase 2 — Bugs y correcciones pendientes

Errores técnicos en el scaffold actual de `@lamb/ui` y `creator-app` que **impedirán el build** incluso después de ejecutar los 12 pasos de `MIGRATION_MONOREPO.md`.

> Estos NO son pasos de la migración (esos ya están cubiertos). Son bugs en los archivos ya creados.

---

## Frontend (`@lamb/ui`)

### BUG-F1: `$app/environment` en código de librería (3 archivos)

**Severidad**: Critical — rompe `pnpm -r build` de `@lamb/ui`

**Problema**: `$app/environment` es un módulo exclusivo de SvelteKit apps. Un paquete de librería construido con `svelte-package` no tiene acceso a él. El build de `@lamb/ui` fallará con un error de resolución de módulo.

**Archivos afectados**:
- `packages/ui/src/services/authService.js` (línea 1)
- `packages/ui/src/services/configService.js` (línea 1)
- `packages/ui/src/i18n/index.js` (línea 3)

**Fix**: Reemplazar `import { browser } from '$app/environment'` por:
```javascript
const browser = typeof window !== 'undefined';
```

- [ ] Corregido

---

### BUG-F2: `svelte-i18n` conflicto de versión major

**Severidad**: Medium — puede causar estado de i18n no compartido entre paquetes

**Problema**: 
- `@lamb/ui` declara `"svelte-i18n": "^3.7.4"` (v3)
- `creator-app` declara `"svelte-i18n": "^4.0.1"` (v4)

pnpm puede instalar dos versiones diferentes, causando que el singleton de i18n no se comparta entre `@lamb/ui` y `creator-app` (cada uno tendría su propia instancia).

**Fix**: Unificar a `"^4.0.1"` en `packages/ui/package.json`.

- [ ] Corregido

---

### BUG-F3: Export `./styles` apunta a archivo inexistente

**Severidad**: Low — rompe `import '@lamb/ui/styles'`

**Problema**: En `packages/ui/package.json`, el export:
```json
"./styles": "./src/styles/index.css"
```
Pero el archivo real es `theme.css`, no `index.css`.

**Fix**: Cambiar a `"./src/styles/theme.css"`.

- [ ] Corregido

---

### BUG-F4: `en.json` no es JSON válido

**Severidad**: Medium — rompe i18n runtime al intentar registrar base translations

**Problema**: `packages/ui/src/i18n/base/en.json` contiene texto plano:
```
Creating placeholder base i18n files. To be migrated from existing SVG, json files.
```
En vez de un objeto JSON vacío o con keys base.

**Fix**: Reemplazar por un JSON válido mínimo (se completará en Step 7 de MIGRATION_MONOREPO.md con las keys reales):
```json
{
  "common": {
    "save": "Save",
    "cancel": "Cancel",
    "delete": "Delete",
    "loading": "Loading..."
  }
}
```

- [ ] Corregido

---

### BUG-F5: Script `build` de `@lamb/ui` incluye `tsc` sin fuentes TypeScript

**Severidad**: Low — el build falla o es innecesario

**Problema**: En `packages/ui/package.json`:
```json
"build": "svelte-package && tsc"
```
Pero todo el source es `.js` (JavaScript con JSDoc, según CLAUDE.md). El paso `tsc` fallará o no hará nada útil.

**Fix**: Cambiar a `"build": "svelte-package"` (sin `tsc`). Si se quiere type-checking, usar `svelte-check` en un script `check` separado.

- [ ] Corregido

---

## Backend (módulos)

### BUG-B1: Module routers no se montan en la app

**Severidad**: Medium — no bloquea Phase 2 pero bloquea Phase 4

**Problema**: `ActivityModule.get_routers()` está definido en el ABC, y `ChatModule` devuelve `[]`. Pero **nada en `main.py`** recorre los módulos descubiertos para montar sus routers con `app.include_router()`. Cuando un módulo futuro (file_evaluation) devuelva routers reales, no se montarán.

**Fix**: Añadir en `main.py` (después de `discover_modules()`):
```python
from lamb.modules import get_all_modules

for module in get_all_modules():
    for router in module.get_routers():
        app.include_router(router, prefix=f"/lamb/v1/modules/{module.name}")
```

- [ ] Corregido

---

### BUG-B2: Import lazy inconsistente en `lti_router.py`

**Severidad**: Low — funciona pero es inconsistente

**Problema**: `get_all_modules` se importa a nivel de módulo (línea 26), pero `get_module` y `LTIContext` se importan dentro de la función handler (línea 152-153). No hay razón técnica para la diferencia.

**Fix**: Mover `get_module` y `LTIContext` al top-level import junto a `get_all_modules`.

- [ ] Corregido

---

## Resumen

| ID | Dónde | Severidad | Bloquea build | Esfuerzo |
|----|-------|-----------|---------------|----------|
| BUG-F1 | `@lamb/ui` services + i18n | Critical | Sí | 5 min |
| BUG-F2 | `@lamb/ui` package.json | Medium | Potencialmente | 1 min |
| BUG-F3 | `@lamb/ui` package.json | Low | Solo ese import | 1 min |
| BUG-F4 | `@lamb/ui` i18n/base/en.json | Medium | Runtime | 2 min |
| BUG-F5 | `@lamb/ui` package.json | Low | Build | 1 min |
| BUG-B1 | `backend/main.py` | Medium | Phase 4 | 5 min |
| BUG-B2 | `backend/lamb/lti_router.py` | Low | No | 2 min |

**Tiempo total estimado: ~15 minutos**
