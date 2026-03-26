# MarkItDown Plus - Guía de Usuario

## ¿Qué es este complemento?

**MarkItDown Plus** es una herramienta que convierte tus documentos (PDFs, archivos de Word, PowerPoints, etc.) en un formato que puede ser buscado y consultado por asistentes de IA. Divide tus documentos en piezas más pequeñas llamadas "fragmentos" y los almacena en una base de conocimientos.

Piensa en ello como crear un índice para un libro: en lugar de leer el libro entero para encontrar información, la IA puede buscar rápidamente las secciones relevantes.

---

## Privacidad y Seguridad

### 🔒 Tus documentos permanecen privados por defecto

**Importante:** Esta herramienta procesa tus documentos **en nuestros servidores** (localmente) por defecto. Tu contenido NO se envía a servicios externos como OpenAI a menos que tú específicamente lo elijas.

| Configuración | Qué pasa con tus datos |
|---------------|------------------------|
| Descripción de imágenes: **Ninguna** (por defecto) | ✅ Todo permanece local. No se usan servicios externos. |
| Descripción de imágenes: **Básica** | ✅ Todo permanece local. Las imágenes se extraen y guardan. |
| Descripción de imágenes: **Con IA** | ⚠️ Las imágenes se envían a OpenAI para descripción. |

**Recomendación:** Para documentos confidenciales, registros de empleados, datos financieros o cualquier información sensible, usa siempre el modo "Ninguna" o "Básica".

---

## Entendiendo las Opciones

### 1. Manejo de Imágenes

Cuando tu documento contiene imágenes (gráficos, diagramas, fotos), puedes elegir cómo manejarlas:

#### Opción: Ninguna (Recomendada para documentos sensibles)
- **Qué hace:** Mantiene las referencias de imágenes existentes pero no extrae ni procesa imágenes
- **Mejor para:** Documentos confidenciales, procesamiento más rápido
- **Privacidad:** ✅ Completamente local

#### Opción: Básica
- **Qué hace:** Extrae imágenes del documento y las guarda con descripciones simples basadas en nombres de archivo
- **Mejor para:** Documentos donde quieres imágenes accesibles pero no necesitas descripciones detalladas
- **Privacidad:** ✅ Completamente local

#### Opción: Con IA (LLM)
- **Qué hace:** Envía las imágenes a la IA de OpenAI para generar descripciones detalladas e inteligentes
- **Mejor para:** Materiales educativos, documentos públicos donde el contexto de las imágenes importa
- **Privacidad:** ⚠️ **Las imágenes se envían a OpenAI** - NO usar para documentos confidenciales

---

### 2. Cómo Dividir tu Documento (Modo de Fragmentación)

Tu documento necesita dividirse en piezas más pequeñas para que la IA pueda buscar eficientemente. Hay tres formas de hacerlo:

#### Opción: Estándar (Por defecto)
- **Qué hace:** Divide tu documento en piezas de tamaño aproximadamente igual (medido en caracteres)
- **Mejor para:** Documentos generales, correos electrónicos, artículos, texto sin estructura
- **Cómo funciona:** Como cortar una cinta larga en piezas iguales

**Configuraciones adicionales para modo Estándar:**
- **Tamaño del fragmento:** Qué tan grande debe ser cada pieza (por defecto: 1000 caracteres, aproximadamente 150-200 palabras)
- **Solapamiento:** Cuánto texto se repite entre piezas para mantener el contexto (por defecto: 200 caracteres)

*Consejo: Fragmentos más pequeños (500-800) funcionan mejor para preguntas y respuestas. Fragmentos más grandes (1500-2500) funcionan mejor para resúmenes.*

#### Opción: Por Página
- **Qué hace:** Mantiene cada página como una pieza separada
- **Mejor para:** PDFs, presentaciones, documentos donde los saltos de página son significativos
- **Funciona con:** PDF, Word (.docx), PowerPoint (.pptx) únicamente

**Configuraciones adicionales para modo Página:**
- **Páginas por fragmento:** Cuántas páginas agrupar juntas (por defecto: 1)

*Ejemplo: Un PDF de 10 páginas con "Páginas por fragmento: 2" crea 5 fragmentos, cada uno con 2 páginas.*

#### Opción: Por Sección
- **Qué hace:** Usa los encabezados de tu documento (títulos, subtítulos) para crear divisiones naturales
- **Mejor para:** Informes, manuales, documentos estructurados con secciones claras
- **Cómo funciona:** Respeta la organización de tu documento

**Configuraciones adicionales para modo Sección:**
- **Dividir en nivel de encabezado:** Qué nivel de encabezado define un fragmento
  - Nivel 1 = Títulos principales (# Encabezado)
  - Nivel 2 = Subtítulos (## Encabezado) - *recomendado*
  - Nivel 3 = Sub-subtítulos (### Encabezado)
- **Secciones por fragmento:** Cuántas secciones agrupar juntas (por defecto: 1)

*Ejemplo: Un informe con capítulos y secciones, usando "Nivel 2" y "1 sección por fragmento" crea un fragmento por sección, con los títulos de capítulo preservados para contexto.*

---

## Ejemplos Prácticos

### Ejemplo 1: Documento de Políticas de Empresa (Confidencial)

**Escenario:** Estás subiendo un manual del empleado con políticas sensibles de RRHH.

**Configuración recomendada:**
- Manejo de imágenes: **Ninguna**
- Modo de fragmentación: **Por Sección**
- Dividir en nivel: **2** (para capturar cada sección de política)
- Secciones por fragmento: **1**

**Por qué:** Mantiene todo privado, respeta la estructura del documento, facilita encontrar políticas específicas.

---

### Ejemplo 2: Catálogo de Productos con Fotos

**Escenario:** Estás subiendo un catálogo de productos con muchas imágenes que necesitan descripciones.

**Configuración recomendada:**
- Manejo de imágenes: **Básica** (o Con IA si las descripciones son cruciales y el contenido no es sensible)
- Modo de fragmentación: **Por Página**
- Páginas por fragmento: **1**

**Por qué:** Cada página de producto permanece junta, las imágenes son accesibles.

---

### Ejemplo 3: Artículo de Investigación

**Escenario:** Estás subiendo un artículo académico para propósitos de investigación.

**Configuración recomendada:**
- Manejo de imágenes: **Básica** (para extraer figuras y gráficos)
- Modo de fragmentación: **Por Sección**
- Dividir en nivel: **2**
- Secciones por fragmento: **1**

**Por qué:** Respeta la estructura del artículo (Resumen, Introducción, Métodos, etc.), mantiene las figuras accesibles.

---

### Ejemplo 4: Documento de Texto Largo

**Escenario:** Estás subiendo un documento largo sin estructura clara (como una transcripción o novela).

**Configuración recomendada:**
- Manejo de imágenes: **Ninguna**
- Modo de fragmentación: **Estándar**
- Tamaño del fragmento: **1000**
- Solapamiento: **200**

**Por qué:** El modo estándar funciona mejor para texto sin estructura, el solapamiento asegura que no se pierda contexto entre piezas.

---

## Preguntas Frecuentes

### P: ¿Qué pasa si elijo "Por Sección" pero mi documento no tiene encabezados?

El sistema automáticamente cambia al modo "Estándar". Obtendrás fragmentos de tamaño uniforme en su lugar.

### P: ¿Cómo sé qué tamaño de fragmento usar?

- **Para preguntas y respuestas:** Fragmentos más pequeños (500-1000) funcionan mejor porque son más enfocados
- **Para resúmenes:** Fragmentos más grandes (1500-2500) proporcionan más contexto
- **En caso de duda:** El valor por defecto (1000) funciona bien para la mayoría de casos

### P: ¿Qué tipos de archivo son compatibles?

PDF, Word (.docx), PowerPoint (.pptx), Excel (.xlsx, .xls), HTML, archivos de audio (.mp3, .wav), CSV, JSON, XML, archivos ZIP y libros electrónicos EPUB.

### P: ¿Se preservará mi archivo original?

¡Sí! El archivo original se guarda, y también se crea una versión en Markdown para facilitar la visualización.

### P: ¿Cuánto tiempo toma el procesamiento?

Depende del tamaño del archivo y las opciones elegidas:
- Documentos pequeños (< 10 páginas): Unos segundos
- Documentos grandes con descripciones de imágenes por IA: Varios minutos

---

## Obtener Ayuda

Si tienes preguntas o encuentras problemas:
1. Verifica que tu archivo esté en un formato compatible
2. Prueba primero con la configuración por defecto
3. Contacta a tu administrador del sistema para asistencia

---

*Última actualización: Enero 2026*

