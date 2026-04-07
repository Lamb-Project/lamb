# Backend en Docker vs en local: LTI, `.env` y permisos

**Issue:** #277 — documentación operativa para desarrollo.  
**Audiencia:** quien prueba LTI (file-eval, chat, passback de notas) alternando o eligiendo entre `docker-compose` y `uvicorn` en la máquina host.

---

## 1. Resumen

| Modo | Cuándo encaja | LTI / passback | Permisos en disco |
|------|----------------|----------------|-------------------|
| **Docker** (`backend` en compose) | Paridad con despliegue, todo el stack junto | Falla si `lis_outcome_service_url` usa `localhost` hacia un LMS en el **host** | Ficheros bajo el repo suelen ser de **root** en volumen montado |
| **Local** (`uvicorn` en el host) | Probar passback a LMS en `localhost:8000` sin trucos de red | `localhost` en la URL de outcomes **sí** apunta al host | Tu usuario escribe en `uploads/` y `static/cache/`; choca si antes escribió Docker como root |

No son dos “versiones” del producto: es el **mismo código** y el mismo `backend/.env`, pero **hostname y usuario del proceso** cambian.

---

## 2. Cómo ejecutar el backend en Docker

1. Definir **`LAMB_PROJECT_PATH`** (ruta absoluta al repo), por ejemplo en el shell o en un `.env` junto al compose.
2. Levantar el ejemplo:

   ```bash
   docker compose -f docker-compose-example.yaml up -d
   ```

3. El servicio **`backend`** (véase [docker-compose-example.yaml](../../docker-compose-example.yaml)):
   - Carga [backend/.env](../../backend/.env) (`env_file`).
   - Monta el proyecto en el contenedor (`volumes: ${LAMB_PROJECT_PATH}:${LAMB_PROJECT_PATH}`).
   - Expone la API en **`127.0.0.1:9099`** (host).

4. Otros servicios relevantes para el stack completo: **`openwebui`** (8080), **`kb`** (9090), builds de frontend, etc.

**Ventajas para desarrollo**

- Mismas dependencias que en CI/prod (pip en imagen).
- Resolución DNS interna: `openwebui`, `kb`, `backend` entre sí.
- No necesitas venv Python en el host.

**Para probar LTI contra un LMS en el host (p. ej. `docker run -p 8000:8000 lti-platform`)**

- El POST de passback sale **desde dentro del contenedor `backend`**.
- Si Moodle/LTI guardó `lis_outcome_service_url` como `http://localhost:8000/...`, dentro del contenedor **`localhost` es el propio contenedor**, no el host → error tipo *Connection refused*.
- Mitigaciones: configurar el LMS con una base alcanzable desde el contenedor (`host.docker.internal`, IP del host, o misma red Docker), o ejecutar el backend en el host (sección 3).

---

## 3. Cómo ejecutar el backend en local (host)

1. **Parar** el servicio `backend` del compose (o no levantarlo) para liberar el puerto 9099:

   ```bash
   docker compose -f docker-compose-example.yaml stop backend
   ```

2. Mantener en marcha lo que necesites en Docker (**openwebui**, **kb**, etc.) si la app lo usa.

3. Entorno Python recomendado:

   ```bash
   cd backend
   python3 -m venv .venv
   source .venv/bin/activate   # Linux / WSL / macOS
   pip install -r requirements-base.txt && pip install -r requirements-ml.txt
   ```

4. Ajustar [backend/.env](../../backend/.env) para **llamadas servidor→servidor desde el host**:

   | Variable | En Docker (compose) | En local (host) |
   |----------|---------------------|-----------------|
   | `OWI_BASE_URL` | `http://openwebui:8080` | `http://127.0.0.1:8080` |
   | `LAMB_KB_SERVER` | `http://kb:9090` | `http://127.0.0.1:9090` |
   | `OLLAMA_BASE_URL` (si aplica) | `http://host.docker.internal:11434` u otro | `http://127.0.0.1:11434` |

   Referencia: comentarios en [backend/.env.example](../../backend/.env.example) (sección Open WebUI y Docker Compose notes).

5. Arrancar:

   ```bash
   export PORT=9099   # opcional si ya está en .env
   uvicorn main:app --port 9099 --host 0.0.0.0 --reload
   ```

**Ventajas para LTI / passback**

- `lis_outcome_service_url` con `http://localhost:8000/...` **resuelve al mismo host** donde corre el LMS de pruebas.
- Evitas `host.docker.internal` y redes Docker solo para desbloquear el envío de notas en local.

**Inconvenientes**

- Debes **recordar revertir** `OWI_BASE_URL` / `LAMB_KB_SERVER` cuando vuelvas a Docker.
- Mismo árbol de ficheros que Docker: riesgo de **permisos** (sección 5).

---

## 4. Probar LTI y file-eval viniendo de cada modo

Flujo común:

1. Lanzamiento LTI → `lti_router` persiste `lis_outcome_service_url` en `lti_activities` (si viene en el POST).
2. Alumno entrega con JWT que incluye `lis_result_sourcedid` (cuando el LMS lo envía).
3. Profesor pone nota → **Sync grades to Moodle** → `POST` a `lis_outcome_service_url` desde el proceso del **backend** (Docker o host).

**Si el backend está en Docker**

- Comprueba que la URL guardada **no** sea solo `localhost` hacia un servicio que vive en el host, salvo que hayas configurado reescritura/red (p. ej. `host.docker.internal` en Linux con `extra_hosts` en el servicio `backend`).

**Si el backend está en el host**

- Tras cambiar `.env` a `127.0.0.1` para OWI/KB, reinicia `uvicorn`.
- Si ves errores de caché de noticias o de subida a `uploads/`, revisa permisos (sección 5).

**Relanzar LTI**

- Tras cambiar la URL base del LMS o `lis_outcome_service_url`, conviene un **nuevo launch** para actualizar la fila en BD.

---

## 5. Permisos: Docker (root) vs usuario local

El compose monta el repo en el contenedor. El proceso suele correr como **root** dentro del contenedor: los ficheros **nuevos** en rutas como:

- `backend/uploads/` (p. ej. file-eval)
- `backend/static/cache/` (p. ej. noticias)

pueden quedar en el host con **dueño root**.

Si luego ejecutas **uvicorn con tu usuario** sobre el mismo árbol:

- Escritura en esas carpetas → **`Permission denied`**.
- Lectura a veces funciona, pero crear subcarpetas o ficheros nuevos falla.

**Arreglo habitual al pasar de Docker a local**

```bash
sudo chown -R "$USER:$USER" \
  backend/uploads \
  backend/static/cache
```

(Ajusta rutas si el repo no está en el cwd.)

Si la base SQLite está en el proyecto y da problemas:

```bash
sudo chown "$USER:$USER" /ruta/a/tu/lamb_v4.db
```

(Usa la ruta real de `LAMB_DB_PATH` en `.env`.)

**Al volver a Docker**

- No hace falta “deshacer” el `chown`: el contenedor como root suele poder leer/escribir igual.
- Si **otra vez** trabajas en local tras una sesión larga en Docker, puede repetirse el conflicto: vuelve a aplicar `chown` en `uploads` y `static/cache` si aparecen denegaciones.

**Mitigación a medio plazo**

- Ejecutar el contenedor `backend` con `user: uid:gid` alineado al desarrollador (cambio en compose), para que los ficheros creados en volumen sean del mismo UID que en el host.

---

## 6. Checklist al cambiar de modo

**De Docker → local**

- [ ] `docker compose ... stop backend` (o no iniciar `backend`).
- [ ] `OWI_BASE_URL=http://127.0.0.1:8080`, `LAMB_KB_SERVER=http://127.0.0.1:9090` (y Ollama si aplica).
- [ ] `chown` en `backend/uploads` y `backend/static/cache` si hubo errores de permisos.
- [ ] `uvicorn` desde `backend/` con venv activado.

**De local → Docker**

- [ ] `OWI_BASE_URL=http://openwebui:8080`, `LAMB_KB_SERVER=http://kb:9090` (valores típicos del `.env` para compose).
- [ ] `docker compose -f docker-compose-example.yaml up -d backend` (o stack completo).
- [ ] Si el passback al LMS en el host deja de funcionar, revisar `lis_outcome_service_url` (localhost vs host alcanzable desde el contenedor).

---

## 7. Producción

En entornos bien configurados:

- El LMS expone **URLs públicas** (`https://...`); el backend debe poder alcanzarlas por red.
- Los servicios internos usan nombres estables (`openwebui`, `kb`, etc.) en la orquestación.
- Se evita alternar root en volumen y usuario local sobre los mismos directorios sin política (usuario fijo en imagen, volúmenes dedicados).

Los problemas descritos aquí son sobre todo de **desarrollo local** y de **mezclar** ejecución en contenedor y en host sobre el mismo clone.

---

## 8. Referencias en el repo

- Compose de ejemplo: [docker-compose-example.yaml](../../docker-compose-example.yaml)
- Variables de entorno: [backend/.env.example](../../backend/.env.example)
- Passback LTI (file-eval): [backend/lamb/modules/file_evaluation/lti_passback.py](../../backend/lamb/modules/file_evaluation/lti_passback.py)
- Lanzamiento LTI y `lis_outcome_service_url`: [backend/lamb/lti_router.py](../../backend/lamb/lti_router.py)
- Comandos generales del stack: [CLAUDE.md](../../CLAUDE.md)
