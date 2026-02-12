# Análisis de Cobertura de Tests Playwright

**Fecha:** 2026-02-12  
**Directorio:** `testing/playwright/tests/`

---

## 1. Tests Existentes — Resumen de Funcionalidades Cubiertas

### ✅ `creator_flow.spec.js`
| Funcionalidad | Estado |
|---|---|
| Crear Knowledge Base | ✅ |
| Abrir detalle de KB | ✅ |
| Ingestar fichero (fixture txt) | ✅ |
| Query a KB (smoke) | ✅ |
| Eliminar KB | ✅ |
| Crear assistant (smoke) | ✅ |
| Eliminar assistant | ✅ |
| Chat con assistant (respuesta esperada) | ✅ |

### ✅ `url_ingest.spec.js`
| Funcionalidad | Estado |
|---|---|
| Crear KB para ingesta URL | ✅ |
| Ingestar contenido vía URL | ✅ |
| Verificar JSON response (Firecrawl, condicional) | ✅ |
| Eliminar KB | ✅ |

### ✅ `youtube_titles.spec.js`
| Funcionalidad | Estado |
|---|---|
| Ingestar vídeo YouTube vía plugin | ✅ |
| Verificar título descriptivo del fichero generado | ✅ |

### ✅ `admin_and_sharing_flow.spec.js`
| Funcionalidad | Estado |
|---|---|
| Admin: crear usuario | ✅ |
| Admin: crear organización con admin | ✅ |
| Admin: deshabilitar usuario | ✅ |
| Admin: eliminar organización | ✅ |
| Sharing: crear usuarios para test de compartición | ✅ |
| Sharing: crear organización con admin | ✅ |
| Sharing: login como usuario, crear assistant | ✅ |
| Sharing: compartir assistant con segundo usuario | ✅ |
| Sharing: verificar assistant compartido visible para otro usuario | ✅ |
| Sharing: eliminar compartición y cleanup | ✅ |

### ✅ `admin_role_lifecycle.spec.js`
| Funcionalidad | Estado |
|---|---|
| Crear usuario con rol admin | ✅ |
| Nuevo admin accede al dashboard | ✅ |
| Nuevo admin accede a gestión de usuarios | ✅ |
| Nuevo admin accede a organizaciones | ✅ |
| Self-disable bloqueado para el propio admin | ✅ |
| Deshabilitar admin creado | ✅ |
| Admin deshabilitado no puede hacer login | ✅ |
| Cleanup: eliminar usuario de test | ✅ |

### ✅ `org_no_admin_and_role_promotion.spec.js`
| Funcionalidad | Estado |
|---|---|
| Crear organización sin admin (campo opcional) | ✅ |
| Verificar org sin admin en la lista | ✅ |
| Crear usuario de test | ✅ |
| Crear org con usuario como admin | ✅ |
| Members modal: verificar usuario como Admin | ✅ |
| Demote: Admin → Member | ✅ |
| Promote: Member → Admin | ✅ |
| Note sobre LTI Creator en modal | ✅ |
| Cleanup: eliminar orgs y deshabilitar usuario | ✅ |

### ✅ `advanced_assistants_management.spec.js`
| Funcionalidad | Estado |
|---|---|
| Crear assistant base | ✅ |
| Editar assistant (validaciones de formulario) | ✅ |
| Publicar assistant (publish/unpublish) | ✅ |
| Configurar plugins: modelo, connector, visión | ✅ |
| Error: nombre vacío (validación client-side) | ✅ |
| Cleanup: eliminar assistant | ✅ |

### ✅ `org_form_modal.spec.js`
| Funcionalidad | Estado |
|---|---|
| Modal de creación de org: campos visibles | ✅ |
| Botón Cancel cierra modal | ✅ |
| Signup key aparece al habilitar signup | ✅ |
| Dropdown de admin carga usuarios del sistema | ✅ |
| Validación del campo Slug | ✅ |
| Formulario se puede rellenar y enviar | ✅ |

### ✅ `kb_delete_modal.spec.js`
| Funcionalidad | Estado |
|---|---|
| Modal de confirmación al borrar KB | ✅ |
| Cancel cierra modal sin borrar | ✅ |
| Escape cierra modal | ✅ |
| Confirm elimina la KB | ✅ |

### ✅ `kb_detail_modals.spec.js`
| Funcionalidad | Estado |
|---|---|
| Crear KB con fichero para tests de modales | ✅ |
| Modal de borrado de fichero aparece | ✅ |
| Cancel cierra modal sin borrar fichero | ✅ |
| Confirm elimina el fichero | ✅ |
| Cleanup: eliminar KB de test | ✅ |

### ✅ `access_control_and_user_dashboard.spec.js`
| Funcionalidad | Estado |
|---|---|
| Admin user dashboard: click en nombre abre vista detalle | ✅ |
| "Back to Users" vuelve a la lista | ✅ |
| System admin ve banner read-only en assistant ajeno | ✅ |
| System admin: tab Edit NO visible en assistant ajeno | ✅ |
| Owner ve acceso completo (Edit tab, sin banner read-only) | ✅ |
| API: /admin/users/{id}/profile devuelve perfil válido | ✅ |
| API: assistant detail devuelve access_level e is_owner | ✅ |
| Cleanup: eliminar assistant y usuario de test | ✅ |

### ✅ `moodle_lti.spec.js`
| Funcionalidad | Estado |
|---|---|
| Click en actividad LTI redirige a OWI | ✅ |
| Assistant visible tras redirect LTI | ✅ |

---

## 2. Funcionalidades SIN Test de Playwright

A continuación se listan las funcionalidades identificadas en el código fuente (rutas frontend, componentes Svelte, routers backend, servicios) que **NO tienen cobertura** en ningún test de Playwright existente.

### 🔴 Login / Signup / Autenticación

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **Signup de usuario** (formulario `/signup`) | `Login.svelte`, `Signup.svelte`, `authService.js`, `main.py::signup` |
| **Signup con clave de organización** | `Signup.svelte`, `main.py::signup` |
| **Logout explícito** (como test principal, no como helper) | `Nav.svelte` |
| **Login con credenciales inválidas** (error message) | `Login.svelte`, `main.py::login` |
| **Sesión expirada / token inválido** | `hooks.server.js` |

### 🔴 Evaluaitor (Rúbricas)

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **Crear rúbrica** | `evaluaitor/+page.svelte`, `RubricForm.svelte`, `RubricEditor.svelte`, `evaluaitor_router.py` |
| **Editar rúbrica** | `RubricEditor.svelte`, `evaluaitor_router.py::update_rubric` |
| **Eliminar rúbrica** | `evaluaitor_router.py::delete_rubric` |
| **Duplicar rúbrica** | `evaluaitor_router.py::duplicate_rubric` |
| **Cambiar visibilidad (público/privado)** | `evaluaitor_router.py::update_rubric_visibility` |
| **Showcase rúbricas** | `evaluaitor_router.py::update_rubric_showcase` |
| **Importar rúbrica (JSON)** | `evaluaitor_router.py::import_rubric` |
| **Exportar rúbrica (JSON/Markdown)** | `evaluaitor_router.py::export_rubric_json`, `export_rubric_markdown` |
| **Generación IA de rúbrica** | `RubricAIGenerationModal.svelte`, `evaluaitor_router.py::ai_generate_rubric` |
| **Modificación IA de rúbrica** | `RubricAIChat.svelte`, `evaluaitor_router.py::ai_modify_rubric` |
| **Lista de rúbricas públicas** | `evaluaitor_router.py::list_public_rubrics` |
| **Vista de detalle de rúbrica (`/evaluaitor/[rubricId]`)** | `evaluaitor/[rubricId]/+page.svelte` |
| **Preview de rúbrica** | `RubricPreview.svelte` |

### 🔴 Prompt Templates

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **Crear prompt template** | `PromptTemplatesContent.svelte`, `templateService.js::createTemplate`, `prompt_templates_router.py` |
| **Editar prompt template** | `templateService.js::updateTemplate` |
| **Eliminar prompt template** | `templateService.js::deleteTemplate` |
| **Duplicar prompt template** | `templateService.js::duplicateTemplate` |
| **Compartir/des-compartir template** | `templateService.js::toggleTemplateSharing` |
| **Ver templates compartidos** | `templateService.js::listSharedTemplates` |
| **Exportar templates** | `templateService.js::exportTemplates` |
| **Usar template en creación de assistant** | `TemplateSelectModal.svelte` |

### 🔴 Chat Analytics

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **Vista de analytics de un assistant** | `ChatAnalytics.svelte`, `analyticsService.js` |
| **Listado de chats de un assistant** | `analyticsService.js::getAssistantChats` |
| **Detalle de un chat individual** | `analyticsService.js::getChatDetail` |
| **Estadísticas del assistant** | `analyticsService.js::getAssistantStats` |
| **Timeline del assistant** | `analyticsService.js::getAssistantTimeline` |

### 🔴 Org-Admin Panel (`/org-admin`)

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **Dashboard de org-admin** | `org-admin/+page.svelte` |
| **Gestión de usuarios org-admin** (CRUD, enable/disable, bulk) | `org-admin/+page.svelte`, `organization_router.py` |
| **Cambio de contraseña de usuario (org-admin)** | `ChangePasswordModal.svelte`, `organization_router.py::change_user_password` |
| **Bulk enable/disable de usuarios** | `org-admin/+page.svelte`, `organization_router.py::org_admin_bulk_enable_users/disable` |
| **Vista "Assistants Access" del org-admin** | `org-admin/+page.svelte` |
| **Gestión de sharing de assistants (org-admin)** | `AssistantSharingModal.svelte`, `org-admin/+page.svelte` |
| **Permiso "Can Share" por usuario** | `org-admin/+page.svelte` |
| **Settings > General (Signup settings)** | `org-admin/+page.svelte` |
| **Settings > API (modelado, claves, modelo por defecto)** | `org-admin/+page.svelte` |
| **Settings > Knowledge Base (URL, API key, test de conexión)** | `org-admin/+page.svelte` |
| **Settings > Assistant Defaults (JSON)** | `org-admin/+page.svelte` |
| **Settings > LTI Creator (crear/editar/eliminar clave LTI)** | `org-admin/+page.svelte` |
| **LTI Activities (listado, enable/disable)** | `org-admin/+page.svelte` |
| **Import CSV de usuarios (bulk import)** | `organization_router.py::validate_bulk_user_import`, `execute_bulk_user_import` |

### 🔴 Knowledge Base — Funcionalidades Avanzadas

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **Editar KB** (nombre, descripción) | `knowledges_router.py::update_knowledge_base` |
| **Compartir/des-compartir KB** (toggle sharing) | `knowledges_router.py::toggle_kb_sharing`, `knowledgeBaseService.js::toggleKBSharing` |
| **KB compartidas visibles** | `knowledgeBaseService.js::getSharedKnowledgeBases` |
| **Ingestion jobs: listado, estado, retry, cancelar** | `knowledges_router.py`, `knowledgeBaseService.js` |
| **Query con plugins** | `knowledges_router.py::get_query_plugins` |
| **Crear KB modal (componente `CreateKnowledgeBaseModal`)** | `CreateKnowledgeBaseModal.svelte` |

### 🔴 Assistants — Funcionalidades Avanzadas

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **Exportar assistant** | `assistantService.js::downloadAssistant`, `assistant_router.py::export_assistant_proxy` |
| **Generar descripción IA del assistant** | `assistant_router.py::generate_assistant_description` |
| **Lista de assistants compartidos ("Shared with Me")** | `assistantService.js::getSharedAssistants` |
| **Configuración RAG_collections desde UI** | `AssistantForm.svelte` |
| **Assistant defaults (org-scoped)** | `assistant_router.py::get_assistant_defaults_for_current_user` |

### 🔴 System Admin (`/admin`) — Funcionalidades No Cubiertas

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **System Admin Dashboard (estadísticas globales)** | `AdminDashboard.svelte`, `organization_router.py::get_system_stats` |
| **Editar organización** (update) | `organization_router.py::update_organization` |
| **Migración de organización** | `organization_router.py::validate_organization_migration`, `migrate_organization` |
| **Config. de organización** (get/update config) | `organization_router.py::get_organization_config`, `update_organization_config` |
| **Uso de organización** (usage stats) | `organization_router.py::get_organization_usage` |
| **Exportar organización** | `organization_router.py::export_organization` |
| **Sync system organization** | `organization_router.py::sync_system_organization` |
| **Admin: cambiar contraseña de un usuario** | `main.py::update_user_password_admin` |
| **Admin: cambiar rol de usuario** | `main.py::update_user_role_admin` |
| **Admin: eliminar usuario (delete real)** | `main.py::delete_user_admin`, `adminService.js::deleteUser` |
| **Admin: verificar dependencias antes de borrar** | `main.py::check_user_dependencies_admin`, `adminService.js::checkUserDependencies` |
| **LTI Global Config** | `organization_router.py::get_lti_global_config`, `update_lti_global_config` |

### 🔴 UI/UX General

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **Selector de idioma** | `LanguageSelector.svelte`, `i18n.js`, `locales/` |
| **Navegación principal (Nav)** | `Nav.svelte` |
| **Paginación (componente reutilizable)** | `Pagination.svelte` |
| **FilterBar (filtros comunes)** | `FilterBar.svelte` |
| **Footer** | `Footer.svelte` |
| **Responsive/mobile** | Todos los componentes |
| **Error handling global** (API down, 403, 500...) | Varios |

### 🔴 API / Backend — Endpoints Directos

| Funcionalidad | Archivo(s) Relevante(s) |
|---|---|
| **`/creator/me` (perfil propio)** | `main.py::get_own_profile` |
| **File management (list, upload, delete files de usuario)** | `main.py::list_user_files`, `upload_file`, `delete_file` |
| **News endpoint** | `main.py::get_news` |
| **Chat proxy (streaming)** | `learning_assistant_proxy.py::proxy_assistant_chat` |
| **Chats CRUD** | `chats_router.py` |

---

## 3. Recomendaciones de Prioridad

### 🔥 Alta Prioridad (flujos críticos sin cobertura)

1. **Evaluaitor (Rúbricas)**: Ruta completa sin ningún test. Es una feature completa con CRUD, IA y exportación.
2. **Prompt Templates**: Ruta completa sin ningún test. Incluye CRUD, compartición y exportación.
3. **Org-Admin Panel**: Panel completo sin ningún test. Es crítico para la administración delegada.
4. **Signup de usuario**: Flujo fundamental de onboarding sin test.
5. **Login con credenciales inválidas**: Caso de error básico sin test.

### ⚠️ Media Prioridad (features secundarias)

6. **Chat Analytics**: Vista de analytics de assistants.
7. **KB sharing**: Toggle de compartición de KBs y visibilidad de KBs compartidas.
8. **Ingestion jobs** (listado, retry, cancel): Operaciones avanzadas de ingesta.
9. **System Admin Dashboard** (stats): Vista de estadísticas globales.
10. **Exportar assistant / generar descripción IA**: Features avanzadas de assistants.

### 💡 Baja Prioridad (UI/UX y edge cases)

11. **Selector de idioma / i18n**: Funcionalidad de localización.
12. **Paginación / FilterBar**: Componentes reutilizables.
13. **Responsive/mobile**: Tests de responsividad.
14. **Migración de org / export org**: Operaciones administrativas infrecuentes.

---

## 4. Resumen Cuantitativo

| Categoría | Tests | Funcionalidades Cubiertas | Funcionalidades Sin Cubrir |
|---|---|---|---|
| Auth (Login/Signup) | Parcial (login como helper) | 1 | 4 |
| Knowledge Bases | 4 specs | ~15 | ~6 |
| Assistants | 3 specs | ~20 | ~5 |
| Admin (System) | 4 specs | ~25 | ~10 |
| Org-Admin | 0 specs | 0 | ~15 |
| Evaluaitor (Rúbricas) | 0 specs | 0 | ~12 |
| Prompt Templates | 0 specs | 0 | ~8 |
| Chat Analytics | 0 specs | 0 | ~4 |
| LTI | 1 spec | 2 | ~3 |
| UI/UX General | 0 specs | 0 | ~6 |
| **TOTAL** | **12 specs** | **~63** | **~73** |

> **Cobertura estimada: ~46%** de las funcionalidades identificadas en rutas, componentes y endpoints tienen al menos un test de Playwright.
