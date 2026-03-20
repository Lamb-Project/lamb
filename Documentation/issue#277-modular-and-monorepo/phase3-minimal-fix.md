# Phase 3 — Cambios Mínimos para que `/m/chat/` Funcione

> **Contexto:** Tras implementar la Phase 3 (Chat Module Frontend como SvelteKit SPA),
> la ruta `/m/chat/setup` devolvía 404 o página en blanco.

## Resumen del Problema Original

El backend redirige a `/m/chat/setup?token=...` tras un LTI launch como instructor.
El backend ya tenía el código para servir `frontend/build/m/chat/index.html` como SPA fallback.
Pero la página se quedaba en blanco porque:

1. **No existía** `frontend/build/m/chat/` — el build iba a otra carpeta
2. **Se borraba** durante el build paralelo — creator-app limpiaba todo
3. **Las rutas de assets eran incorrectas** — apuntaban a `/app/immutable/...` en vez de `/m/chat/app/immutable/...`

---

## Los 3 Cambios Necesarios

### 1. Corregir la ruta de salida del adapter-static

**Problema:** `../build` desde `packages/module-chat/` resuelve a `packages/build/` (directorio equivocado).
El backend busca en `frontend/build/`.

**Archivos:**
- `frontend/packages/module-chat/svelte.config.js`
- `frontend/packages/creator-app/svelte.config.js`

```diff
 // module-chat/svelte.config.js
 adapter: adapter({
-    pages: '../build/m/chat',
-    assets: '../build/m/chat',
+    pages: '../../build/m/chat',
+    assets: '../../build/m/chat',
 })

 // creator-app/svelte.config.js
 adapter: adapter({
-    pages: '../build',
-    assets: '../build',
+    pages: '../../build',
+    assets: '../../build',
 })
```

### 2. Build secuencial en Docker

**Problema:** `adapter-static` ejecuta `rimraf()` en el directorio de salida antes de escribir.
Con build paralelo, creator-app borraba `frontend/build/` entero, eliminando `m/chat/`.

**Archivo:** `docker-compose-example.yaml`

```diff
-pnpm --filter creator-app --filter module-chat build
+pnpm --filter creator-app build && pnpm --filter module-chat build
```

### 3. Rutas de assets absolutas en module-chat

**Problema:** Sin `relative: false`, SvelteKit generaba `href="/app/immutable/..."` que carga
los JS de **creator-app** en vez de module-chat. Con `relative: false`, genera
`href="/m/chat/app/immutable/..."`.

**Archivo:** `frontend/packages/module-chat/svelte.config.js`

```diff
 paths: {
     base: '/m/chat',
+    relative: false
 },
```

---

## Cambio Extra (menor)

`strict: false` en ambos adapter-static para evitar fallos cuando existen archivos
de la otra app en el directorio padre compartido.

Puerto por defecto corregido en `backend/lamb/modules/chat/__init__.py` (8000 → 9099).

---

### 4. Caddyfile para producción

**Problema:** En producción, Caddy sirve el frontend (no el backend). El `try_files {path} /index.html`
siempre caía al `index.html` de creator-app para cualquier ruta desconocida, incluyendo `/m/chat/*`.

**Archivo:** `Caddyfile`

```diff
+    # Module frontends (SPA fallback to module-specific index.html)
+    handle /m/chat/* {
+        root * /var/www/frontend
+        try_files {path} /m/chat/index.html
+        file_server
+    }
+
     handle {
         root * /var/www/frontend
         try_files {path} /index.html
         file_server
     }
```

> **Nota:** Este bloque debe ir ANTES del handler genérico. Para futuros módulos
> (e.g. `module-file-eval`), añadir handlers similares: `handle /m/file-eval/* { ... }`.

---

## Backend

### 5. Consistencia en el payload de configuración

**Problema:** `lti_router.py` pasaba el payload crudo del frontend a `on_activity_configured`, pero el servicio esperaba claves específicas como `resource_link_id` (sin el prefijo `lti_`).

**Archivo:** `backend/lamb/lti_router.py`

```python
# Se construye un setup_data limpio con valores validados del JWT
setup_data = {
    "resource_link_id": resource_link_id,
    "assistant_ids": assistant_ids,
    "configured_by_email": creator_user["user_email"],
    "activity_name": context_title or resource_link_id,
}
module.on_activity_configured(activity['id'], setup_data)
```

### 6. Métodos de DatabaseManager corregidos

**Problema:** El módulo de chat intentaba usar `execute_query` (inexistente) para guardar info de OWI, y el método `update_lti_activity` bloqueaba los campos `owi_group_id`/`name`.

**Archivos:**
- `backend/lamb/database_manager.py`: Añadidos campos a `allowed_fields`.
- `backend/lamb/modules/chat/service.py`: Cambiado `execute_query` por `update_lti_activity`.

### 7. Fix de Timestamp en Dashboard

**Problema:** Error 500 al cargar el dashboard porque se intentaba llamar a `.timestamp()` sobre un entero (SQLite ya devuelve el unix timestamp como int).

**Archivo:** `backend/lamb/lti_router.py`

```python
# Antes: activity.get('created_at').timestamp() -> ERROR
# Ahora:
"created_at": activity.get('created_at'),
```

---

## Cómo Verificar

```bash
# 1. Limpiar y reconstruir
sudo rm -rf frontend/build
docker-compose -f docker-compose-example.yaml down
docker-compose -f docker-compose-example.yaml up --force-recreate -d

# 2. Esperar ~60s y verificar que existe el build
ls frontend/build/m/chat/index.html

# 3. Verificar que las rutas son correctas (deben empezar con /m/chat/)
grep -oP 'href="[^"]*"' frontend/build/m/chat/index.html

# 4. Probar en el navegador: acceder a un LTI launch como instructor
# La página de setup debe cargar correctamente
```
