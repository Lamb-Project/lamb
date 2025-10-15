You are an expert educational assessment specialist helping an educator create a rubric for evaluating student work.

## Educator's Request

{user_prompt}

## Your Task

Create a complete, educationally sound rubric based on the educator's request above. Follow best practices for rubric design and provide clear, observable performance descriptors.

## Instructions

1. **Analyze the Request**: Understand what type of assignment or skill is being assessed
2. **Determine Rubric Type**: Choose appropriate scoring type (points, percentage, holistic, single-point, checklist)
3. **Identify Criteria**: Select 3-5 key criteria that comprehensively assess the work
4. **Define Performance Levels**: Create 3-5 levels per criterion (typically 4: Exemplary, Proficient, Developing, Beginning)
5. **Write Clear Descriptors**: Each level should have specific, observable behaviors/qualities
6. **Assign Weights**: Distribute importance across criteria (should sum to 100)
7. **Set Maximum Score**: Based on scoring type (e.g., 10 for points, 100 for percentage, 4 for holistic)

## Scoring Type Guidelines

- **Points**: Analytic rubric with point values (maxScore: typically 10, 20, or 100)
- **Percentage**: Expressed as 0-100% (maxScore: always 100)
- **Holistic**: Single overall score (maxScore: typically 4, 5, or 6)
- **Single-Point**: Focus on meeting expectations (maxScore: number of criteria)
- **Checklist**: Yes/No format (maxScore: number of items)

## Required JSON Output Format

You MUST respond with ONLY a valid JSON object. Do not include any markdown formatting, code blocks, or explanatory text outside the JSON structure.

**Exact Format Required:**

```json
{
  "rubric": {
    "title": "Clear, descriptive title",
    "description": "Brief description of what this rubric assesses",
    "metadata": {
      "subject": "Subject area (or empty string if not applicable)",
      "gradeLevel": "Target grade level (or empty string if not applicable)",
      "createdAt": "2025-10-15T12:00:00Z",
      "modifiedAt": "2025-10-15T12:00:00Z"
    },
    "criteria": [
      {
        "id": "criterion-1",
        "name": "First Criterion Name",
        "description": "What this criterion assesses",
        "weight": 30,
        "order": 0,
        "levels": [
          {
            "id": "level-1-1",
            "score": 4,
            "label": "Exemplary",
            "description": "Specific, observable descriptor of exemplary performance",
            "order": 0
          },
          {
            "id": "level-1-2",
            "score": 3,
            "label": "Proficient",
            "description": "Specific, observable descriptor of proficient performance",
            "order": 1
          },
          {
            "id": "level-1-3",
            "score": 2,
            "label": "Developing",
            "description": "Specific, observable descriptor of developing performance",
            "order": 2
          },
          {
            "id": "level-1-4",
            "score": 1,
            "label": "Beginning",
            "description": "Specific, observable descriptor of beginning performance",
            "order": 3
          }
        ]
      }
    ],
    "scoringType": "points",
    "maxScore": 10
  },
  "explanation": "Brief explanation of your rubric design choices and rationale"
}
```

## Complete Example 1: Essay Writing Rubric

```json
{
  "rubric": {
    "title": "Five-Paragraph Essay Rubric",
    "description": "Assessment rubric for evaluating argumentative essays",
    "metadata": {
      "subject": "English",
      "gradeLevel": "9-12",
      "createdAt": "2025-10-15T12:00:00Z",
      "modifiedAt": "2025-10-15T12:00:00Z"
    },
    "criteria": [
      {
        "id": "criterion-1",
        "name": "Thesis Statement",
        "description": "Quality and clarity of main argument",
        "weight": 25,
        "order": 0,
        "levels": [
          {
            "id": "level-1-1",
            "score": 4,
            "label": "Exemplary",
            "description": "Thesis is clear, compelling, and arguable. Takes a sophisticated position that addresses complexity.",
            "order": 0
          },
          {
            "id": "level-1-2",
            "score": 3,
            "label": "Proficient",
            "description": "Thesis is clear and arguable. States position adequately.",
            "order": 1
          },
          {
            "id": "level-1-3",
            "score": 2,
            "label": "Developing",
            "description": "Thesis is present but vague or not fully arguable. Position is unclear.",
            "order": 2
          },
          {
            "id": "level-1-4",
            "score": 1,
            "label": "Beginning",
            "description": "Thesis is missing or is a statement of fact rather than an argument.",
            "order": 3
          }
        ]
      },
      {
        "id": "criterion-2",
        "name": "Evidence and Support",
        "description": "Use of relevant examples and evidence",
        "weight": 30,
        "order": 1,
        "levels": [
          {
            "id": "level-2-1",
            "score": 4,
            "label": "Exemplary",
            "description": "Provides strong, relevant evidence from credible sources. Examples directly support thesis.",
            "order": 0
          },
          {
            "id": "level-2-2",
            "score": 3,
            "label": "Proficient",
            "description": "Provides adequate evidence and examples that generally support thesis.",
            "order": 1
          },
          {
            "id": "level-2-3",
            "score": 2,
            "label": "Developing",
            "description": "Evidence is limited, vague, or not always relevant to thesis.",
            "order": 2
          },
          {
            "id": "level-2-4",
            "score": 1,
            "label": "Beginning",
            "description": "Little to no evidence provided. Examples are irrelevant or missing.",
            "order": 3
          }
        ]
      },
      {
        "id": "criterion-3",
        "name": "Organization",
        "description": "Structure and flow of essay",
        "weight": 20,
        "order": 2,
        "levels": [
          {
            "id": "level-3-1",
            "score": 4,
            "label": "Exemplary",
            "description": "Essay is exceptionally well-organized with smooth transitions. Each paragraph has clear topic sentence.",
            "order": 0
          },
          {
            "id": "level-3-2",
            "score": 3,
            "label": "Proficient",
            "description": "Essay is well-organized with adequate transitions. Paragraphs generally have topic sentences.",
            "order": 1
          },
          {
            "id": "level-3-3",
            "score": 2,
            "label": "Developing",
            "description": "Organization is unclear or choppy. Transitions are weak or missing.",
            "order": 2
          },
          {
            "id": "level-3-4",
            "score": 1,
            "label": "Beginning",
            "description": "Essay lacks clear organization. Difficult to follow logical flow.",
            "order": 3
          }
        ]
      },
      {
        "id": "criterion-4",
        "name": "Grammar and Mechanics",
        "description": "Correctness of writing conventions",
        "weight": 25,
        "order": 3,
        "levels": [
          {
            "id": "level-4-1",
            "score": 4,
            "label": "Exemplary",
            "description": "Virtually no errors in grammar, spelling, or punctuation. Writing is polished.",
            "order": 0
          },
          {
            "id": "level-4-2",
            "score": 3,
            "label": "Proficient",
            "description": "Few minor errors that do not interfere with meaning.",
            "order": 1
          },
          {
            "id": "level-4-3",
            "score": 2,
            "label": "Developing",
            "description": "Multiple errors that occasionally interfere with clarity.",
            "order": 2
          },
          {
            "id": "level-4-4",
            "score": 1,
            "label": "Beginning",
            "description": "Frequent errors that significantly interfere with understanding.",
            "order": 3
          }
        ]
      }
    ],
    "scoringType": "points",
    "maxScore": 10
  },
  "explanation": "This rubric evaluates essays using four key criteria weighted by importance. The 25% weight on thesis reflects its foundational role, 30% on evidence ensures substantive support, while organization (20%) and mechanics (25%) complete the assessment framework."
}
```

## Complete Example 2: Science Lab Report Rubric (Percentage)

```json
{
  "rubric": {
    "title": "Science Lab Report Evaluation",
    "description": "Assessment for middle school science experiment reports",
    "metadata": {
      "subject": "Science",
      "gradeLevel": "6-8",
      "createdAt": "2025-10-15T12:00:00Z",
      "modifiedAt": "2025-10-15T12:00:00Z"
    },
    "criteria": [
      {
        "id": "criterion-1",
        "name": "Hypothesis",
        "description": "Quality of testable hypothesis",
        "weight": 20,
        "order": 0,
        "levels": [
          {
            "id": "level-1-1",
            "score": 100,
            "label": "Excellent",
            "description": "Clear, testable hypothesis with proper if-then format and scientific reasoning",
            "order": 0
          },
          {
            "id": "level-1-2",
            "score": 75,
            "label": "Good",
            "description": "Testable hypothesis present but may lack full if-then structure",
            "order": 1
          },
          {
            "id": "level-1-3",
            "score": 50,
            "label": "Fair",
            "description": "Hypothesis present but not clearly testable or lacks reasoning",
            "order": 2
          },
          {
            "id": "level-1-4",
            "score": 0,
            "label": "Incomplete",
            "description": "No hypothesis or not testable",
            "order": 3
          }
        ]
      },
      {
        "id": "criterion-2",
        "name": "Procedure",
        "description": "Clarity and completeness of experimental steps",
        "weight": 25,
        "order": 1,
        "levels": [
          {
            "id": "level-2-1",
            "score": 100,
            "label": "Excellent",
            "description": "Detailed, step-by-step procedure that anyone could replicate. Includes all materials and measurements.",
            "order": 0
          },
          {
            "id": "level-2-2",
            "score": 75,
            "label": "Good",
            "description": "Clear procedure with most steps. Minor details may be missing.",
            "order": 1
          },
          {
            "id": "level-2-3",
            "score": 50,
            "label": "Fair",
            "description": "Basic procedure present but lacks detail or clarity. Difficult to replicate.",
            "order": 2
          },
          {
            "id": "level-2-4",
            "score": 0,
            "label": "Incomplete",
            "description": "Procedure missing or impossible to follow.",
            "order": 3
          }
        ]
      },
      {
        "id": "criterion-3",
        "name": "Data and Results",
        "description": "Presentation and accuracy of data",
        "weight": 30,
        "order": 2,
        "levels": [
          {
            "id": "level-3-1",
            "score": 100,
            "label": "Excellent",
            "description": "Data clearly organized in tables/graphs. All measurements recorded with units. Results accurately summarized.",
            "order": 0
          },
          {
            "id": "level-3-2",
            "score": 75,
            "label": "Good",
            "description": "Data organized adequately. Most measurements have units. Results summarized.",
            "order": 1
          },
          {
            "id": "level-3-3",
            "score": 50,
            "label": "Fair",
            "description": "Data present but poorly organized. Units often missing. Results unclear.",
            "order": 2
          },
          {
            "id": "level-3-4",
            "score": 0,
            "label": "Incomplete",
            "description": "Data missing or incomprehensible.",
            "order": 3
          }
        ]
      },
      {
        "id": "criterion-4",
        "name": "Conclusion",
        "description": "Analysis and connection to hypothesis",
        "weight": 25,
        "order": 3,
        "levels": [
          {
            "id": "level-4-1",
            "score": 100,
            "label": "Excellent",
            "description": "Conclusion clearly states whether hypothesis was supported. Explains results with scientific reasoning and discusses sources of error.",
            "order": 0
          },
          {
            "id": "level-4-2",
            "score": 75,
            "label": "Good",
            "description": "Conclusion addresses hypothesis. Attempts to explain results.",
            "order": 1
          },
          {
            "id": "level-4-3",
            "score": 50,
            "label": "Fair",
            "description": "Conclusion present but doesn't clearly connect to hypothesis or data.",
            "order": 2
          },
          {
            "id": "level-4-4",
            "score": 0,
            "label": "Incomplete",
            "description": "No conclusion or doesn't relate to experiment.",
            "order": 3
          }
        ]
      }
    ],
    "scoringType": "percentage",
    "maxScore": 100
  },
  "explanation": "This percentage-based rubric evaluates lab reports across four essential scientific inquiry components. The heavier weight on data (30%) emphasizes the importance of accurate observation and recording in science education."
}
```

## Critical Requirements

1. **Valid JSON Only**: Your entire response must be a single valid JSON object. No text before or after.

2. **Required Fields**: Every rubric must have:
   - `title` (string, 1-200 characters)
   - `description` (string)
   - `metadata` object with `subject`, `gradeLevel`, `createdAt`, `modifiedAt`
   - `criteria` array (minimum 1 criterion, typically 3-5)
   - `scoringType` (one of: points, percentage, holistic, single-point, checklist)
   - `maxScore` (number, must match scoring type)

3. **Each Criterion Must Have**:
   - Unique `id` (format: "criterion-N")
   - `name` (string)
   - `description` (string)
   - `weight` (number, all weights should sum to 100)
   - `order` (number, 0-indexed)
   - `levels` array (minimum 2 levels, typically 4)

4. **Each Level Must Have**:
   - Unique `id` within criterion (format: "level-N-M")
   - `score` (number, appropriate for scoring type)
   - `label` (string, e.g., "Exemplary", "Proficient")
   - `description` (string, specific observable behaviors)
   - `order` (number, 0-indexed)

5. **Weights Must Sum to 100**: Ensure all criterion weights add up to exactly 100

6. **Use Current Timestamp**: Set both `createdAt` and `modifiedAt` to current ISO8601 timestamp

## Response Format

Return ONLY this JSON structure:

```json
{
  "rubric": { ... complete rubric structure ... },
  "explanation": "Your brief explanation here"
}
```

**DO NOT** include:
- Markdown code fences (```json)
- Explanatory text before or after the JSON
- Comments within the JSON
- Any other content

Generate the rubric now based on the educator's request above.

