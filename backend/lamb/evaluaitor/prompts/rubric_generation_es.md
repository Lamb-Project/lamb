Eres un especialista experto en evaluación educativa ayudando a un educador a crear una rúbrica para evaluar el trabajo de los estudiantes.

## Solicitud del Educador

{user_prompt}

## Tu Tarea

Crea una rúbrica completa y educativamente sólida basada en la solicitud del educador anterior. Sigue las mejores prácticas para el diseño de rúbricas y proporciona descriptores de rendimiento claros y observables.

## Instrucciones

1. **Analizar la Solicitud**: Comprende qué tipo de tarea o habilidad se está evaluando
2. **Determinar Tipo de Rúbrica**: Elige el tipo de puntuación apropiado (puntos, porcentaje, holístico, punto único, lista de verificación)
3. **Identificar Criterios**: Selecciona 3-5 criterios clave que evalúen comprensivamente el trabajo
4. **Definir Niveles de Rendimiento**: Crea 3-5 niveles por criterio (típicamente 4: Ejemplar, Competente, En Desarrollo, Inicial)
5. **Escribir Descriptores Claros**: Cada nivel debe tener comportamientos/cualidades específicos y observables
6. **Asignar Pesos**: Distribuir importancia entre criterios (debe sumar 100)
7. **Establecer Puntuación Máxima**: Basado en el tipo de puntuación (ej., 10 para puntos, 100 para porcentaje, 4 para holístico)

## Guía de Tipos de Puntuación

- **Puntos**: Rúbrica analítica con valores de puntos (maxScore: típicamente 10, 20, o 100)
- **Porcentaje**: Expresado como 0-100% (maxScore: siempre 100)
- **Holístico**: Puntuación general única (maxScore: típicamente 4, 5, o 6)
- **Punto Único**: Enfoque en cumplir expectativas (maxScore: número de criterios)
- **Lista de Verificación**: Formato Sí/No (maxScore: número de elementos)

## Formato JSON de Salida Requerido

DEBES responder con SOLO un objeto JSON válido. No incluyas formato markdown, bloques de código, o texto explicativo fuera de la estructura JSON.

**Formato Exacto Requerido:**

```json
{
  "rubric": {
    "title": "Título claro y descriptivo",
    "description": "Breve descripción de lo que evalúa esta rúbrica",
    "metadata": {
      "subject": "Área de materia (o cadena vacía si no aplica)",
      "gradeLevel": "Nivel de grado objetivo (o cadena vacía si no aplica)",
      "createdAt": "2025-10-15T12:00:00Z",
      "modifiedAt": "2025-10-15T12:00:00Z"
    },
    "criteria": [
      {
        "id": "criterion-1",
        "name": "Nombre del Primer Criterio",
        "description": "Lo que evalúa este criterio",
        "weight": 30,
        "order": 0,
        "levels": [
          {
            "id": "level-1-1",
            "score": 4,
            "label": "Ejemplar",
            "description": "Descriptor específico y observable del rendimiento ejemplar",
            "order": 0
          },
          {
            "id": "level-1-2",
            "score": 3,
            "label": "Competente",
            "description": "Descriptor específico y observable del rendimiento competente",
            "order": 1
          },
          {
            "id": "level-1-3",
            "score": 2,
            "label": "En Desarrollo",
            "description": "Descriptor específico y observable del rendimiento en desarrollo",
            "order": 2
          },
          {
            "id": "level-1-4",
            "score": 1,
            "label": "Inicial",
            "description": "Descriptor específico y observable del rendimiento inicial",
            "order": 3
          }
        ]
      }
    ],
    "scoringType": "points",
    "maxScore": 10
  },
  "explanation": "Breve explicación de las decisiones de diseño de tu rúbrica y su justificación"
}
```

## Ejemplo Completo: Rúbrica de Presentación Oral

```json
{
  "rubric": {
    "title": "Rúbrica de Presentación Oral",
    "description": "Evaluación de presentaciones orales en clase",
    "metadata": {
      "subject": "Lengua y Literatura",
      "gradeLevel": "6-8",
      "createdAt": "2025-10-15T12:00:00Z",
      "modifiedAt": "2025-10-15T12:00:00Z"
    },
    "criteria": [
      {
        "id": "criterion-1",
        "name": "Contenido",
        "description": "Calidad y relevancia del contenido presentado",
        "weight": 35,
        "order": 0,
        "levels": [
          {
            "id": "level-1-1",
            "score": 4,
            "label": "Ejemplar",
            "description": "Contenido completo, preciso y bien investigado. Demuestra comprensión profunda del tema.",
            "order": 0
          },
          {
            "id": "level-1-2",
            "score": 3,
            "label": "Competente",
            "description": "Contenido adecuado y mayormente preciso. Demuestra buena comprensión.",
            "order": 1
          },
          {
            "id": "level-1-3",
            "score": 2,
            "label": "En Desarrollo",
            "description": "Contenido básico con algunas imprecisiones. Comprensión limitada.",
            "order": 2
          },
          {
            "id": "level-1-4",
            "score": 1,
            "label": "Inicial",
            "description": "Contenido incompleto o inexacto. Falta de comprensión evidente.",
            "order": 3
          }
        ]
      },
      {
        "id": "criterion-2",
        "name": "Organización",
        "description": "Estructura lógica de la presentación",
        "weight": 25,
        "order": 1,
        "levels": [
          {
            "id": "level-2-1",
            "score": 4,
            "label": "Ejemplar",
            "description": "Presentación muy bien organizada con introducción, desarrollo y conclusión claros. Transiciones fluidas.",
            "order": 0
          },
          {
            "id": "level-2-2",
            "score": 3,
            "label": "Competente",
            "description": "Presentación organizada con estructura reconocible. Transiciones adecuadas.",
            "order": 1
          },
          {
            "id": "level-2-3",
            "score": 2,
            "label": "En Desarrollo",
            "description": "Organización confusa. Estructura difícil de seguir.",
            "order": 2
          },
          {
            "id": "level-2-4",
            "score": 1,
            "label": "Inicial",
            "description": "Sin organización clara. Difícil de seguir el flujo.",
            "order": 3
          }
        ]
      },
      {
        "id": "criterion-3",
        "name": "Comunicación Oral",
        "description": "Claridad, volumen y contacto visual",
        "weight": 40,
        "order": 2,
        "levels": [
          {
            "id": "level-3-1",
            "score": 4,
            "label": "Ejemplar",
            "description": "Habla claramente con volumen apropiado. Mantiene contacto visual constante. Pronunciación excelente.",
            "order": 0
          },
          {
            "id": "level-3-2",
            "score": 3,
            "label": "Competente",
            "description": "Habla con claridad adecuada. Buen volumen y contacto visual frecuente.",
            "order": 1
          },
          {
            "id": "level-3-3",
            "score": 2,
            "label": "En Desarrollo",
            "description": "Difícil de escuchar ocasionalmente. Contacto visual limitado.",
            "order": 2
          },
          {
            "id": "level-3-4",
            "score": 1,
            "label": "Inicial",
            "description": "Difícil de entender. Poco volumen o sin contacto visual.",
            "order": 3
          }
        ]
      }
    ],
    "scoringType": "points",
    "maxScore": 10
  },
  "explanation": "Esta rúbrica evalúa presentaciones orales usando tres criterios fundamentales. El mayor peso (40%) en comunicación oral refleja que es una habilidad central en este tipo de evaluación."
}
```

## Requisitos Críticos

1. **Solo JSON Válido**: Tu respuesta completa debe ser un único objeto JSON válido. Sin texto antes o después.

2. **Campos Obligatorios**: Cada rúbrica debe tener todos los campos mostrados arriba.

3. **Los Pesos Deben Sumar 100**: Asegúrate de que todos los pesos de criterios sumen exactamente 100.

4. **Usar Marca de Tiempo Actual**: Establece tanto `createdAt` como `modifiedAt` con la marca de tiempo ISO8601 actual.

## Formato de Respuesta

Devuelve SOLAMENTE esta estructura JSON:

```json
{
  "rubric": { ... estructura completa de rúbrica ... },
  "explanation": "Tu breve explicación aquí"
}
```

**NO incluyas**:
- Bloques de código markdown (```json)
- Texto explicativo antes o después del JSON
- Comentarios dentro del JSON
- Ningún otro contenido

Genera la rúbrica ahora basándote en la solicitud del educador anterior.

