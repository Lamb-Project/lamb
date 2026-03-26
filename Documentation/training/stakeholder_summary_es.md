# Plataforma LAMB -- Resumen para Partes Interesadas

**Version:** 1.0
**Fecha:** 15 de febrero de 2026
**Audiencia:** Docentes, Administradores Institucionales, Administradores de Sistemas

---

## Tabla de Contenidos

1. [¿Qué es LAMB?](#1-qué-es-lamb)
2. [La Filosofía: IA Segura en la Educación](#2-la-filosofía-ia-segura-en-la-educación)
3. [¿Para quién es LAMB?](#3-para-quién-es-lamb)
4. [Capacidades Principales](#4-capacidades-principales)
5. [Cómo Funciona -- Para Docentes](#5-cómo-funciona--para-docentes)
6. [Cómo Funciona -- Integración LTI con Moodle](#6-cómo-funciona--integración-lti-con-moodle)
7. [Cómo Funciona -- Para Administradores Institucionales](#7-cómo-funciona--para-administradores-institucionales)
8. [Cómo Funciona -- Para Administradores de Sistemas](#8-cómo-funciona--para-administradores-de-sistemas)
9. [Evaluación Asistida por IA: Evaluaitor y LAMBA](#9-evaluación-asistida-por-ia-evaluaitor--lamba)
10. [Arquitectura General](#10-arquitectura-general)
11. [Privacidad y Soberanía de Datos](#11-privacidad-y-soberanía-de-datos)
12. [Glosario](#12-glosario)

---

## 1. ¿Qué es LAMB?

**LAMB** (Learning Assistants Manager and Builder) es una plataforma de código abierto que permite a los educadores crear, gestionar y desplegar asistentes de aprendizaje basados en IA directamente en Sistemas de Gestión del Aprendizaje (como Moodle) -- **sin necesidad de escribir código**.

Piense en LAMB como un **"constructor de chatbots educativos"**: permite a los educadores combinar modelos de lenguaje de gran tamaño (GPT-4, Mistral, modelos alojados localmente, etc.) con sus propios materiales del curso para crear tutores de IA especializados a los que los estudiantes pueden acceder directamente desde Moodle.

### La Propuesta en Una Frase

> **LAMB otorga a los educadores control total para construir un "ChatGPT especializado" para su asignatura, conectarlo a Moodle y mantener los datos de los estudiantes completamente seguros.**

### Propuesta de Valor Principal

| Para... | LAMB ofrece... |
|--------|------------------|
| **Docentes** | Un constructor sin código para crear tutores de IA basados en materiales del curso |
| **Instituciones** | Despliegue de IA manteniendo la soberanía y privacidad de los datos |
| **Estudiantes** | Asistencia de IA contextualizada y específica por materia dentro de su LMS habitual |

### Fundamento Académico

LAMB no es un producto comercial de una startup. Está desarrollado por investigadores universitarios y ha sido revisado por pares:

> *"LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems"*
> Marc Alier, Juanan Pereira, Francisco Jose Garcia-Penalvo, Maria Jose Casan, Jose Cabre
> *Computer Standards & Interfaces*, Volume 92, March 2025

El proyecto está liderado por **Marc Alier** (Universitat Politecnica de Catalunya, Barcelona) y **Juanan Pereira** (Universidad del País Vasco / Euskal Herriko Unibertsitatea, País Vasco), con la colaboración de la Universidad de Salamanca (Grupo de Investigación Grial) y Tknika (Centro de Investigación Aplicada de Formación Profesional del País Vasco).

---

## 2. La Filosofía: IA Segura en la Educación

LAMB está construido sobre los principios del **Manifiesto de IA Segura en la Educación** (https://manifesto.safeaieducation.org), un marco firmado por más de 87 académicos de todo el mundo, incluyendo al Dr. Charles Severance (Universidad de Michigan, creador de Coursera).

La creencia central del manifiesto: **"La IA siempre debe estar al servicio de las personas, potenciando las capacidades humanas en lugar de reemplazarlas."**

### Los Siete Principios

| # | Principio | Lo Que Significa para la Educación | Cómo lo Implementa LAMB |
|---|-----------|----------------------------|----------------------|
| 1 | **Supervisión Humana** | Todas las decisiones permanecen bajo supervisión humana. La IA no puede ser responsable de educar a los estudiantes. | Los educadores crean, controlan y gestionan todos los asistentes. El comportamiento de cada asistente es definido por el educador. |
| 2 | **Protección de la Privacidad** | Los datos de los estudiantes deben ser protegidos. Los estudiantes conservan el control total sobre sus datos personales. | Infraestructura autoalojada. Ningún dato de los estudiantes sale de la institución. No se envían datos personales identificables a proveedores externos de LLM sin configuración institucional explícita. |
| 3 | **Alineación Educativa** | La IA debe apoyar las estrategias educativas institucionales, no socavarlas. | Los asistentes se basan en materiales específicos del curso y objetivos de aprendizaje. Solo responden dentro del ámbito definido por el educador. |
| 4 | **Integración Didáctica** | La IA debe integrarse de forma fluida en los flujos de trabajo docentes existentes. | La integración LTI incorpora los asistentes directamente en los cursos de Moodle. Los estudiantes no necesitan inicios de sesión ni plataformas separadas. |
| 5 | **Precisión y Explicabilidad** | Las respuestas de la IA deben ser precisas y rastreables. | RAG (Generación Aumentada por Recuperación) proporciona citaciones automáticas de fuentes. El modo de depuración permite a los educadores inspeccionar exactamente lo que la IA "ve". |
| 6 | **Interfaces Transparentes** | Las interfaces deben comunicar claramente las limitaciones de la IA. | Comunicación clara de que las respuestas son generadas por IA. Se citan los documentos fuente cuando se hace referencia a ellos. |
| 7 | **Entrenamiento Ético** | Los modelos de IA deben ser entrenados éticamente con transparencia sobre las fuentes de datos. | Plataforma de código abierto. Los educadores eligen su proveedor de LLM. Total transparencia sobre qué modelos se utilizan. |

### ¿Por Qué No Usar Simplemente ChatGPT o Google Gemini?

El manifiesto y LAMB abordan una preocupación real: cuando los educadores usan directamente plataformas comerciales de IA:

- **Entregan su conocimiento** -- los prompts y materiales se convierten en datos de entrenamiento para el proveedor
- **Exponen datos de los estudiantes** -- las identidades, preguntas y comportamiento de los estudiantes son procesados por terceros
- **No tienen transparencia** -- cómo se comporta el modelo, qué datos retiene y cómo evoluciona son aspectos opacos
- **No pueden personalizar el comportamiento** -- no hay forma de restringir las respuestas a los materiales del curso ni de aplicar enfoques pedagógicos
- **Arriesgan la dependencia del proveedor** -- cambiar de proveedor implica reconstruir todo

LAMB resuelve todos estos problemas otorgando a la institución control total sobre toda la pila tecnológica.

---

## 3. ¿Para quién es LAMB?

### Docentes (Usuarios Creadores)

Los docentes son los usuarios principales de LAMB. Utilizan la **Interfaz de Creación** -- un entorno web sin código -- para:

- Crear asistentes de IA especializados para sus cursos
- Construir bases de conocimiento a partir de múltiples fuentes: carga de archivos (PDF, Word, PowerPoint, hojas de cálculo, Markdown), URLs web y sitios web rastreados, y transcripciones de vídeos de YouTube
- Configurar cómo se comporta la IA (prompts de sistema, selección de modelo, ajustes de RAG)
- Crear rúbricas de evaluación estructuradas y adjuntarlas a los asistentes para la evaluación asistida por IA (Evaluaitor)
- Configurar actividades de calificación donde los estudiantes envían trabajos, la IA propone una evaluación basada en una rúbrica, y el docente revisa y decide la calificación final (LAMBA)
- Probar los asistentes antes de publicarlos para los estudiantes
- Publicar asistentes como actividades LTI en Moodle
- Ver analíticas sobre cómo los estudiantes usan sus asistentes

**No se requieren habilidades de programación.** La IA nunca califica de forma autónoma -- asiste al docente proponiendo evaluaciones, pero el docente siempre revisa, edita y confirma la calificación final. Un docente puede crear y publicar su primer asistente en aproximadamente 15 minutos.

### Administradores Institucionales (Administradores de Organización)

Los administradores de organización gestionan su departamento o institución dentro de LAMB:

- Gestionar usuarios dentro de su organización (crear, habilitar/deshabilitar)
- Configurar proveedores de IA (claves API, modelos disponibles)
- Establecer políticas de registro (registro abierto vs. solo por invitación)
- Habilitar/deshabilitar funciones como el uso compartido de asistentes
- Gestionar el acceso LTI Creator para su organización

### Administradores de Sistemas

Los administradores de sistemas gestionan el despliegue de LAMB en sí:

- Desplegar y mantener la infraestructura de LAMB
- Crear y gestionar organizaciones (multi-tenencia)
- Configurar proveedores globales de LLM y claves API
- Gestionar usuarios y roles a nivel de sistema
- Configurar credenciales LTI
- Supervisar el estado y rendimiento del sistema

---

## 4. Capacidades Principales

### Para la Docencia

| Capacidad | Descripción |
|-----------|-------------|
| **Asistentes Ilimitados** | Crear tantos asistentes de IA como sean necesarios, cada uno con un comportamiento único |
| **Tutores Especializados por Materia** | Asistentes que solo responden dentro del contexto del curso definido por el educador |
| **Base de Conocimiento (RAG)** | Ingestión de contenido desde archivos (PDF, Word, PowerPoint, hojas de cálculo), URLs web, rastreo de sitios web y transcripciones de vídeos de YouTube -- la IA los usa como su "libro de texto" |
| **Citaciones Automáticas** | Cuando la IA hace referencia a materiales cargados, cita la fuente |
| **Múltiples Modelos de IA** | Cambiar entre GPT-4o, Mistral, Llama y otros modelos con un solo clic |
| **Modo de Depuración** | Ver el prompt completo enviado a la IA, permitiendo el ajuste fino |
| **Publicación LTI** | Publicar asistentes como actividades de Moodle con unos pocos clics |
| **Compartir Asistentes** | Compartir asistentes con colegas de la misma organización |
| **Evaluadores Basados en Rúbricas** | Crear rúbricas de evaluación estructuradas (manualmente o generadas por IA) y adjuntarlas a asistentes para una evaluación asistida por IA consistente |
| **Evaluación Asistida por IA (LAMBA)** | Los estudiantes envían tareas vía LTI; la IA propone una evaluación según rúbricas; el docente revisa, edita y decide la calificación final; las notas se sincronizan con Moodle |
| **Analíticas de Chat** | Ver cómo los estudiantes interactúan con sus asistentes |
| **Multilingüe** | Interfaz disponible en inglés, español, catalán y euskera |

### Para la Administración

| Capacidad | Descripción |
|-----------|-------------|
| **Multi-Tenencia** | Organizaciones aisladas con configuración independiente |
| **Gestión de Usuarios** | Crear, habilitar/deshabilitar y gestionar cuentas de usuario |
| **Acceso Basado en Roles** | Roles de administrador de sistema, administrador de organización, creador y usuario final |
| **Flexibilidad de Proveedores de LLM** | Configurar OpenAI, Anthropic, Ollama u otros proveedores por organización |
| **Claves de Registro** | Registro específico por organización con claves secretas |
| **Acceso LTI Creator** | Los educadores pueden acceder a LAMB directamente desde Moodle vía LTI |

### Para la Infraestructura

| Capacidad | Descripción |
|-----------|-------------|
| **Autoalojado** | Desplegar en sus propios servidores -- soberanía total de datos |
| **Despliegue con Docker** | Despliegue con un solo comando usando Docker Compose |
| **API Compatible con OpenAI** | Endpoint estándar `/v1/chat/completions` para integración |
| **Arquitectura de Plugins** | Conectores extensibles para nuevos proveedores de LLM |
| **Base de Datos SQLite** | Base de datos simple basada en archivos (no se necesita servidor de base de datos separado) |

---

## 5. Cómo Funciona -- Para Docentes

### El Flujo de Trabajo del Docente (15 Minutos para el Primer Asistente)

#### Paso 1: Iniciar Sesión
Inicie sesión en la Interfaz de Creación de LAMB con sus credenciales institucionales (o vía LTI desde Moodle).

#### Paso 2: Crear un Asistente
Dé a su asistente un nombre y una descripción. Elija un modelo de IA (por ejemplo, GPT-4o-mini para respuestas rápidas, GPT-4o para razonamiento complejo).

#### Paso 3: Definir el Comportamiento
Escriba un **prompt de sistema** que indique a la IA cómo comportarse. Por ejemplo:

> *"Eres un tutor de Introducción a la Informática. Responde solo preguntas relacionadas con algoritmos, estructuras de datos y fundamentos de programación. Cuando los estudiantes pregunten sobre temas fuera del curso, redirecciónales amablemente. Siempre anima a los estudiantes a reflexionar sobre los problemas antes de dar respuestas directas."*

#### Paso 4: Construir una Base de Conocimiento (Opcional pero Recomendado)
Agregue sus materiales del curso desde múltiples fuentes:
- **Cargar archivos** -- apuntes de clase, capítulos de libros de texto, conjuntos de problemas (PDF, Word, PowerPoint, hojas de cálculo, Markdown y más)
- **Ingestar desde URLs** -- apunte a una página web o deje que el rastreador siga enlaces a través de un sitio
- **Importar vídeos de YouTube** -- extraer e indexar automáticamente las transcripciones de vídeos

LAMB procesa e indexa todo el contenido para que la IA pueda referenciarlo al responder preguntas.

#### Paso 5: Configurar RAG
Conecte su base de conocimiento al asistente. Configure cuántos fragmentos de contexto recuperar (Top K). La IA ahora basará sus respuestas en los materiales reales de su curso y citará las fuentes.

#### Paso 6: Probar
Use la interfaz de chat integrada para probar su asistente. Hágale preguntas que sus estudiantes podrían hacer. Use el **modo de depuración** para ver exactamente qué prompt y contexto recibe la IA.

#### Paso 7: Publicar en Moodle
Haga clic en "Publicar". LAMB genera las credenciales LTI (URL de la Herramienta, Clave del Consumidor, Secreto). Añádalas en Moodle como una actividad de Herramienta Externa. Los estudiantes ahora pueden acceder al asistente directamente desde la página de su curso.

### Dos Formas de Acceder a LAMB como Docente

1. **Inicio de sesión directo** -- Navegue a la URL de LAMB e inicie sesión con email/contraseña
2. **Lanzamiento LTI Creator** -- Haga clic en un enlace LTI en Moodle y acceda directamente a la Interfaz de Creación (sin necesidad de contraseña separada). Esto lo configura el administrador de su organización.

---

## 6. Cómo Funciona -- Integración LTI con Moodle

LTI (Learning Tools Interoperability, Interoperabilidad de Herramientas de Aprendizaje) es el protocolo estándar que conecta LAMB con Moodle. LAMB soporta tres modos de integración LTI:

### 6.1 LTI Unificado (Recomendado para Nuevos Despliegues)

El enfoque de **LTI Unificado** utiliza una única herramienta LTI para toda la instancia de LAMB. Es la opción más flexible y con más funcionalidades.

**Cómo funciona:**

1. El administrador de sistemas configura **un único conjunto de credenciales LTI globales** para toda la instancia de LAMB
2. Un administrador de Moodle añade LAMB como Herramienta Externa usando estas credenciales globales
3. Los docentes añaden actividades de LAMB a sus cursos en Moodle
4. **Primera configuración:** Cuando un docente hace clic en la actividad por primera vez, ve una página de configuración donde selecciona qué asistentes publicados poner a disposición
5. **Después de la configuración:** Los estudiantes que hacen clic en la actividad ven los asistentes seleccionados y pueden comenzar a chatear
6. **Panel del docente:** Los docentes obtienen un panel mostrando estadísticas de uso, registros de acceso de estudiantes y (si está habilitado) revisión de transcripciones de chat anonimizadas

**Características principales:**
- Múltiples asistentes por actividad (los estudiantes pueden elegir)
- Panel del docente con estadísticas de uso
- Visibilidad opcional del chat (transcripciones anonimizadas para revisión pedagógica)
- Flujo de consentimiento del estudiante cuando la visibilidad del chat está habilitada
- Un único conjunto de credenciales LTI para toda la instancia

**Experiencia del estudiante:**
1. Hacer clic en el enlace de la actividad en Moodle
2. (Si la visibilidad del chat está habilitada y es el primer acceso) Aceptar un aviso de consentimiento
3. Ver los asistentes disponibles y comenzar a chatear
4. Todo ocurre dentro de Moodle -- no se necesita inicio de sesión separado

### 6.2 LTI Heredado (Un Asistente por Actividad)

El enfoque anterior donde cada asistente publicado tiene sus propias credenciales LTI. Todavía soportado pero menos flexible.

**Cómo funciona:**
1. El docente publica un asistente en LAMB
2. LAMB genera una clave de consumidor y un secreto LTI únicos para ese asistente
3. El docente los añade como Herramienta Externa en Moodle
4. Los estudiantes hacen clic en el enlace y acceden directamente a ese asistente

### 6.3 LTI Creator (Acceso del Docente a LAMB desde Moodle)

Este modo permite a los docentes acceder a la propia Interfaz de Creación de LAMB a través de Moodle, eliminando la necesidad de credenciales de inicio de sesión separadas para LAMB.

**Cómo funciona:**
1. El administrador de organización configura las credenciales de LTI Creator
2. El administrador de Moodle añade LAMB Creator como Herramienta Externa
3. Cuando un docente hace clic en el enlace, accede directamente a la Interfaz de Creación de LAMB
4. Su identidad se vincula a su cuenta del LMS -- no se necesita contraseña separada
5. Pueden crear y gestionar asistentes como de costumbre

---

## 7. Cómo Funciona -- Para Administradores Institucionales

### Gestión de Organizaciones

LAMB utiliza un modelo **multi-tenencia** donde cada institución, departamento o equipo es una **organización**. Las organizaciones proporcionan aislamiento completo:

- Cada organización tiene sus propios usuarios, asistentes y bases de conocimiento
- Cada organización configura sus propios proveedores de IA y claves API
- Los usuarios de una organización no pueden ver los recursos de otra

### Responsabilidades Principales

#### Gestión de Usuarios
- Crear cuentas para docentes (usuarios creadores) y usuarios finales
- Habilitar/deshabilitar cuentas de usuario
- Establecer roles de usuario dentro de la organización (administrador, miembro)
- Gestionar usuarios de LTI Creator que acceden vía Moodle

#### Configuración de Proveedores de IA
- Configurar qué proveedores de IA están disponibles (OpenAI, Anthropic, Ollama, etc.)
- Establecer claves API para cada proveedor
- Definir modelos predeterminados
- Controlar qué modelos pueden usar los docentes

#### Políticas de Acceso
- Habilitar/deshabilitar el registro abierto para la organización
- Establecer una clave de registro para el auto-registro
- Habilitar/deshabilitar el uso compartido de asistentes entre docentes
- Configurar las credenciales de acceso de LTI Creator

#### Tipos de Usuario

| Tipo de Usuario | Acceso | Propósito |
|-----------|--------|---------|
| **Creador** | Interfaz de Creación (constructor de asistentes) | Docentes que crean y gestionan asistentes |
| **Usuario Final** | Solo interfaz de chat (Open WebUI) | Usuarios que solo necesitan interactuar con asistentes publicados |
| **LTI Creator** | Interfaz de Creación (vía Moodle LTI) | Docentes que acceden a LAMB a través de su LMS |

---

## 8. Cómo Funciona -- Para Administradores de Sistemas

### Despliegue

LAMB está diseñado para **despliegue autoalojado** usando Docker Compose. La pila incluye:

| Servicio | Puerto | Propósito |
|---------|------|---------|
| **Backend** (FastAPI) | 9099 | API principal, autenticación, pipeline de completions |
| **Frontend** (Svelte) | 5173 (dev) | Aplicación web de la Interfaz de Creación |
| **Open WebUI** | 8080 | Interfaz de chat para estudiantes y usuarios finales |
| **KB Server** | 9090 | Procesamiento de documentos de la base de conocimiento y búsqueda vectorial |

### Inicio Rápido
```bash
git clone https://github.com/Lamb-Project/lamb.git
cd lamb
./scripts/setup.sh
docker-compose up -d
```

### Configuración Principal

| Variable | Propósito |
|----------|---------|
| `LAMB_DB_PATH` | Ruta al directorio de la base de datos de LAMB |
| `OWI_DATA_PATH` | Ruta al directorio de datos de Open WebUI |
| `LAMB_BEARER_TOKEN` | Clave API para el endpoint de completions (**¡cambiar el valor por defecto!**) |
| `LAMB_JWT_SECRET` | Secreto para firmar tokens JWT (**¡establecer un valor seguro!**) |
| `OPENAI_API_KEY` | Clave API de OpenAI por defecto (puede sobrescribirse por organización) |
| `LTI_GLOBAL_CONSUMER_KEY` | Clave de consumidor LTI global para LTI Unificado |
| `LTI_GLOBAL_SECRET` | Secreto compartido LTI global |
| `OWI_BASE_URL` | URL interna para Open WebUI |
| `OWI_PUBLIC_BASE_URL` | URL pública para Open WebUI |

### Tareas de Administración del Sistema

- **Crear organizaciones** -- Configurar tenants aislados para departamentos o instituciones
- **Gestionar usuarios globales** -- Crear cuentas de administrador de sistema, gestionar todos los usuarios
- **Configurar LTI** -- Establecer credenciales LTI globales para LTI Unificado
- **Supervisar el estado** -- Endpoint `GET /status` para comprobaciones de salud
- **Copias de seguridad de la base de datos** -- Realizar copias de seguridad de los archivos de base de datos SQLite regularmente
- **SSL/TLS** -- Configurar HTTPS vía Caddy o proxy inverso
- **Gestión de proveedores de LLM** -- Configurar valores por defecto a nivel de sistema, supervisar el uso de la API

### Lista de Verificación para Producción

- [ ] Cambiar `LAMB_BEARER_TOKEN` del valor por defecto
- [ ] Establecer `LAMB_JWT_SECRET` con un valor aleatorio seguro
- [ ] Configurar SSL/TLS (se recomienda Caddy)
- [ ] Establecer copias de seguridad regulares de la base de datos
- [ ] Configurar claves API de LLM específicas por organización
- [ ] Establecer el nivel de registro (`GLOBAL_LOG_LEVEL=WARNING` para producción)
- [ ] Configurar la supervisión del sistema
- [ ] Probar la integración LTI de extremo a extremo

### Arquitectura Multi-Tenencia

```
Organización del Sistema (siempre existe, no se puede eliminar)
    |
    +-- Departamento A (slug: "engineering")
    |   +-- Usuarios (con roles: propietario, administrador, miembro)
    |   +-- Asistentes
    |   +-- Bases de Conocimiento
    |   +-- Configuración independiente de proveedores de LLM
    |
    +-- Departamento B (slug: "physics")
    |   +-- Usuarios
    |   +-- Asistentes
    |   +-- Bases de Conocimiento
    |   +-- Configuración independiente de proveedores de LLM
    |
    +-- Institución Asociada (slug: "partner-univ")
        +-- ...
```

---

## 9. Evaluación Asistida por IA: Evaluaitor y LAMBA

LAMB incluye un sistema **Evaluaitor** integrado para la evaluación basada en rúbricas, y la aplicación **LAMBA** (Learning Activities & Machine-Based Assessment, Actividades de Aprendizaje y Evaluación Basada en Máquinas) se está integrando en la plataforma para proporcionar un pipeline completo de evaluación asistida por IA. Es fundamental destacar que **la IA nunca califica de forma autónoma** -- propone evaluaciones que el docente debe revisar, editar si es necesario y aprobar explícitamente antes de que cualquier calificación llegue al estudiante. Esta es una aplicación directa del Principio 1 del Manifiesto (Supervisión Humana).

### 9.1 Evaluaitor: Evaluación Basada en Rúbricas

Evaluaitor es el sistema de gestión de rúbricas de LAMB. Permite a los docentes crear rúbricas de evaluación estructuradas y adjuntarlas a los asistentes, convirtiendo cualquier asistente en un evaluador de IA consistente.

#### Creación de Rúbricas

Los docentes pueden crear rúbricas de tres maneras:

1. **Creación manual** -- Definir criterios, niveles de desempeño, pesos y puntuación desde cero
2. **Generación por IA** -- Describir en lenguaje natural lo que se desea evaluar y la IA genera una rúbrica completa (soporta inglés, español, catalán y euskera)
3. **Desde plantillas** -- Duplicar una rúbrica pública compartida por colegas o promovida por administradores como plantilla de referencia

#### Estructura de la Rúbrica

Cada rúbrica contiene:
- **Título y descripción** -- Qué se está evaluando
- **Criterios** -- Las dimensiones de la evaluación (por ejemplo, "Calidad del Contenido", "Pensamiento Crítico"), cada uno con un peso
- **Niveles de desempeño** -- Descripciones para cada nivel de calidad (por ejemplo, Ejemplar / Competente / En Desarrollo / Inicial) con puntuaciones
- **Tipo de puntuación** -- Puntos, porcentaje, holístico, punto único o lista de verificación
- **Metadatos** -- Área de conocimiento, nivel educativo

#### Uso de Rúbricas con Asistentes

Cuando una rúbrica se adjunta a un asistente, el pipeline de completions de LAMB inyecta automáticamente la rúbrica en el contexto de la IA con formato optimizado para la evaluación -- incluyendo instrucciones de puntuación, cálculos de pesos y formato de salida esperado. Esto significa que la IA produce evaluaciones propuestas consistentes según los criterios específicos de la rúbrica, que el docente luego revisa y finaliza.

#### Compartir y Plantillas

- Las rúbricas pueden ser **privadas** (solo las ve el creador) o **públicas** (visibles para todos los miembros de la organización)
- Los administradores pueden promover rúbricas como **plantillas de referencia** disponibles en toda la plataforma
- Las rúbricas se pueden **exportar/importar** como JSON para compartir entre instituciones

### 9.2 LAMBA: El Pipeline de Calificación (En Integración)

LAMBA comenzó como una aplicación LTI separada y ahora se está integrando directamente en LAMB. Proporciona el ciclo de vida completo de la evaluación a través de Moodle:

#### El Flujo de Trabajo de Evaluación

1. **Los docentes crean actividades de evaluación** en Moodle vía LTI y asignan un asistente evaluador basado en rúbricas
2. **Los estudiantes cargan documentos** (PDF, Word, TXT, código fuente) a través de la interfaz de Moodle
3. **La IA propone evaluaciones** -- el asistente analiza cada entrega según la rúbrica y produce una puntuación sugerida y retroalimentación escrita
4. **Los docentes revisan las propuestas de la IA** -- pueden aceptar, editar o anular completamente la puntuación y retroalimentación sugerida para cada estudiante
5. **Los docentes confirman la calificación final** -- solo la calificación aprobada por el docente es la calificación real
6. **Las calificaciones finales se sincronizan con el libro de calificaciones de Moodle** vía LTI

#### Características Principales

| Característica | Descripción |
|---------|-------------|
| **Propuestas Basadas en Rúbricas** | La IA propone evaluaciones según rúbricas estructuradas, dando al docente un punto de partida consistente |
| **El Docente Tiene la Última Palabra** | La sugerencia de la IA y la calificación real son campos separados -- el docente debe transferir explícitamente la evaluación propuesta a la calificación final, editándola según sea necesario |
| **Entregas Grupales** | Soporta tareas grupales con códigos de entrega compartidos |
| **Sincronización de Calificaciones con Moodle** | Solo las calificaciones finales confirmadas por el docente se envían al libro de calificaciones de Moodle |
| **Procesamiento por Lotes** | Solicitar propuestas de IA para todas las entregas a la vez con seguimiento de progreso en tiempo real |
| **Supervisión Humana** | La IA asiste; el docente decide -- consistente con el Principio 1 del Manifiesto |

#### Objetivo

Reducir la carga de trabajo de evaluación del docente en un **50%** en evaluaciones rutinarias, entregando retroalimentación propuesta en minutos en lugar de días. La IA proporciona un punto de partida consistente basado en rúbricas, pero **el docente siempre conserva la autoridad total sobre la calificación final**.

---

## 10. Arquitectura General

```
+------------------------------------------------------------------+
|                       Plataforma LAMB                            |
|                                                                  |
|   +----------------+    +----------------+    +----------------+ |
|   |   Interfaz de  |    |   Backend      |    |   Open WebUI   | |
|   |   Creación     |<-->|   (FastAPI)     |<-->|   (Chat UI)    | |
|   |   (Svelte)     |    |   Puerto 9099  |    |   Puerto 8080  | |
|   +----------------+    +-------+--------+    +----------------+ |
|          |                      |                      |         |
|    Los docentes           Lógica central         Los estudiantes |
|    usan esto para         y API                  usan esto para  |
|    crear asistentes             |                chatear         |
|                          +------+-------+                        |
|                          |  KB Server   |                        |
|                          |  Puerto 9090 |                        |
|                          +--------------+                        |
|                                 |                                |
|                          +------+-------+                        |
|                          | Proveedor LLM|                        |
|                          | OpenAI/Ollama|                        |
|                          +--------------+                        |
+------------------------------------------------------------------+
         |                                           |
    LTI Creator                                 LTI Estudiante
    (Los docentes acceden                       (Los estudiantes acceden
     a LAMB desde Moodle)                        a asistentes desde Moodle)
         |                                           |
+------------------------------------------------------------------+
|                     Moodle (LMS)                                 |
+------------------------------------------------------------------+
```

### Cómo Se Responde la Pregunta de un Estudiante

1. El estudiante escribe una pregunta en la interfaz de chat (Open WebUI, lanzada vía LTI)
2. La pregunta llega a la API de completions de LAMB
3. LAMB carga la configuración del asistente (prompt de sistema, modelo, ajustes de RAG)
4. El **Procesador RAG** consulta la base de conocimiento buscando contenido relevante de los documentos cargados
5. El **Procesador de Prompts** combina el prompt de sistema, el contexto recuperado y la pregunta del estudiante
6. El **Conector** envía todo al LLM configurado (por ejemplo, OpenAI GPT-4o)
7. La respuesta del LLM se transmite de vuelta al estudiante con citaciones de fuentes

---

## 11. Privacidad y Soberanía de Datos

### Dónde Residen los Datos

| Datos | Ubicación | Quién los Controla |
|------|----------|----------------|
| Cuentas de usuario | Base de datos de LAMB (servidor de la institución) | La institución |
| Configuraciones de asistentes | Base de datos de LAMB | El educador + la institución |
| Materiales del curso (BCs) | ChromaDB en el servidor de la institución | El educador + la institución |
| Historial de chat | Base de datos de Open WebUI en el servidor de la institución | La institución |
| Interacciones de estudiantes | Servidor de la institución | La institución |

### Lo Que NO Sale de la Institución

- Identidades y datos personales de los estudiantes
- Conversaciones de chat e historial de interacciones
- Materiales del curso cargados y bases de conocimiento
- Analíticas de uso y datos de evaluación

### Lo Que Se Envía a Servicios Externos (Configurable)

- **Solo el texto de las preguntas y el contexto** se envía al proveedor de LLM configurado (OpenAI, etc.)
- Esto puede **eliminarse por completo** utilizando modelos alojados localmente (Ollama con Llama, Mistral, etc.)
- La institución elige qué proveedor de LLM usar y puede cambiarlo en cualquier momento

### Alineación con RGPD y FERPA

- Autoalojado: cumplimiento total con los requisitos de residencia de datos
- No se requieren registros obligatorios en servicios de terceros para los estudiantes
- Los estudiantes acceden a los asistentes a través de su LMS existente -- no se necesitan cuentas nuevas
- Retención de datos clara bajo control institucional
- La visibilidad opcional del chat requiere consentimiento explícito del estudiante

---

## 12. Glosario

| Término | Definición |
|------|-----------|
| **Asistente** | Un chatbot basado en IA configurado por un docente con comportamiento, conocimiento y ajustes de modelo específicos |
| **Interfaz de Creación** | La interfaz web donde los docentes construyen y gestionan asistentes |
| **Base de Conocimiento (BC)** | Una colección de documentos cargados que la IA puede referenciar al responder preguntas |
| **RAG** | Retrieval-Augmented Generation (Generación Aumentada por Recuperación) -- la técnica de recuperar fragmentos relevantes de documentos para incluirlos en los prompts de la IA |
| **LTI** | Learning Tools Interoperability (Interoperabilidad de Herramientas de Aprendizaje) -- el protocolo estándar para conectar herramientas externas a un LMS |
| **LMS** | Learning Management System (Sistema de Gestión del Aprendizaje) (por ejemplo, Moodle, Canvas) |
| **Organización** | Un tenant aislado en LAMB (departamento, institución o equipo) con sus propios usuarios y configuración |
| **Open WebUI (OWI)** | El componente de interfaz de chat donde los estudiantes interactúan con los asistentes publicados |
| **Prompt de Sistema** | Instrucciones que definen cómo se comporta un asistente de IA (personalidad, reglas, limitaciones) |
| **Conector** | Un plugin que conecta LAMB con un proveedor de LLM específico (OpenAI, Ollama, Anthropic) |
| **LTI Unificado** | El modo LTI recomendado donde una herramienta sirve múltiples asistentes por actividad |
| **LTI Creator** | Un modo LTI que permite a los docentes acceder a la Interfaz de Creación desde dentro de Moodle |
| **Evaluaitor** | El sistema de gestión de rúbricas integrado en LAMB para crear criterios de evaluación estructurados |
| **Rúbrica** | Un conjunto estructurado de criterios con niveles de desempeño y pesos utilizado para evaluar el trabajo de los estudiantes de manera consistente |
| **LAMBA** | Learning Activities & Machine-Based Assessment (Actividades de Aprendizaje y Evaluación Basada en Máquinas) -- el pipeline de evaluación asistida por IA (en proceso de integración en LAMB). La IA propone evaluaciones; el docente decide la calificación final. |
| **Manifiesto** | El Manifiesto de IA Segura en la Educación -- el marco ético que guía el diseño de LAMB |

---

## Enlaces Principales

| Recurso | URL |
|----------|-----|
| Repositorio GitHub de LAMB | https://github.com/Lamb-Project/lamb |
| Sitio Web del Proyecto LAMB | https://lamb-project.org |
| LAMBA (Extensión de Calificación) | https://github.com/Lamb-Project/LAMBA |
| Manifiesto de IA Segura en la Educación | https://manifesto.safeaieducation.org |
| Lista de Verificación del Manifiesto | https://manifesto.safeaieducation.org/checklist |
| Artículo de Investigación (DOI) | https://doi.org/10.1016/j.csi.2024.103940 |

---

*Este documento fue preparado como material de formación para las partes interesadas del proyecto LAMB.*
*Última actualización: 15 de febrero de 2026*
