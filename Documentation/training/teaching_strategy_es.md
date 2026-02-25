# Curso de Formación LAMB -- Estrategia Didáctica

**Versión:** 1.0
**Fecha:** 15 de febrero de 2026
**Estado:** Borrador
**Destinatarios:** Diseñadores del curso, formadores

---

## 1. Identidad del Curso

**Título:** *Creación de Asistentes de Aprendizaje con IA mediante LAMB -- Un Curso Práctico para Educadores*

**Formato:** Híbrido (curso asíncrono en Moodle + sesiones síncronas AMA)

**Duración:** 3-4 semanas (flexible, contenido dosificado)

**Plataforma:** Moodle con LAMB integrado vía LTI

**Público objetivo:** Profesorado universitario que desea crear asistentes de aprendizaje basados en IA para sus asignaturas. No se requieren conocimientos de programación.

---

## 2. Filosofía Pedagógica

### 2.1 Aprender Haciendo, No Mirando

Cada contenido tiene una **llamada a la acción** clara y alcanzable. Los participantes nunca se limitan a mirar: siempre hacen algo concreto con LAMB inmediatamente después. El objetivo es que, al finalizar el curso, cada participante tenga al menos un asistente funcional y publicado, basado en los materiales de su propia asignatura.

### 2.2 Usar Nuestro Propio Producto

El curso en sí está construido sobre LAMB. Los participantes experimentan LAMB desde el lado del estudiante (interactuando con un asistente del curso, siendo evaluados por LAMBA) mientras aprenden simultáneamente a ser creadores. Esta doble perspectiva es intencional: sienten lo que sentirán sus estudiantes.

### 2.3 Contenido Impulsado por la Comunidad

El foro no es un canal de soporte: es un **motor de contenido**. Las preguntas, frustraciones e ideas de los participantes se convierten en screencasts, entradas de FAQ y debates sobre funcionalidades. El curso se enriquece con cada cohorte. Se dice explícitamente a los participantes: vuestras preguntas mejoran este curso para todos.

### 2.4 Dosificación, No Avalancha

El contenido se publica cada 1-2 días en vídeos cortos y enfocados (5-10 minutos como máximo). Esto crea un ritmo: ver, hacer, compartir, debatir. Evita la sobrecarga y da tiempo al profesorado para responder en el foro antes de la siguiente publicación.

### 2.5 Alineación con el Manifiesto

El curso encarna los principios del Manifiesto de IA Segura en Educación en su propio diseño:
- **Supervisión Humana** -- El formador está presente, es receptivo y dirige la conversación
- **Privacidad** -- Los participantes utilizan una instancia de LAMB alojada institucionalmente
- **Integración Didáctica** -- El curso se desarrolla dentro de Moodle, el mismo entorno que los participantes ya utilizan
- **Transparencia** -- Los participantes ven cómo funciona el asistente de IA desde dentro (modo depuración, inspección de prompts)

---

## 3. Objetivos de Aprendizaje

Al finalizar el curso, los participantes serán capaces de:

### Semana 1: Experiencia y Primer "¡Wow!" (Nivel Básico)
1. Experimentar los asistentes de LAMB como usuario final: sentir lo que sentirán los estudiantes
2. Explicar qué es LAMB y por qué existe (privacidad, control, principios del manifiesto)
3. Acceder a LAMB desde Moodle vía LTI Creator y navegar por la Interfaz de Creación
4. Crear un primer asistente con un prompt de sistema y un único archivo adjunto (RAG de archivo único): contexto instantáneo sin complejidad de configuración
5. Probar el asistente y ver cómo responde preguntas a partir del material de tu propia asignatura

### Semana 2: Conocimiento Profundo y Refinamiento (Nivel Intermedio)
6. Construir una base de conocimiento completa a partir de múltiples fuentes (archivos, URLs, YouTube)
7. Conectar una base de conocimiento a un asistente (configuración RAG, Top K)
8. Comprender la diferencia entre RAG de archivo único y bases de conocimiento completas
9. Probar y depurar un asistente usando el modo depuración
10. Iterar sobre los prompts de sistema para mejorar el comportamiento del asistente

### Semana 3: Publicación, Evaluación y Más Allá (Nivel Avanzado)
11. Publicar un asistente como actividad LTI en un curso de Moodle
12. Crear una rúbrica de evaluación usando Evaluaitor (manual o generada por IA)
13. Adjuntar una rúbrica a un asistente para la evaluación asistida por IA
14. Comprender el flujo de evaluación de LAMBA (la IA propone, el docente decide)

### Meta-Aprendizaje (A lo largo del curso)
13. Experimentar LAMB desde la perspectiva del estudiante (interactuando con el asistente del curso)
14. Experimentar la evaluación asistida por IA desde la perspectiva del estudiante (LAMBA)
15. Evaluar críticamente el papel de la IA en su propio contexto docente

---

## 4. Infraestructura del Curso

### 4.1 Estructura del Curso en Moodle

```
Curso de Formación LAMB (Moodle)
|
+-- Anuncios (canal de mensajes del profesorado)
|     Canal unidireccional para actualizaciones del formador,
|     publicación de nuevos vídeos y respuestas a preguntas frecuentes.
|
+-- Foro de Debate (abierto a todos)
|     El corazón del curso. Los participantes publican preguntas,
|     solicitudes de funcionalidades, frustraciones, ideas y logros.
|     El formador responde con texto o screencasts breves.
|
+-- Asistentes de Demostración (Herramienta Externa LTI -- Unified LTI)
|     Asistentes preconstruidos para la experiencia de usuario
|     final de la Semana 1. Los participantes interactúan como
|     estudiantes antes de convertirse en creadores.
|     Ejemplos: un tutor de historia, un ayudante de matemáticas,
|     un coach de idiomas.
|
+-- Acceso a LAMB Creator (Herramienta Externa LTI -- LTI Creator)
|     Enlace LTI Creator -- un clic lleva a los participantes
|     directamente a la Interfaz de Creación de LAMB.
|     No se necesitan credenciales adicionales.
|
+-- Asistente IA del Curso (Herramienta Externa LTI -- Unified LTI)
|     Un asistente LAMB cargado con todas las transcripciones
|     de vídeos y la documentación del curso. Los participantes
|     pueden hacerle preguntas y este les redirige al vídeo
|     y momento exacto correspondiente.
|
+-- Módulos de Contenido (uno por vídeo/tema)
|     +-- Vídeo (incrustado o enlazado)
|     +-- Resumen escrito / transcripción
|     +-- Llamada a la acción (tarea concreta)
|     +-- Opcional: enlace a documentación relevante
|
+-- Entregable Final
|     Enviar un enlace/descripción de su asistente publicado.
|     Evaluado mediante LAMBA con una rúbrica.
|
+-- Sesiones AMA (2-3 videoconferencias programadas)
      Eventos de calendario con enlaces de videoconferencia.
```

### 4.2 Configuración de LAMB

**LTI Creator:** Los participantes se aprovisionan como usuarios `lti_creator` en una organización de formación dedicada. Acceden a LAMB directamente desde Moodle sin necesidad de un inicio de sesión separado.

**Asistentes de Demostración (Semana 1):** 2-3 asistentes preconstruidos publicados vía Unified LTI para la experiencia de usuario final en los primeros días. Deben estar pulidos, ser diversos (diferentes materias, diferentes tonos) y demostrar cómo se ve y se siente un asistente bien diseñado. Los participantes chatean con estos antes de construir los suyos propios, estableciendo el nivel de referencia hacia el que trabajan.

**Asistente del Curso:** Un asistente LAMB publicado cuya base de conocimiento contiene:
- Todas las transcripciones de vídeos (con marcas de tiempo e identificadores de vídeo)
- El documento resumen para partes interesadas
- Entradas de FAQ generadas a partir de preguntas del foro

El prompt de sistema del asistente le indica que debe:
- Responder preguntas sobre LAMB
- Hacer referencia a vídeos y marcas de tiempo específicas cuando sea relevante (p. ej., "Esto se trata en el Vídeo 5 en el minuto 3:20")
- Redirigir al foro para preguntas que no pueda responder
- Ser transparente sobre el hecho de que es un asistente de IA construido con el propio LAMB

**Evaluación con LAMBA:** El entregable final (un asistente publicado) se evalúa mediante una rúbrica a través de LAMBA. La IA propone una evaluación; el formador revisa y confirma la calificación. Los participantes experimentan LAMBA desde el lado del estudiante.

### 4.3 El Bucle de Autoconsumo

```
Los participantes hacen preguntas en el foro
        |
        v
Las mejores preguntas se convierten en screencasts de respuesta
        |
        v
Las transcripciones de los screencasts se ingestan en la KB del curso
        |
        v
El asistente IA del curso ahora puede responder esas preguntas
        |
        v
Los participantes experimentan un asistente mejorado
        |
        v
Comprenden por qué las bases de conocimiento importan para SUS asistentes
```

Este bucle se hace explícito a los participantes. Ven cómo el asistente del curso mejora en tiempo real a medida que se añade nuevo contenido, demostrando el valor de mantener y hacer crecer una base de conocimiento.

---

## 5. Plan de Contenidos: La Serie de Vídeos

Cada vídeo dura **5-10 minutos**, es enfocado y termina con una llamada a la acción concreta.

### Semana 1: Primero Experimentar, Después Crear

La primera semana está diseñada para ser **agradable e inmediatamente gratificante**. Los participantes comienzan como usuarios finales -- experimentando los asistentes de LAMB tal como lo harán sus estudiantes -- antes de pasar al lado creador. Cuando crean, utilizan **RAG de archivo único**, que les permite adjuntar un documento a un asistente sin complejidad de configuración. Sin crear bases de conocimiento, sin configurar fragmentación, sin esperas. Sube un archivo, selecciónalo, y el asistente conoce instantáneamente el contenido de tu asignatura.

| # | Título del Vídeo | Contenido Clave | Llamada a la Acción |
|---|------------------|-----------------|---------------------|
| 1 | **Conoce a tu Tutor IA** | Comienza como estudiante: interactúa con 2-3 asistentes de demostración preconstruidos (un tutor de historia, un ayudante de matemáticas, un coach de idiomas). Siente la experiencia. Observa cómo cada uno tiene diferente personalidad, alcance y conocimiento. | Chatea con cada asistente de demostración. Publica en el foro: ¿cuál te impresionó más y por qué? ¿Qué querrías para TU asignatura? |
| 2 | **¿Por qué LAMB? Control, Privacidad y el Manifiesto** | Ahora que lo has sentido -- ¿por qué existe esto? Preocupaciones de privacidad con ChatGPT, principios del manifiesto, control institucional, la justificación de una IA educativa diseñada específicamente frente a herramientas de propósito general. | Lee el manifiesto (o revísalo por encima). Publica en el foro: ¿qué preocupaciones tienes sobre la IA en tus asignaturas? |
| 3 | **Tu Primer Acceso y tu Primer Asistente** | Haz clic en el enlace LTI Creator en Moodle. Accede a la Interfaz de Creación. Crea un asistente: nombre, descripción, elige un modelo, escribe un prompt de sistema básico. Mantenlo sencillo. | Accede a LAMB desde Moodle. Crea un asistente para tu asignatura con un prompt de sistema sencillo (p. ej., "Eres un tutor de [tu materia]. Sé amable y motivador."). |
| 4 | **El Truco de Magia: Adjunta un Archivo y Observa** | Introduce el RAG de archivo único: selecciona "single_file_rag" como procesador RAG, sube un archivo (tu programa, un resumen de capítulo, un conjunto de conceptos clave -- simplemente un archivo .txt o .md), selecciónalo, guarda. Ahora prueba: pregunta al asistente sobre el contenido de tu asignatura. Lo sabe. | Sube un documento de tu asignatura y adjúntalo a tu asistente. Hazle 5 preguntas que requieran conocimiento de ese archivo. Publica en el foro: ¿cuál fue el momento "wow"? |
| 5 | **El Asistente del Curso y el Autoconsumo del Producto** | Demuestra el propio asistente LAMB del curso. Muestra cómo hace referencia a vídeos específicos y marcas de tiempo. Explica el concepto de autoconsumo: este curso funciona con LAMB. Todo lo que estás aprendiendo a construir, también lo estás experimentando como estudiante. | Prueba el asistente del curso. Pregúntale algo sobre lo que has aprendido esta semana. Compara sus respuestas con las de los asistentes de demostración del Vídeo 1 -- ¿qué tiene de diferente un asistente con contenido real detrás? |

### Semana 2: Conocimiento Profundo y Refinamiento

Ahora que los participantes tienen un asistente funcional con un solo archivo, la Semana 2 introduce el sistema completo de bases de conocimiento -- explicando por qué podrían necesitar más de un archivo, cómo funciona la búsqueda semántica y cómo ajustar el comportamiento de su asistente.

| # | Título del Vídeo | Contenido Clave | Llamada a la Acción |
|---|------------------|-----------------|---------------------|
| 6 | **De un Archivo a una Base de Conocimiento Completa** | La limitación del RAG de archivo único (el archivo completo en contexto, un solo archivo). Introducción a las Bases de Conocimiento: crear una colección, subir múltiples documentos. Explicar la fragmentación y la búsqueda vectorial -- la IA encuentra las partes relevantes en lugar de leerlo todo. | Crea una base de conocimiento. Sube al menos 2-3 documentos de tu asignatura. |
| 7 | **Más Allá de los Archivos: URLs, Rastreadores y YouTube** | Ingestar una página web, rastrear un sitio web de curso, importar la transcripción de una clase de YouTube. Mostrar cómo diversas fuentes se convierten en conocimiento consultable. | Añade una URL o un vídeo de YouTube a tu KB. |
| 8 | **Conectando tu Base de Conocimiento (RAG)** | Cambia tu asistente de RAG de archivo único a una KB completa. Configura Top K. Prueba la diferencia -- ahora busca fragmentos relevantes en lugar de volcar el archivo completo. Compara los resultados. | Conecta tu KB a tu asistente. Haz las mismas preguntas de la Semana 1. ¿Es mejor? Publica tu comparación en el foro. |
| 9 | **Modo Depuración: Ver lo que Ve la IA** | Activa el modo depuración. Lee el prompt completo: prompt de sistema + contexto recuperado + pregunta del usuario. Comprende lo que la IA realmente recibe. Inspecciona las citas. | Activa el modo depuración. Haz una captura de pantalla del prompt completo. Publícala en el foro con tus observaciones. |
| 10 | **Ingeniería de Prompts para Educadores** | Refinamiento de prompts de sistema: establecer límites, tono, estrategias pedagógicas (método socrático, andamiaje, "no des la respuesta -- guía al estudiante"). Comparación antes/después. | Reescribe tu prompt de sistema. Compara el comportamiento del asistente antes y después. Comparte tu mejor prompt en el foro. |

### Semana 3: Publicación, Evaluación y Más Allá

| # | Título del Vídeo | Contenido Clave | Llamada a la Acción |
|---|------------------|-----------------|---------------------|
| 11 | **Publicar en Moodle** | El flujo de publicación, credenciales LTI, añadir como Herramienta Externa en Moodle, vista del estudiante | Publica tu asistente. Añádelo a un curso de prueba en Moodle (o a tu curso real). |
| 12 | **Creación de Rúbricas de Evaluación con Evaluaitor** | Creación manual de rúbricas, rúbricas generadas por IA, criterios/niveles/pesos, compartir plantillas | Crea una rúbrica para evaluar tu asistente (o un trabajo de estudiante). Prueba la generación por IA. |
| 13 | **Evaluación Asistida por IA con LAMBA** | El flujo de evaluación, cómo la IA propone (no decide), revisión docente, modelo de doble calificación | Experimenta LAMBA como estudiante enviando tu entregable final. Después debate en el foro: ¿cómo lo usarías? |
| 14 | **Compartir, Analíticas y Próximos Pasos** | Compartir asistentes con colegas, analíticas de chat, el ecosistema LAMB, lo que viene a continuación | Comparte tu asistente con un colega. Revisa tus analíticas. Publica tus reflexiones finales en el foro. |

### Contenido Extra / Responsivo

| # | Título del Vídeo | Cuándo |
|---|------------------|--------|
| B1-Bn | **Screencasts de respuesta a preguntas del foro** | Según necesidad, a lo largo del curso |
| B? | **Avanzado: Plantillas de Prompts** | Si los participantes preguntan sobre prompts reutilizables |
| B? | **Avanzado: Administración de Organización** | Si hay administradores institucionales en la cohorte |
| B? | **Avanzado: Comparación de Múltiples Modelos** | Si los participantes quieren comparar GPT-4o vs. Mistral vs. local |

---

## 6. El Foro como Motor de Contenido

### 6.1 Cultura del Foro

El foro se posiciona no como "soporte" sino como una **comunidad profesional de aprendizaje**. El formador establece el tono en el Vídeo 1 y en el anuncio de bienvenida:

> *Este foro es donde el curso realmente sucede. Publica lo que sea: preguntas que no logras resolver, funcionalidades que desearías que existieran, cosas que te frustraron, cosas que te encantaron, ideas sobre cómo usarías LAMB en tu docencia. No hay preguntas tontas, y tus preguntas literalmente mejorarán este curso, porque convertiremos las mejores en nuevo contenido.*

### 6.2 Tipos de Publicaciones Animados

| Tipo | Descripción | Respuesta del Formador |
|------|-------------|------------------------|
| **Preguntas** | "¿Cómo hago...?", "¿Por qué...?" | Respuesta escrita o screencast si es visual |
| **Solicitudes de funcionalidades** | "Estaría genial que LAMB pudiera..." | Reconocer, discutir viabilidad, posiblemente derivar a GitHub |
| **Aclaraciones** | "No entendí la parte sobre..." | Screencast breve abordando la confusión |
| **Logros** | "Conseguí que mi asistente funcionara y..." | Celebrar, preguntar más, compartir con el grupo |
| **Frustraciones** | "Intenté X y no funcionó porque..." | Resolver el problema, posiblemente crear un screencast, mejorar documentación |
| **Ideas** | "¿Y si usáramos LAMB para...?" | Debatir, conectar con ideas de otros participantes |

### 6.3 Pipeline de Screencast a KB

Cuando el formador crea un screencast de respuesta:

1. Grabar un screencast breve (2-5 min) abordando la pregunta del foro
2. Subir al alojamiento de vídeo (YouTube no listado o plataforma institucional)
3. Generar/escribir una transcripción
4. Publicar el enlace del screencast como respuesta en el hilo del foro
5. **Ingestar la transcripción en la base de conocimiento del asistente del curso**
6. El asistente del curso ahora puede responder esa pregunta y apuntar al screencast

Este pipeline se documenta y es visible para los participantes -- demuestra el mantenimiento de la KB en tiempo real.

---

## 7. Sesiones AMA (Síncronas)

### 7.1 Formato

2-3 sesiones de videoconferencia en directo (60-90 minutos cada una), programadas en momentos clave:

| Sesión | Momento | Enfoque |
|--------|---------|---------|
| **AMA 1** | Final de la Semana 1 | Primeras impresiones, aclaración de conceptos, resolución de problemas con los primeros asistentes |
| **AMA 2** | Final de la Semana 2 | Bases de conocimiento, RAG, debate sobre ingeniería de prompts |
| **AMA 3** | Final de la Semana 3 | Publicación, evaluación, planes futuros, cierre del curso |

### 7.2 Estructura

Cada sesión AMA sigue una estructura flexible:

1. **Calentamiento (10 min)** -- El formador aborda 2-3 preguntas seleccionadas del foro (preparadas por si los participantes son tímidos al principio)
2. **Preguntas abiertas (40-60 min)** -- Los participantes preguntan lo que quieran. Se anima a compartir pantalla para resolución de problemas en directo.
3. **Muestra y Cuenta (10-20 min)** -- Voluntarios muestran sus asistentes. Retroalimentación grupal.

### 7.3 Preguntas Preparadas

El formador selecciona 2-3 hilos interesantes del foro antes de cada sesión como iniciadores de conversación. Esto garantiza que la sesión tenga impulso incluso si los participantes están inicialmente callados. A medida que avanza el curso y se genera confianza, esta preparación se vuelve menos necesaria.

### 7.4 Grabación

Las sesiones AMA se graban y se publican en el curso. Las transcripciones se ingestan en la KB del asistente del curso.

---

## 8. Estrategia de Evaluación

### 8.1 Filosofía

La evaluación en este curso tiene un doble propósito:
1. Asegurar que los participantes han alcanzado los objetivos de aprendizaje fundamentales
2. **Demostrar LAMBA en acción** -- los participantes experimentan la evaluación asistida por IA desde la perspectiva del estudiante

### 8.2 Entregable Final

Cada participante entrega un **asistente LAMB publicado** para su propio contexto docente. La entrega incluye:

- El nombre del asistente y una breve descripción de su propósito
- El prompt de sistema utilizado
- Una descripción del contenido de la base de conocimiento (qué se ingesto y por qué)
- El curso de Moodle donde está publicado (o un plan de publicación)
- Una breve reflexión (300-500 palabras): ¿Qué funcionó? ¿Qué cambiarías? ¿Cómo podrían beneficiarse tus estudiantes?

### 8.3 Rúbrica de Evaluación

El entregable se evalúa mediante una rúbrica creada en Evaluaitor y procesada a través de LAMBA:

| Criterio | Peso | Qué Buscamos |
|----------|------|---------------|
| **Diseño del Asistente** | 25% | Propósito claro, prompt de sistema bien redactado, elección de modelo apropiada |
| **Calidad de la Base de Conocimiento** | 25% | Contenido relevante ingestado, fuentes apropiadas, alcance razonable |
| **Pruebas e Iteración** | 20% | Evidencia de pruebas, refinamiento de prompts, uso del modo depuración |
| **Publicación e Integración** | 15% | Asistente publicado y accesible vía LTI en un curso de Moodle |
| **Reflexión** | 15% | Análisis reflexivo de la experiencia, planes realistas de uso |

### 8.4 La Experiencia LAMBA

El flujo de evaluación:

1. El participante entrega su trabajo a través de Moodle (actividad LTI de LAMBA)
2. La IA evalúa la entrega según la rúbrica y propone una calificación con retroalimentación escrita
3. **El formador revisa cada propuesta de la IA**, edita la retroalimentación cuando es necesario, ajusta las puntuaciones si la IA evaluó incorrectamente y confirma la calificación final
4. El participante recibe la calificación y la retroalimentación confirmadas por el formador en Moodle

Esto se hace transparente para los participantes. Se les dice:

> *La IA leyó tu entrega y propuso una evaluación. Tu formador revisó después esa propuesta, la editó cuando fue necesario y confirmó la calificación final. Así es exactamente como funciona LAMBA: la IA asiste, el docente decide. Acabas de experimentarlo desde el lado del estudiante.*

### 8.5 Participación en el Foro (No Calificada pero Valorada)

La participación en el foro se anima pero no se califica formalmente. El formador destaca contribuciones valiosas en los anuncios y las sesiones AMA. Los participantes que comparten prompts, ayudan a compañeros o publican preguntas reflexivas reciben reconocimiento público.

---

## 9. Directrices de Producción de Contenido

### 9.1 Producción de Vídeo

| Aspecto | Directriz |
|---------|-----------|
| **Duración** | 5-10 minutos como máximo. Si es más largo, dividir en dos. |
| **Formato** | Screencast con voz en off. Cámara facial opcional pero recomendada para intro/cierre. |
| **Estructura** | Gancho (qué aprenderás) > Demostración (mostrar, no contar) > Llamada a la acción (qué hacer ahora) |
| **Tono** | Conversacional, motivador, entre iguales. No una clase magistral, sino mostrar a un colega cómo hacer algo. |
| **Subtítulos** | Siempre. Los autogenerados son aceptables, corregidos si es posible. |
| **Transcripción** | Siempre producida. Doble propósito: accesibilidad + KB del asistente del curso. |

### 9.2 Screencasts de Respuesta

| Aspecto | Directriz |
|---------|-----------|
| **Duración** | 2-5 minutos. Abordar una pregunta por screencast. |
| **Contexto** | Empezar leyendo la pregunta del foro en voz alta. |
| **Formato** | Grabación de pantalla mostrando la solución. No requiere edición. |
| **Publicación** | Responder en el hilo del foro con el enlace al vídeo. |
| **Ingesta en KB** | Transcripción añadida a la KB del asistente del curso en un plazo de 24 horas. |

### 9.3 Contenido Escrito

- El documento resumen para partes interesadas sirve como referencia principal
- Cada módulo de vídeo incluye un breve resumen escrito (no una transcripción completa, sino un resumen de 2-3 párrafos)
- Las entradas de FAQ se compilan a partir de las interacciones del foro

---

## 10. Cronograma y Ritmo

### Ritmo Semanal

```
Lunes:       Nuevo vídeo publicado + anuncio
Martes:      Actividad en el foro, el formador responde a las publicaciones
Miércoles:   Segundo vídeo publicado (si la cadencia es de 2 días)
Jueves:      Actividad en el foro, screencasts de respuesta si es necesario
Viernes:     Tercer vídeo o día de descanso + anuncio de resumen semanal
Fin de semana: Los participantes se ponen al día, el foro sigue activo
```

### Calendario del Curso (Modelo de 3 Semanas)

| Día | Contenido | Actividad |
|-----|-----------|-----------|
| **D1** | Vídeo 1: Conoce a tu Tutor IA | Chatear con asistentes de demostración, presentación en el foro |
| **D2** | Vídeo 2: ¿Por qué LAMB? | Leer el manifiesto, debatir sobre preocupaciones con la IA |
| **D3** | Vídeo 3: Primer Acceso y Primer Asistente | Acceder vía LTI, crear asistente |
| **D4** | Vídeo 4: El Truco de Magia (RAG de archivo único) | Subir un archivo, "wow" instantáneo |
| **D5** | Vídeo 5: Asistente del Curso y Autoconsumo | Probar el asistente del curso |
| **D5-6** | **Sesión AMA 1** | Primeras impresiones, momentos wow, preguntas |
| **D7** | Descanso / ponerse al día | |
| **D8** | Vídeo 6: De un Archivo a una KB Completa | Crear KB, subir múltiples documentos |
| **D9** | Vídeo 7: URLs, Rastreadores y YouTube | Ingestar contenido web/vídeo |
| **D10** | Vídeo 8: Conectando tu KB (RAG) | Cambiar de archivo único a KB completa |
| **D11** | Vídeo 9: Modo Depuración | Inspeccionar prompts y contexto |
| **D12** | Vídeo 10: Ingeniería de Prompts | Refinar prompts de sistema |
| **D12-13** | **Sesión AMA 2** | Comparación de RAG, compartir prompts |
| **D14** | Descanso / ponerse al día | |
| **D15** | Vídeo 11: Publicación | Publicar en Moodle |
| **D16** | Vídeo 12: Rúbricas con Evaluaitor | Crear rúbricas |
| **D17** | Vídeo 13: LAMBA | Experimentar la evaluación asistida por IA |
| **D18** | Vídeo 14: Compartir y Analíticas | Funcionalidades de cierre |
| **D19** | Fecha límite del entregable final | Entregar vía LAMBA |
| **D20-21** | **Sesión AMA 3** | Muestra y cuenta, reflexiones, cierre |

---

## 11. Métricas de Éxito

### Para los Participantes

| Métrica | Objetivo |
|---------|----------|
| Completó al menos un asistente | 90%+ de los participantes |
| Publicó el asistente en Moodle | 70%+ de los participantes |
| Creó una base de conocimiento con contenido real de su asignatura | 80%+ de los participantes |
| Publicó al menos una vez en el foro | 95%+ de los participantes |
| Entregó el entregable final | 80%+ de los participantes |

### Para el Curso

| Métrica | Objetivo |
|---------|----------|
| Satisfacción de los participantes (encuesta post-curso) | 4.0+ / 5.0 |
| Publicaciones en el foro por participante (media) | 3+ |
| Screencasts de respuesta producidos | 5-10 por cohorte |
| Crecimiento de la KB del asistente del curso | Incremento medible de D1 a D21 |
| Participantes que continúan usando LAMB después del curso | Seguimiento a los 3 meses |

### Para LAMB (Retroalimentación de Producto)

| Métrica | Resultado |
|---------|-----------|
| Solicitudes de funcionalidades recopiladas | Triaje y derivación a issues de GitHub |
| Errores reportados | Registrados y priorizados |
| Puntos de fricción UX identificados | Documentados para mejora del producto |
| Casos de uso descubiertos | Añadidos a documentación / sitio web |

---

## 12. Reutilización y Escalabilidad

### Modelo de Cohortes

Este curso está diseñado para ejecutarse en cohortes. Cada cohorte:
- Recibe una instancia de curso en Moodle nueva (o sección)
- Comparte la misma organización de formación en LAMB
- Hereda el catálogo de contenido creciente de cohortes anteriores
- Se beneficia de una KB del asistente del curso en mejora continua

### Crecimiento del Catálogo de Contenido

```
Cohorte 1:  14 vídeos base + N screencasts de respuesta
Cohorte 2:  14 vídeos base + N + M screencasts de respuesta (algunos de la Cohorte 1 reutilizados)
Cohorte 3:  14 vídeos base (posiblemente refinados) + biblioteca creciente de screencasts de respuesta
   ...
```

El asistente del curso se vuelve más capaz con cada cohorte a medida que crece su KB. Esto es en sí mismo una demostración de la propuesta de valor de LAMB.

### Localización

- Los vídeos base pueden producirse en múltiples idiomas (español, inglés, catalán, euskera -- coincidiendo con los idiomas de la interfaz de LAMB)
- El asistente del curso puede configurarse por idioma
- Los materiales escritos ya existen en múltiples idiomas en el sitio web del proyecto

---

## 13. Riesgos y Mitigaciones

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Baja participación en el foro | El curso se siente vacío, menos screencasts | Sembrar el foro con preguntas del formador. Invitar directamente a los participantes a responder a indicaciones específicas en las llamadas a la acción. |
| Los participantes se retrasan con los vídeos | Acumulación de contenido sin ver, desvinculación | Mantener los vídeos cortos. Anuncios de resumen semanal. Sesiones AMA como puntos de recuperación. |
| Problemas con la instancia de LAMB (caídas, errores) | Frustración, participantes bloqueados | Tener una instancia de respaldo fiable. Comunicación transparente sobre los problemas. Convertir los errores en momentos de aprendizaje ("esto es código abierto -- vamos a reportarlo"). |
| Los participantes carecen de acceso de administrador a Moodle para publicar | No pueden completar el paso de publicación | Proporcionar un curso de prueba compartido en Moodle. Colaborar con los administradores institucionales de Moodle. Ofrecer el paso de publicación como opcional si no es posible el acceso. |
| La evaluación asistida por IA (LAMBA) se siente impersonal | Reacción negativa ante la IA proponiendo calificaciones | Ser extremadamente transparente sobre el proceso. Mostrar la propuesta bruta de la IA vs. la retroalimentación final del formador. Enfatizar el modelo de que el docente decide. |
| Las sesiones AMA tienen poca asistencia | Oportunidad perdida para la construcción de comunidad | Grabar y compartir. Ofrecer dos franjas horarias si es posible. Mantenerlas opcionales pero valiosas (Q&A exclusivo, muestra y cuenta). |

---

## 14. Resumen: El Curso en Una Página

**Qué:** Un curso híbrido de 3 semanas que enseña a educadores universitarios a crear asistentes de aprendizaje con IA mediante LAMB.

**Cómo:** Vídeos diarios cortos con tareas prácticas, un foro de debate activo y sesiones AMA en directo. El propio curso funciona con LAMB (autoconsumo).

**El Bucle:**
1. Ver un vídeo corto (5-10 min)
2. Hacer algo concreto con LAMB (llamada a la acción)
3. Compartir tu experiencia en el foro
4. Recibir respuestas (texto o screencast) del formador
5. Esas respuestas alimentan la base de conocimiento del asistente del curso
6. El asistente del curso se vuelve más inteligente -- demostrando el valor de lo que estás construyendo

**Evaluación:** Entregar un asistente publicado. La IA propone una evaluación vía LAMBA. El formador revisa y confirma. Los participantes experimentan el ciclo completo desde ambos lados.

**Filosofía:** La IA asiste; el docente decide. Siempre.

---

*Este documento define la estrategia didáctica del curso de formación LAMB. El siguiente paso es desarrollar guiones detallados de los vídeos y la estructura del curso en Moodle.*
