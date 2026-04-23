# Frontend Svelte import audit — resultados (2026-04-23)

> Ejecución automática del plan de auditoría (grep estático + intento de build/check en CI local).

## 1. Comandos que requieren entorno sano (no ejecutables aquí)

| Comando | Resultado en este entorno | Qué debe hacer un humano en su máquina |
|--------|----------------------------|----------------------------------------|
| `cd lamb/frontend && npx pnpm@9 -r run build` | Falló: `EACCES` al escribir `creator-app/.../version.js`, `ENOENT` al generar `module-chat/.../version.js`, y Rollup `Cannot find module @rollup/rollup-linux-x64-gnu` en `module-file-eval` | `pnpm install` / reinstalar opcionales de Rollup; comprobar permisos y que existan `src/lib` de version si aplica |
| `pnpm --filter creator-app run check` | Mismo error de Rollup al cargar Vite/svelte-kit | Tras arreglar `node_modules`, vuelve a ejecutar `check` en `creator-app`, `module-chat`, `module-file-eval` |

**Conclusión:** no se pudo verificar con Vite en este worker; el análisis de imports se hizo **solo por búsqueda de código y existencia de ficheros**.

---

## 2. Búsquedas estáticas (OK)

- **`$lib/i18n` en `creator-app`:** 0 coincidencias (reemplazo correcto por `@lamb/ui` donde aplica).
- **`ConfirmationModal` vía ruta rota** (`$lib/components/modals/ConfirmationModal`): 0 en `creator-app`.
- **`from '$lib/...` en `packages/ui/src` (código):** 0 (evita resolución al paquete consumidor). Solo comentarios hacen referencia a `$lib` en comentarios de otros ficheros, no imports activos.
- **`module-chat` / `module-file-eval`:** sin `$lib/i18n` ni el patrón de ConfirmationModal roto.
- **`authService.fetchUserProfile`:** usa `GET /creator/me` (archivo: `lamb/frontend/packages/ui/src/lib/services/authService.js`).
- **Sesión (`replaceSessionWithLoginData`, `replaceSessionWithToken`):** solo se usan en `Login.svelte` y `+layout.svelte`, ambos con `import` desde `$lib/session/sessionManager`.
- **Rutas migradas (`agent/`, `libraries/`):** imports `$lib/...` apuntan a módulos que **existen** en disco (`services/aacService.js`, `services/libraryService.js`, modales y stores locales comprobados por glob).

## 3. Advertencias de packaging (@lamb/ui)

- El build de `ui` (cuando pudo avanzar) notificó: *SvelteKit-specific imports* sin declarar `@sveltejs/kit` en `dependencies`/`peerDependencies` del `package.json` de `ui`. Revisar si se quiere añadir `peerDependencies` para silenciar el aviso; no es un error de import en runtime del creator.

## 4. Riesgo residual (solo verificable con build)

- Cualquier import tipográfico o dependencia faltante que no coincida con los patrones buscados.
- Resolución `aacStore.svelte` → `aacStore.svelte.js`: en proyectos reales el resolver suele aceptar el sufijo; un build completo lo confirma.

## 5. Recomendación mínima para el repositorio

1. Tras arreglar `node_modules` y permisos, una sola pasada:  
   `cd lamb/frontend && pnpm -r run build && pnpm --filter creator-app --filter module-chat --filter module-file-eval run check`
2. Añadir esa línea a CI (si aún no está) para no reintroducir regresiones de imports.
