# LAMB - Learning Assistant Manager and Builder
## Plataforma para crear herramientas educativas con IA sin programar

---

# 1. ¿QUÉ ES LAMB?

## Una plataforma, múltiples herramientas educativas

LAMB (Learning Assistant Manager and Builder) es una **plataforma open-source** que permite a docentes crear herramientas educativas potenciadas por inteligencia artificial de forma visual e intuitiva, **sin necesidad de programar**.

LAMB no es simplemente un "constructor de chatbots". Es una plataforma extensible que actualmente ofrece dos tipos de herramientas:

| Herramienta | Descripción | Caso de uso típico |
|-------------|-------------|-------------------|
| **Asistentes de aprendizaje** | Chatbots aumentados con RAG que conocen tus materiales | Tutorías, resolución de dudas, consulta de contenidos |
| **Actividades con evaluación automática (LAMBA)** | Gestión de entregas con feedback y calificación basada en rúbricas | Tareas, trabajos, ejercicios evaluables |

Ambas herramientas comparten la misma filosofía: **tú defines el conocimiento, las instrucciones y las rúbricas**; la IA se encarga de interactuar con los estudiantes siguiendo tus criterios.

**Proyecto open-source desarrollado por:**
- Marc Alier (Universitat Politècnica de Catalunya - UPC)
- Juanan Pereira (Universidad del País Vasco - UPV/EHU)

**Enlaces importantes:**
- Web oficial: www.lamb-project.org
- Repositorio GitHub: github.com/Lamb-Project/lamb
- Manifiesto de IA Segura en Educación: manifesto.safeaieducation.org

---

# 2. ¿POR QUÉ USAR LAMB?

## El problema con los servicios comerciales

Cuando usas ChatGPT, Gemini u otros servicios directamente con tus estudiantes:

- **No controlas las instrucciones**: El proveedor tiene sus propias directrices ocultas
- **Tu conocimiento queda expuesto**: Los documentos y rúbricas que subes se almacenan en servidores externos
- **Los datos de tus estudiantes van a terceros**: Todas las interacciones son procesadas por empresas externas
- **No tienes registros completos**: No sabes exactamente cómo usan tus estudiantes la herramienta
- **No puedes integrar en el LMS**: Los estudiantes deben usar servicios externos
- **Problemas de privacidad**: Puede que no cumplas con GDPR o políticas institucionales

## Lo que LAMB te ofrece

Con LAMB, **tú tienes el control total**:

| Aspecto | Servicios comerciales | Con LAMB |
|---------|----------------------|----------|
| Instrucciones y rúbricas | Las del proveedor + las tuyas | Solo las que tú defines |
| Conocimiento | Se queda con el proveedor | Permanece en tu infraestructura |
| Datos de estudiantes | Procesados por terceros | Se quedan en tu sistema |
| Registros de uso | Limitados o inexistentes | Completos y accesibles |
| Modelo de IA | El que ofrece el servicio | Tú eliges (y puedes cambiar) |
| Integración LMS | Manual o inexistente | Nativa vía LTI |
| Calificaciones | Copiar/pegar manual | Sincronización automática con Moodle |

---

# 3. LAS HERRAMIENTAS DE LAMB

## 3.1 Asistentes de Aprendizaje (Chatbots con RAG)

### ¿Qué son?

Son chatbots educativos que **conocen tus materiales** y responden basándose en ellos. Utilizan RAG (Retrieval Augmented Generation) para recuperar información relevante de tus documentos antes de generar cada respuesta.

### Características

- **Base de conocimiento propia**: Sube PDFs, Word, Markdown con tu contenido
- **Respuestas fundamentadas**: El asistente cita las fuentes de sus respuestas
- **Comportamiento configurable**: Define instrucciones, tono, límites
- **Múltiples modelos**: GPT-4, Claude, Mistral, modelos locales
- **Integración LMS**: Acceso directo desde Moodle vía LTI

### Casos de uso

- **Tutor de contenidos**: Responde dudas sobre el temario citando los apuntes
- **Experto simulado**: Proporciona conocimiento experto para análisis de casos
- **Coach de aprendizaje**: Guía al estudiante con preguntas en lugar de dar respuestas directas
- **Consulta de normativa**: Responde sobre legislación o documentación técnica citando artículos

### Ejemplo real: Macroeconomics Study Coach

Un asistente alimentado con 30 videolecciones transcritas. Cuando un estudiante pregunta sobre un concepto, responde citando la lección específica e incluye el enlace al momento exacto del vídeo.

---

## 3.2 Actividades con Evaluación Automática (LAMBA)

### ¿Qué es LAMBA?

LAMBA (Learning Activities & Machine-Based Assessment) es el módulo de LAMB para **gestionar entregas de tareas y evaluarlas automáticamente** usando rúbricas e inteligencia artificial.

### Características

- **Gestión de actividades**: Crea tareas individuales o grupales con fechas límite
- **Sistema de entregas**: Los estudiantes suben documentos (PDF, DOCX, TXT)
- **Entregas grupales**: Los estudiantes pueden formar grupos con códigos compartidos
- **Evaluación con IA**: Conecta un evaluador LAMB que aplica tu rúbrica automáticamente
- **Feedback detallado**: Los estudiantes reciben retroalimentación basada en los criterios de la rúbrica
- **Sincronización de notas**: Las calificaciones se envían automáticamente a Moodle
- **Multiidioma**: Interfaz en catalán, español e inglés

### El flujo completo
```
┌─────────────────────────────────────────────────────────────────┐
│                         PROFESOR                                │
├─────────────────────────────────────────────────────────────────┤
│  1. Crea actividad en LAMBA (título, descripción, fecha)        │
│  2. Define o selecciona la rúbrica de evaluación                │
│  3. Asocia un evaluador LAMB (asistente IA con la rúbrica)      │
│  4. Configura la actividad en Moodle como herramienta LTI       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                        ESTUDIANTE                               │
├─────────────────────────────────────────────────────────────────┤
│  1. Accede a la actividad desde Moodle                          │
│  2. Lee la descripción y los criterios                          │
│  3. Sube su documento (individual o se une a un grupo)          │
│  4. Recibe feedback automático basado en la rúbrica             │
│  5. La calificación aparece automáticamente en Moodle           │
└─────────────────────────────────────────────────────────────────┘
```

### ¿Cómo funciona la evaluación?

1. El estudiante sube su documento
2. LAMBA extrae el texto del documento
3. El texto se envía al evaluador LAMB asociado
4. El evaluador (un asistente IA configurado con tu rúbrica) analiza el contenido
5. Genera feedback estructurado según los criterios de la rúbrica
6. Asigna una calificación
7. La nota se sincroniza automáticamente con el libro de calificaciones de Moodle

### Casos de uso

- **Trabajos escritos**: Ensayos, informes, análisis evaluados según criterios específicos
- **Ejercicios prácticos**: Resolución de problemas con feedback inmediato
- **Entregas grupales**: Proyectos de equipo con evaluación compartida
- **Evaluación formativa**: Feedback rápido para que el estudiante mejore antes de la entrega final

---

# 4. CONCEPTOS CLAVE

## Bases de Conocimiento

Son colecciones de documentos procesados que alimentan a los asistentes. LAMB:
- Acepta PDF, Word (DOCX), Markdown, TXT, archivos ZIP
- Extrae y estructura el contenido automáticamente
- Crea embeddings semánticos para búsqueda por significado
- Permite organizar el conocimiento en bases separadas por tema

## RAG (Retrieval Augmented Generation)

Es la técnica que permite a los asistentes "conocer" tus materiales:
1. El estudiante hace una pregunta
2. LAMB busca en la base de conocimiento los fragmentos más relevantes
3. Esos fragmentos se incluyen como contexto para el modelo de IA
4. El modelo genera una respuesta basada en ese contexto
5. El asistente cita las fuentes utilizadas

## Rúbricas

Son los criterios de evaluación que guían al evaluador automático:
- Define dimensiones (ej: contenido, estructura, argumentación)
- Especifica niveles de logro para cada dimensión
- El evaluador IA aplica estos criterios al analizar las entregas
- El feedback se estructura según las dimensiones de la rúbrica

## Integración LTI

LTI (Learning Tools Interoperability) es el estándar que permite:
- Incrustar herramientas LAMB en Moodle (y otros LMS)
- Autenticar estudiantes con credenciales institucionales
- Sincronizar calificaciones automáticamente con el libro de notas
- Mantener el contexto del curso (qué actividad, qué estudiante)

---

# 5. TUTORIAL: CREA TU PRIMER ASISTENTE DE APRENDIZAJE

## Paso 1: Registro y acceso

1. Accede a la instancia de LAMB de tu institución
2. Pulsa "Sign Up" y completa el formulario
3. Introduce la "Secret Key" proporcionada por tu coordinación

## Paso 2: Crea una base de conocimiento

1. Ve a "Knowledge Bases" → "New"
2. Ponle un nombre descriptivo (ej: "Materiales Economía 101")
3. Marca como "Private" si es necesario
4. Guarda

### Sube tus documentos

1. Dentro de tu base, pulsa "Markdown Ingest"
2. Arrastra tus archivos: PDFs, Word, Markdown, TXT o ZIP
3. Configura el "Chunk size" (~2000 para textos largos)
4. Espera a que se procesen

## Paso 3: Crea el asistente

1. Ve a "My Assistants" → "New"
2. Configura:
   - **Nombre**: Ej. "Tutor de Economía"
   - **Descripción**: Qué hace el asistente
   - **Modelo**: Elige el LLM (GPT-4o, Mistral, etc.)
3. En la sección **RAG**:
   - Selecciona tu base de conocimiento
   - Configura k=3 (fragmentos a recuperar)
4. Guarda

## Paso 4: Prueba y ajusta

1. Usa el chat integrado para probar el asistente
2. Activa el modo "Debug" para ver el prompt completo
3. Ajusta las instrucciones según los resultados

## Paso 5: Publica en Moodle

1. En el asistente, pulsa "Publish"
2. Copia: Tool URL, Consumer Key, Shared Secret
3. En Moodle → "Añadir actividad" → "External Tool"
4. Pega los datos y configura "Launch container" → "New window"
5. Guarda

**¡Listo!** Los estudiantes ya pueden acceder desde Moodle.

---

# 6. TUTORIAL: CREA UNA ACTIVIDAD CON EVALUACIÓN AUTOMÁTICA (LAMBA)

## Requisitos previos

- Tener acceso a una instancia de LAMB con LAMBA habilitado
- Tener configurado un evaluador LAMB con tu rúbrica (o crearlo)

## Paso 1: Accede a LAMBA

1. Accede a LAMBA como profesor (desde Moodle o directamente)
2. O accede al panel de administración en `/admin`

## Paso 2: Crea la actividad

1. Ve a la gestión de actividades
2. Crea una nueva actividad con:
   - **Título**: Nombre de la tarea (debe coincidir con el nombre en Moodle)
   - **Descripción**: Instrucciones para los estudiantes
   - **Tipo**: Individual o grupal
   - **Fecha límite**: Opcional
   - **ID del evaluador LAMB**: El asistente IA que evaluará las entregas

## Paso 3: Configura el evaluador

El evaluador es un asistente LAMB configurado específicamente para evaluar según tu rúbrica:
- Contiene las instrucciones de evaluación
- Conoce los criterios y niveles de la rúbrica
- Genera feedback estructurado y calificación

## Paso 4: Configura en Moodle

1. En tu curso Moodle → "Añadir actividad" → "External Tool"
2. Selecciona LAMBA como herramienta preconfigurada
3. **Importante**: El nombre de la actividad debe coincidir con el título en LAMBA
4. Configura las calificaciones:
   - Permitir que LAMBA añada calificaciones
   - Calificación máxima: 10
   - Calificación para aprobar: 5.00
5. Guarda

## Paso 5: Flujo del estudiante

1. El estudiante accede desde Moodle
2. Ve la descripción y sube su documento
3. (Si es grupal) Se une a un grupo con código compartido o crea uno nuevo
4. Recibe feedback automático del evaluador
5. La nota aparece en el libro de calificaciones de Moodle

## Paso 6: Revisión del profesor

- Puedes ver todas las entregas en el panel de LAMBA
- Revisar el feedback generado por la IA
- Ajustar calificaciones manualmente si es necesario
- Reenviar notas a Moodle si haces cambios

---

# 7. CASOS DE USO Y EJEMPLOS

## Asistentes de aprendizaje

### Tutor de contenidos con videoclases
**Configuración**: Transcripciones de videolecciones + apuntes
**Comportamiento**: Responde dudas citando la lección y el minuto del vídeo
**Ejemplo real**: Macroeconomics Study Coach (30 videolecciones)

### Panel de expertos simulado
**Configuración**: Entrevistas transcritas a expertos reales + documentación
**Comportamiento**: Proporciona conocimiento experto sin hacer el análisis por el estudiante
**Ejemplo real**: Análisis PESTLE con expertos en cada dimensión

### Coach de programación
**Configuración**: Ejercicios, ejemplos resueltos, documentación
**Comportamiento**: Guía con preguntas y pistas, NO escribe código completo

### Consultor de normativa
**Configuración**: Legislación, reglamentos, documentos técnicos
**Comportamiento**: Responde citando artículos específicos

## Actividades evaluables con LAMBA

### Ensayo argumentativo
**Rúbrica**: Tesis, argumentación, evidencias, estructura, redacción
**Feedback**: Comentarios específicos en cada dimensión + nota global

### Informe técnico
**Rúbrica**: Precisión técnica, metodología, presentación de datos, conclusiones
**Feedback**: Identificación de errores y sugerencias de mejora

### Análisis de caso
**Rúbrica**: Comprensión del caso, aplicación de teoría, profundidad del análisis
**Feedback**: Retroalimentación formativa para mejorar

### Proyecto grupal
**Configuración**: Actividad grupal con código compartido
**Rúbrica**: Criterios adaptados a trabajo colaborativo
**Feedback**: Evaluación del producto del equipo

---

# 8. BUENAS PRÁCTICAS

## Para asistentes de aprendizaje

### Sobre los materiales
- **Calidad de entrada = calidad de salida**: Documentos bien estructurados dan mejores respuestas
- **Formato limpio**: PDFs con texto seleccionable funcionan mejor que escaneos
- **Organización**: Bases de conocimiento temáticas, no una única base enorme

### Sobre las instrucciones
- **Sé específico**: Define claramente qué debe y qué no debe hacer
- **Establece límites**: Que se ciña a los materiales proporcionados
- **Anticipa mal uso**: Instrucciones para mantener el foco

## Para actividades evaluables (LAMBA)

### Sobre las rúbricas
- **Criterios claros**: Dimensiones bien definidas y diferenciadas
- **Niveles específicos**: Descripciones concretas de cada nivel de logro
- **Coherencia**: La rúbrica debe reflejar los objetivos de aprendizaje

### Sobre el feedback
- **Formativo**: Que ayude al estudiante a mejorar
- **Específico**: Referencias concretas al trabajo del estudiante
- **Constructivo**: Identificar fortalezas además de áreas de mejora

## Para ambos tipos de herramientas

### Integración pedagógica
- **Presenta la herramienta**: Explica qué es, qué puede hacer y sus limitaciones
- **Define expectativas**: Cuándo es apropiado usarla y cuándo no
- **Promueve pensamiento crítico**: Los estudiantes deben verificar y reflexionar
- **Es un complemento**: No sustituye la interacción humana ni el aprendizaje activo

### Privacidad
- **Informa a los estudiantes**: Deben saber que las interacciones se registran
- **No pidas datos sensibles**: La herramienta no debe solicitar información personal
- **Revisa periódicamente**: Detecta usos problemáticos en los registros

---

# 9. PRINCIPIOS DE IA SEGURA EN EDUCACIÓN

LAMB se adhiere al **Manifiesto para una IA Segura en Educación** (manifesto.safeaieducation.org).

## Los 7 principios

### 1. Supervisión Humana y Responsabilidad
La IA complementa, no reemplaza, al docente. Las decisiones importantes requieren supervisión humana. Los estudiantes pueden apelar decisiones de la IA.

**En LAMB**: Tú defines todo. Puedes revisar y ajustar calificaciones. El feedback de IA es una ayuda, no la última palabra.

### 2. Garantía de Confidencialidad
Protección de datos de estudiantes. La institución controla la tecnología y los datos.

**En LAMB**: Datos en infraestructura propia. Sin registro en servicios externos. Control total sobre qué se envía a los LLM.

### 3. Alineación con Estrategias Educativas
Compatible con políticas institucionales. No facilita prácticas no éticas.

**En LAMB**: Integración nativa con LMS institucional. Configuración de límites y comportamientos.

### 4. Alineación con Prácticas Didácticas
Basado en diseño instruccional. Apoya las metodologías, no las interrumpe.

**En LAMB**: Tú diseñas cómo se integra en tu secuencia didáctica. Es herramienta, no protagonista.

### 5. Precisión y Explicabilidad
Información precisa y verificable. Mitigación de alucinaciones.

**En LAMB**: RAG para fundamentar respuestas. Citas de fuentes. Feedback basado en rúbricas explícitas.

### 6. Interfaz y Comportamiento Transparente
Claro qué es IA y cuáles son sus limitaciones.

**En LAMB**: Configurable para reconocer limitaciones. Transparencia sobre el proceso.

### 7. Formación Ética y Transparencia
Modelos entrenados éticamente. Transparencia sobre sesgos.

**En LAMB**: Elección de modelos según criterios éticos. Posibilidad de usar modelos locales/open-source.

---

# 10. PREGUNTAS FRECUENTES

## Generales

**¿LAMB es gratuito?**
Sí, es open-source (GPL v3). Necesitas infraestructura donde ejecutarlo y posiblemente pagar APIs de modelos de IA.

**¿Necesito saber programar?**
No. Todo se configura visualmente.

**¿Qué LMS son compatibles?**
Cualquiera con LTI 1.1: Moodle, Canvas, Blackboard, Sakai, etc.

## Sobre asistentes

**¿El asistente puede inventar información?**
El RAG reduce drásticamente las alucinaciones al basar las respuestas en tus documentos. Además, cita las fuentes para verificación.

**¿Puedo tener varios asistentes?**
Sí, ilimitados. Cada uno con su propia base de conocimiento e instrucciones.

## Sobre LAMBA y evaluación

**¿La evaluación automática sustituye al profesor?**
No. Es una herramienta de apoyo. Puedes revisar, ajustar y tomar la decisión final.

**¿Qué formatos de documento acepta LAMBA?**
PDF, DOCX y TXT.

**¿Las notas se sincronizan automáticamente con Moodle?**
Sí, mediante el protocolo LTI.

**¿Puedo modificar una calificación después de generada?**
Sí, puedes ajustar manualmente y reenviar a Moodle.

## Sobre privacidad

**¿Las entregas de los estudiantes se envían a OpenAI/Google?**
Solo el texto extraído se envía al modelo configurado. Puedes usar modelos locales para evitar cualquier envío externo.

**¿Quién puede ver las entregas y calificaciones?**
Depende de la configuración de tu institución. LAMBA tiene roles diferenciados (admin, profesor, estudiante).

---

# 11. RECURSOS Y SOPORTE

## Documentación
- **Web del proyecto**: www.lamb-project.org
- **Tutorial rápido**: lamb-project.org/tutorial
- **GitHub**: github.com/Lamb-Project/lamb

## Manifiesto y checklist
- **Manifiesto**: manifesto.safeaieducation.org
- **Checklist de evaluación**: manifesto.safeaieducation.org/checklist

## Comunidad
- **GitHub Issues**: Reportar problemas
- **GitHub Discussions**: Preguntas y discusión

## Referencia académica

> Alier, M., Pereira, J., García-Peñalvo, F.J., Casañ, M.J., & Cabré, J. (2025). LAMB: An open-source software framework to create artificial intelligence assistants deployed and integrated into learning management systems. *Computer Standards & Interfaces*, 92. DOI: 10.1016/j.csi.2024.103940

---

# 12. RESUMEN

## LAMB es una plataforma para crear herramientas educativas con IA sin programar

**Actualmente ofrece:**

| Herramienta | Para qué sirve |
|-------------|---------------|
| **Asistentes de aprendizaje** | Chatbots que conocen tus materiales y responden citando fuentes |
| **LAMBA (evaluación)** | Tareas con feedback y calificación automática basada en rúbricas |

**Ventajas clave:**

✅ Control total sobre instrucciones, conocimiento y rúbricas
✅ Datos de estudiantes en tu infraestructura
✅ Integración nativa con Moodle y otros LMS
✅ Sincronización automática de calificaciones
✅ Elección de modelo de IA (incluso locales)
✅ Sin necesidad de programar

**En menos de una hora** puedes tener tu primer asistente o actividad evaluable funcionando.

---

*LAMB es un proyecto open-source desarrollado por investigadores de la UPC y UPV/EHU, comprometido con una IA segura y ética en educación.*