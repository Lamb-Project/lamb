# File Evaluation Module (Phase 4) — Plan refinado

> **For agentic workers:** REQUIRED SUB-SKILL: Use @superpowers/subagent-driven-development (recommended) or @superpowers/executing-plans to implement task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portar el flujo de evaluación de archivos de LAMBA al ecosistema LAMB como módulo `file_evaluation` que cumple el contrato `ActivityModule`, sustituyendo cookies LTI en memoria por JWTs (`lamb.auth`) y SQLAlchemy por SQL vía `LambDatabaseManager`.

**Architecture:** Se entrega en **vertical slices** (backend utilizable antes del frontend). Un único router FastAPI bajo `/lamb/v1/modules/file_evaluation/`. Los datos de actividad viven en `lti_activities` + `setup_config` JSON; las tablas `mod_file_eval_*` solo almacenan entregas, alumnos y notas. Los JWT de sesión del SPA se crean en `lamb/lti_router.py` (mismo patrón que `_create_dashboard_jwt`) para no duplicar lógica por módulo. La página de “progreso” de evaluación **no** es una ruta aparte en el MVP: se integra en la vista de corrección con polling.

**Tech Stack:** FastAPI, Pydantic v2, SQLite + `LambDatabaseManager.execute_query`, JWT HS256 (`lamb/auth.py`), SvelteKit 5 + adapter-static (patrón `frontend/packages/module-chat`), `pypdf`, `python-docx`.

**Fuentes de referencia en el repo:**

| Concepto | Ruta en LAMB |
|----------|----------------|
| Contrato del módulo | `backend/lamb/modules/base.py` |
| Módulo de referencia | `backend/lamb/modules/chat/__init__.py`, `chat/service.py` |
| JWTs LTI / redirecciones | `backend/lamb/lti_router.py` (`_create_dashboard_jwt`, `_validate_lti_jwt`) |
| Montaje SPA y estáticos | `backend/main.py` (bloques `module_chat`, catch-all) |
| Paquete frontend plantilla | `frontend/packages/module-chat/` (`svelte.config.js` → `../../build/m/chat`) |

---

## Cómo este plan simplifica el original

1. **MVP sin `/progress`**: La evaluación en curso se muestra en `grading/+page.svelte` (modal o sección con polling). La ruta `progress` solo si hace falta después.
2. **No portar CRUD de actividades LAMBA**: No `POST/GET/PUT /api/activities` hacia tablas propias; la actividad es `lti_activities`. Solo endpoints que el SPA necesite (entregas, notas, evaluación, estado).
3. **JWT centralizado**: Añadir en `lti_router.py` (o un módulo `lamb/lti_jwt_helpers.py` si prefieres no inflar el router) una función tipo `_create_file_eval_jwt(...)` y validación única usada por el `router.py` del módulo — evita copiar `decode_token` mal en cada ruta.
4. **Migraciones que realmente corren**: Hoy `get_migrations()` está en el contrato pero **no hay bucle de aplicación** en `backend/main.py` lifespan (solo `discover_modules` + montaje de routers). **Incluir una tarea explícita** que ejecute cada `SELECT`/`CREATE` de forma idempotente al arranque o documente añadir migración en `database_manager.py` — sin esto las tablas no existen.
5. **Tests en pytest** (un archivo) en lugar de cinco bloques `python -c` sueltos.
6. **Commits pequeños** por slice: (1) migraciones + runner, (2) libs puras, (3) servicios SQL, (4) router + dependencias, (5) `FileEvalModule` completo, (6) frontend, (7) `main.py` montaje `/m/file-eval/app`.

---

## Mapa de archivos (responsabilidad única)

| Archivo | Responsabilidad |
|---------|-----------------|
| `backend/lamb/modules/file_evaluation/__init__.py` | Exporta `module = FileEvalModule()` |
| `backend/lamb/modules/file_evaluation/module.py` | Implementación `ActivityModule` |
| `backend/lamb/modules/file_evaluation/migrations.py` | Lista `MIGRATION_SQL: list[str]` (CREATE TABLE + índices, idempotente) |
| `backend/lamb/modules/file_evaluation/schemas.py` | Modelos Pydantic de API |
| `backend/lamb/modules/file_evaluation/document_extractor.py` | Extracción de texto (copia desde LAMBA + logger) |
| `backend/lamb/modules/file_evaluation/evaluator_client.py` | Regex de nota + llamada interna a `run_lamb_assistant` (no HTTP) |
| `backend/lamb/modules/file_evaluation/storage_service.py` | Rutas bajo `uploads/file-eval/...` |
| `backend/lamb/modules/file_evaluation/grade_service.py` | CRUD notas en SQL |
| `backend/lamb/modules/file_evaluation/lti_passback.py` | OAuth/XML LTI 1.1 (lógica idéntica a LAMBA; credenciales desde `LtiActivityManager`) |
| `backend/lamb/modules/file_evaluation/evaluation_service.py` | Estados, batch, timeouts |
| `backend/lamb/modules/file_evaluation/service.py` | Entregas, grupos, vistas de alumno/profesor (SQL) |
| `backend/lamb/modules/file_evaluation/router.py` | Un solo `APIRouter` + dependencia `get_current_file_eval_payload` |
| `backend/lamb/modules/file_evaluation/deps.py` (opcional) | Extraer JWT Bearer / query `token` → claims validados |
| `frontend/packages/module-file-eval/...` | SPA `base: '/m/file-eval'`, salida `../../build/m/file-eval` |
| `backend/main.py` | Montaje `StaticFiles` para `/m/file-eval/app` + (si aplica) aplicar migraciones de módulos |
| `backend/requirements.txt` | `pypdf`, `python-docx` |

---

## Contrato JWT (definir una vez)

Propuesta mínima para el SPA (ajustar nombres a lo que ya use `lamb_auth`):

- `lti_type`: `"file_eval"` (nuevo valor; ampliar `_validate_lti_jwt` o validar con `decode_token` + comprobación de campo).
- `lti_resource_link_id`, `lti_activity_id`, `lti_lms_user_id`, `lti_user_email` (sintético vía `LtiActivityManager.generate_student_email()`), `lti_display_name`, `is_instructor: bool`.

**Profesor:** Misma idea que chat: redirigir a  
`{LAMB_PUBLIC_BASE_URL}/m/file-eval/grading?resource_link_id=...&token=...`  
**Alumno:**  
`.../m/file-eval/upload?...`

**Consentimiento:** Si el módulo debe respetar el flujo de consentimiento como chat, reutilizar `_create_consent_token` y redirigir a una página de consentimiento en el paquete del módulo (o compartir la de chat) — **decisión de producto**: si file-eval exige consentimiento explícito, añadir ruta `/m/file-eval/consent` copiando el patrón de `module-chat`; si no, documentar “skip” en el mismo sitio que chat para estudiantes ya aceptados.

---

## Tareas (orden recomendado)

### Task 1: Aplicar migraciones de módulos al arranque

**Files:**

- Modify: `backend/main.py` (dentro de `lifespan`, después de `discover_modules()`)
- Opcional: `backend/lamb/database_manager.py` si preferís centralizar en `init_db`

**Pasos:**

- [ ] **Step 1: Escribir función `apply_module_migrations()`**

```python
def apply_module_migrations():
    from lamb.modules import get_all_modules
    from lamb.database_manager import LambDatabaseManager
    db = LambDatabaseManager()
    for mod in get_all_modules():
        for sql in mod.get_migrations():
            if not sql.strip():
                continue
            conn = db.get_connection()
            if not conn:
                raise RuntimeError("No DB connection for module migrations")
            try:
                conn.execute(sql)
                conn.commit()
            finally:
                conn.close()
```

(En este codebase no existe `execute_query()` en `LambDatabaseManager`; usar `get_connection()` + `cursor.execute` / `conn.execute` según el estilo del resto del archivo.)

- [ ] **Step 2: Invocar en `lifespan`** antes de montar routers (o justo después de `discover_modules`).

- [ ] **Step 3: Verificar**

Run: `cd /home/franpv2004/proyecto/lamb/backend && python -c "from main import lifespan"` — o arrancar uvicorn y revisar logs sin error.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py
git commit -m "feat: apply ActivityModule SQL migrations on startup #{issue}"
```

---

### Task 2: Esqueleto del paquete + migraciones SQL

**Files:**

- Create: `backend/lamb/modules/file_evaluation/__init__.py`
- Create: `backend/lamb/modules/file_evaluation/migrations.py`
- Create: `backend/lamb/modules/file_evaluation/module.py` (stub con `get_migrations()` real, resto `raise NotImplementedError` o `pass` según permita ABC)

**Pasos:**

- [ ] **Step 1: DDL** — Traducir modelos LAMBA (`db_models.py`) a tablas `mod_file_eval_*` con FK a `lti_activities(id)`, índices acordados, sin claves compuestas LAMBA.

- [ ] **Step 2: `FileEvalModule.get_migrations()`** retorna `MIGRATION_SQL` desde `migrations.py`.

- [ ] **Step 3: Test**

Run:

```bash
cd /home/franpv2004/proyecto/lamb/backend
pytest tests/modules/test_file_evaluation_migrations.py -v
```

Test mínimo (crear archivo si no existe):

```python
def test_file_eval_migrations_returns_sql():
    from lamb.modules.file_evaluation.migrations import MIGRATION_SQL
    assert any("mod_file_eval_submissions" in s for s in MIGRATION_SQL)
```

- [ ] **Step 4: Commit**

---

### Task 3: `document_extractor.py` + dependencias

**Files:**

- Create: `backend/lamb/modules/file_evaluation/document_extractor.py`
- Modify: `backend/requirements.txt`

**Pasos:**

- [ ] Copiar lógica desde LAMBA `document_extractor.py`, logger `get_logger(__name__, component="FILE_EVAL")`.
- [ ] Añadir `pypdf>=5.1.0`, `python-docx>=1.1.0`.
- [ ] `pip install -r requirements.txt` (o el entorno del proyecto).
- [ ] Pytest: extracción de `.txt` temporal (como en el plan original).
- [ ] Commit.

---

### Task 4: `evaluator_client.py` (sin HTTP)

**Files:**

- Create: `backend/lamb/modules/file_evaluation/evaluator_client.py`

**Pasos:**

- [ ] Portar `_extract_score_and_feedback`, `parse_evaluation_response`, `validate_chat_completions_format` desde `lamb_api_service.py` (LAMBA).
- [ ] Implementar método que llame a `run_lamb_assistant` desde `lamb.completions.main` con los parámetros que ya use el backend (revisar firma real en `backend/lamb/completions/main.py`).
- [ ] Tests unitarios de regex (parametrizados).
- [ ] Commit.

---

### Task 5: `storage_service.py`

**Files:**

- Create: `backend/lamb/modules/file_evaluation/storage_service.py`

**Pasos:**

- [ ] `UPLOADS_ROOT` = `Path(__file__).resolve().parents[N]/uploads/file-eval` o variable de entorno documentada.
- [ ] Mantener `is_within_uploads` y sanitización de nombre.
- [ ] Commit.

---

### Task 6: `grade_service.py` + `schemas.py` (solo lo necesario para notas)

**Files:**

- Create: `backend/lamb/modules/file_evaluation/grade_service.py`
- Create: `backend/lamb/modules/file_evaluation/schemas.py`

**Pasos:**

- [ ] Pydantic: `GradeRequest`, `GradeUpdate`, `GradeResponse`, etc.
- [ ] SQL: upsert/select notas en `mod_file_eval_grades`.
- [ ] Commit.

---

### Task 7: `lti_passback.py`

**Files:**

- Create: `backend/lamb/modules/file_evaluation/lti_passback.py`

**Pasos:**

- [ ] Copiar funciones OAuth/XML **sin cambiar algoritmo**.
- [ ] Sustituir lectura de credenciales/env por `LtiActivityManager.get_lti_credentials()` y URLs desde fila `lti_activities` / launch.
- [ ] Commit.

---

### Task 8: `evaluation_service.py`

**Files:**

- Create: `backend/lamb/modules/file_evaluation/evaluation_service.py`

**Pasos:**

- [ ] Estados: `pending`, `processing`, `completed`, `error`.
- [ ] `process_evaluation_batch` invocable desde `BackgroundTasks` (definir en `router` o `main` según patrón existente).
- [ ] Commit.

---

### Task 9: `service.py` (entregas y grupos)

**Files:**

- Create: `backend/lamb/modules/file_evaluation/service.py`

**Pasos:**

- [ ] `setup_config` JSON: `evaluator_id`, `activity_type`, `max_group_size`, `deadline`, `language`.
- [ ] `create_submission`, grupo, listados — solo SQL + `storage_service`.
- [ ] Commit.

---

### Task 10: JWT helpers + `router.py`

**Files:**

- Modify: `backend/lamb/lti_router.py` (o nuevo `backend/lamb/lti_module_tokens.py`)
- Create: `backend/lamb/modules/file_evaluation/router.py`
- Modify: `backend/lamb/modules/file_evaluation/module.py` — `get_routers()` devuelve el router

**Pasos:**

- [ ] Añadir creador de JWT file-eval y validación compartida.
- [ ] Endpoints mínimos MVP (lista a cerrar contra LAMBA `activities_router` / `submissions_router` / `grades_router` **solo los que el SPA llame**):

  - `POST /activities/{id}/submissions` (multipart)
  - `GET /activities/{id}/submissions`
  - `GET /activities/{id}/view` (vista profesor/alumno según rol en JWT)
  - `POST /activities/{id}/evaluate`
  - `GET /activities/{id}/evaluation-status`
  - `POST /activities/{id}/grades/sync`
  - `GET /submissions/me`, `POST /submissions/join`, `GET /submissions/{id}/members`, `GET /submissions/my-file/download`
  - `POST /grades/{submission_id}`, `POST /grades/activity/{id}/accept-ai-grades`

  Prefijos: el montaje añade `/lamb/v1/modules/file_evaluation`, así las rutas internas no repiten ese prefijo.

- [ ] Commit.

---

### Task 11: Completar `FileEvalModule`

**Files:**

- Modify: `backend/lamb/modules/file_evaluation/module.py`

**Pasos:**

- [ ] `get_setup_fields()` — `SetupField` para evaluator, tipo actividad, tamaño grupo, deadline, idioma.
- [ ] `on_activity_configured` / `on_activity_reconfigured` — persistir/validar `setup_config` (vía manager existente si ya existe API).
- [ ] `on_student_launch` / `on_instructor_launch` / `launch_user` — redirecciones con JWT (copiar estructura de `ChatModule`).
- [ ] `get_dashboard_stats` — conteos; `get_dashboard_chats` / `get_dashboard_chat_detail` — vacíos / `None`.
- [ ] `get_frontend_build_path()` — devolver `None` hasta que exista build, o la ruta relativa acordada con `main.py` (chat devuelve `None` pero los estáticos se montan por convención `frontend/build/m/chat` — **alinear** con montaje explícito en `main.py`).

- [ ] Commit.

---

### Task 12: `main.py` — montaje estáticos file-eval

**Files:**

- Modify: `backend/main.py`

**Pasos:**

- [ ] Tras build del paquete, existirá `frontend/build/m/file-eval/app` — duplicar bloque `module_chat` para `module_file_eval`.
- [ ] Actualizar comentarios del catch-all si se añaden rutas `m/file-eval/app/`.
- [ ] Commit.

---

### Task 13: Frontend `module-file-eval`

**Files:**

- Create: árbol bajo `frontend/packages/module-file-eval/` (copiar `package.json`, `svelte.config.js`, `vite.config.js` desde `module-chat`; cambiar nombre, `paths.base`, `pages/assets` → `../../build/m/file-eval`, puerto dev p. ej. 5174)
- Create: `src/routes/upload/+page.svelte`, `src/routes/grading/+page.svelte`
- Create: `src/lib/services/*.js`, `src/lib/locales/*.json` con prefijo `fileEval.*`

**Pasos:**

- [ ] `pnpm install` / `npm install` en el workspace.
- [ ] Servicios: token en query → header `Authorization: Bearer`.
- [ ] `pnpm build` desde monorepo raíz según convención del repo.
- [ ] Commit.

---

## Verificación

### Automatizada (pytest)

Run:

```bash
cd /home/franpv2004/proyecto/lamb/backend
pytest tests/modules/test_file_evaluation_*.py -v
```

Incluir: migraciones, extractor TXT, regex de notas, import de módulo (`get_module('file_evaluation')`).

### Manual (LTI)

Igual que el plan original: lanzamiento instructor/alumno, subida, evaluación IA, passback.

---

## Referencias de skills

- @superpowers/subagent-driven-development — ejecución por tarea.
- @superpowers/executing-plans — ejecución en bloque con checkpoints.
- @superpowers/verification-before-completion — antes de declarar “hecho”.

---

## Plan review (opcional)

Tras escribir este documento, si usas el flujo superpowers, despachar un revisor de plan con: ruta a este archivo + enlace al issue/spec. Máximo 3 iteraciones; si no hay acuerdo, revisión humana.

---

## Al completar el plan

**Plan guardado en:** `docs/superpowers/plans/2026-03-23-file-evaluation-module-port.md`

**Opciones de ejecución:**

1. **Subagent-driven (recomendado)** — un subagente por tarea, revisión entre tareas.
2. **Inline** — @superpowers/executing-plans en esta sesión con checkpoints.

**¿Cuál prefieres?**
