So I am developing an app, and I want to add a new feature. 
Educational rubrics. I have several goals here:
First I need a data format, LLM friendly, to represent a rubric. 
Seccond I need a user interface that allows me to represent the rubric for a user (an educator) so the user can perform two actions:
* make specific manual edits (like edit one cell of the rubric) 
* talk to a LLM to change aspects of the rubric according to her criteria or the nature of the exercise. 
*
Great project! Let me help you design both the data format and UI approach for educational rubrics.
Data Format
For an LLM-friendly rubric format, I'd recommend a structured JSON format that's both human-readable and easy for LLMs to parse and modify:
json
{
  "rubricId": "unique-id",
  "title": "Essay Writing Rubric",
  "description": "Rubric for evaluating argumentative essays",
  "metadata": {
    "subject": "English",
    "gradeLevel": "9-12",
    "createdAt": "2025-10-13",
    "modifiedAt": "2025-10-13"
  },
  "criteria": [
    {
      "id": "criterion-1",
      "name": "Thesis Statement",
      "description": "Quality and clarity of the main argument",
      "weight": 20,
      "levels": [
        {
          "id": "level-1",
          "score": 4,
          "label": "Exemplary",
          "description": "Thesis is clear, compelling, and demonstrates sophisticated understanding"
        },
        {
          "id": "level-2",
          "score": 3,
          "label": "Proficient",
          "description": "Thesis is clear and appropriate"
        },
        {
          "id": "level-3",
          "score": 2,
          "label": "Developing",
          "description": "Thesis is present but unclear or weak"
        },
        {
          "id": "level-4",
          "score": 1,
          "label": "Beginning",
          "description": "Thesis is missing or unintelligible"
        }
      ]
    }
  ],
  "scoringType": "points",
  "maxScore": 100
}
Why this format works well:
Clear hierarchy: Rubric → Criteria → Levels
IDs everywhere: Makes targeted edits easy ("change criterion-1, level-2")
Semantic structure: LLMs can understand the relationships
Extensible: Easy to add fields like examples, tips, or student-facing descriptions
User Interface Design
For the UI, I'd suggest a hybrid approach with three main components:
1. Visual Rubric Table
Traditional grid view where educators can:
Click any cell to edit inline
Drag to reorder criteria
Add/remove rows and columns
See the full rubric at a glance
2. AI Chat Panel (side-by-side or overlay)
Conversational interface where educators can say things like:
"Make this rubric appropriate for 6th graders"
"Add a criterion for creativity"
"Rewrite the 'Exemplary' level for Thesis to be more specific"
"Convert this to a single-point rubric"
3. Change Preview & Acceptance
When the LLM suggests changes:
Show a diff view (before/after)
Highlight what's changing
Allow accept/reject/modify
Enable undo/redo
Implementation Approach
For LLM Integration:
System Prompt Template:
"You are helping an educator modify their rubric. The current rubric is:
[JSON rubric here]

When the educator requests changes:
1. Return the COMPLETE modified rubric in JSON format
2. Explain what you changed and why
3. Ask clarifying questions if the request is ambiguous

Maintain educational best practices and alignment with the original learning objectives."
For Manual Edits:
Each cell edit updates the specific path in the JSON
Use a state management system (Redux, Zustand, etc.) to track changes
Validate edits (e.g., scores are numeric, descriptions aren't empty)
Additional Considerations
Would you like me to create a working prototype? I can build:
An interactive React component showing the rubric table
A mock chat interface for LLM interactions
Demo JSON structure with sample data
Also consider:
Should rubrics support different scoring types (points, proficiency levels, single-point)?
Do you need rubric templates or starting points?
Should there be a bank of common criteria educators can choose from?
How should collaborative editing work if multiple educators use the same rubric?
What aspect would you like to dive into first?
my development stack is python 3.11 with fastapi , my frontend is svelte 5.0 with javascript+jsdoc ...
explain how Use a state management system (Redux, Zustand, etc.) to track changes ...
Great stack! For Svelte 5.0, you don't need Redux or Zustand - Svelte has excellent built-in state management with runes (the new Svelte 5 reactivity system). Let me show you how to manage rubric state effectively.
Svelte 5 State Management for Rubrics
1. Basic Approach: Svelte Runes
Svelte 5 uses runes ($state, $derived, $effect) for reactivity. Here's a simple rubric store:
javascript
// stores/rubricStore.svelte.js

/**
 * @typedef {Object} RubricLevel
 * @property {string} id
 * @property {number} score
 * @property {string} label
 * @property {string} description
 */

/**
 * @typedef {Object} RubricCriterion
 * @property {string} id
 * @property {string} name
 * @property {string} description
 * @property {number} weight
 * @property {RubricLevel[]} levels
 */

/**
 * @typedef {Object} Rubric
 * @property {string} rubricId
 * @property {string} title
 * @property {string} description
 * @property {Object} metadata
 * @property {RubricCriterion[]} criteria
 * @property {string} scoringType
 * @property {number} maxScore
 */

class RubricStore {
  /** @type {Rubric | null} */
  #rubric = $state(null);
  
  /** @type {Array<Rubric>} */
  #history = $state([]);
  
  /** @type {number} */
  #historyIndex = $state(-1);

  get rubric() {
    return this.#rubric;
  }

  get canUndo() {
    return this.#historyIndex > 0;
  }

  get canRedo() {
    return this.#historyIndex < this.#history.length - 1;
  }

  /**
   * Initialize or load a rubric
   * @param {Rubric} rubric
   */
  loadRubric(rubric) {
    this.#rubric = rubric;
    this.#history = [structuredClone(rubric)];
    this.#historyIndex = 0;
  }

  /**
   * Save current state to history (for undo/redo)
   */
  #saveToHistory() {
    if (!this.#rubric) return;
    
    // Remove any future history if we're not at the end
    this.#history = this.#history.slice(0, this.#historyIndex + 1);
    
    // Add current state
    this.#history.push(structuredClone(this.#rubric));
    this.#historyIndex++;
    
    // Limit history size
    if (this.#history.length > 50) {
      this.#history.shift();
      this.#historyIndex--;
    }
  }

  /**
   * Update a specific cell in the rubric
   * @param {string} criterionId
   * @param {string} levelId
   * @param {string} field - 'description', 'label', 'score'
   * @param {any} value
   */
  updateCell(criterionId, levelId, field, value) {
    if (!this.#rubric) return;

    const criterion = this.#rubric.criteria.find(c => c.id === criterionId);
    if (!criterion) return;

    const level = criterion.levels.find(l => l.id === levelId);
    if (!level) return;

    level[field] = value;
    this.#rubric.metadata.modifiedAt = new Date().toISOString();
    
    this.#saveToHistory();
  }

  /**
   * Update criterion metadata
   * @param {string} criterionId
   * @param {Partial<RubricCriterion>} updates
   */
  updateCriterion(criterionId, updates) {
    if (!this.#rubric) return;

    const criterion = this.#rubric.criteria.find(c => c.id === criterionId);
    if (!criterion) return;

    Object.assign(criterion, updates);
    this.#rubric.metadata.modifiedAt = new Date().toISOString();
    
    this.#saveToHistory();
  }

  /**
   * Add a new criterion
   * @param {RubricCriterion} criterion
   */
  addCriterion(criterion) {
    if (!this.#rubric) return;

    this.#rubric.criteria.push(criterion);
    this.#saveToHistory();
  }

  /**
   * Remove a criterion
   * @param {string} criterionId
   */
  removeCriterion(criterionId) {
    if (!this.#rubric) return;

    this.#rubric.criteria = this.#rubric.criteria.filter(c => c.id !== criterionId);
    this.#saveToHistory();
  }

  /**
   * Replace entire rubric (for LLM updates)
   * @param {Rubric} newRubric
   */
  replaceRubric(newRubric) {
    this.#rubric = newRubric;
    this.#saveToHistory();
  }

  undo() {
    if (!this.canUndo) return;
    
    this.#historyIndex--;
    this.#rubric = structuredClone(this.#history[this.#historyIndex]);
  }

  redo() {
    if (!this.canRedo) return;
    
    this.#historyIndex++;
    this.#rubric = structuredClone(this.#history[this.#historyIndex]);
  }

  /**
   * Get a preview of changes between current and proposed rubric
   * @param {Rubric} proposedRubric
   * @returns {Object} Changes object
   */
  getChanges(proposedRubric) {
    const changes = {
      modified: [],
      added: [],
      removed: []
    };

    // Compare criteria
    const currentIds = new Set(this.#rubric?.criteria.map(c => c.id) || []);
    const proposedIds = new Set(proposedRubric.criteria.map(c => c.id));

    // Find added criteria
    for (const criterion of proposedRubric.criteria) {
      if (!currentIds.has(criterion.id)) {
        changes.added.push({ type: 'criterion', item: criterion });
      }
    }

    // Find removed criteria
    for (const criterion of this.#rubric?.criteria || []) {
      if (!proposedIds.has(criterion.id)) {
        changes.removed.push({ type: 'criterion', item: criterion });
      }
    }

    // Find modified criteria (simplified - you'd want deeper comparison)
    for (const criterion of proposedRubric.criteria) {
      const current = this.#rubric?.criteria.find(c => c.id === criterion.id);
      if (current && JSON.stringify(current) !== JSON.stringify(criterion)) {
        changes.modified.push({ 
          type: 'criterion', 
          before: current, 
          after: criterion 
        });
      }
    }

    return changes;
  }
}

// Create singleton instance
export const rubricStore = new RubricStore();
2. Using the Store in Components
svelte
<!-- RubricTable.svelte -->
<script>
  import { rubricStore } from './stores/rubricStore.svelte.js';

  /** @type {string} */
  let editingCell = $state(null);
  
  /**
   * @param {string} criterionId
   * @param {string} levelId
   */
  function startEdit(criterionId, levelId) {
    editingCell = `${criterionId}-${levelId}`;
  }

  /**
   * @param {string} criterionId
   * @param {string} levelId
   * @param {string} field
   * @param {Event} event
   */
  function handleCellEdit(criterionId, levelId, field, event) {
    const value = event.target.textContent;
    rubricStore.updateCell(criterionId, levelId, field, value);
    editingCell = null;
  }
</script>

<div class="rubric-table">
  <table>
    <thead>
      <tr>
        <th>Criterion</th>
        {#each rubricStore.rubric?.criteria[0]?.levels || [] as level}
          <th>{level.label} ({level.score})</th>
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each rubricStore.rubric?.criteria || [] as criterion}
        <tr>
          <td>
            <strong>{criterion.name}</strong>
            <p>{criterion.description}</p>
          </td>
          {#each criterion.levels as level}
            <td
              contenteditable="true"
              onblur={(e) => handleCellEdit(criterion.id, level.id, 'description', e)}
              onfocus={() => startEdit(criterion.id, level.id)}
            >
              {level.description}
            </td>
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>

  <div class="actions">
    <button onclick={() => rubricStore.undo()} disabled={!rubricStore.canUndo}>
      Undo
    </button>
    <button onclick={() => rubricStore.redo()} disabled={!rubricStore.canRedo}>
      Redo
    </button>
  </div>
</div>
3. Integration with FastAPI Backend
javascript
// api/rubricApi.js

/**
 * Fetch rubric from backend
 * @param {string} rubricId
 * @returns {Promise<Rubric>}
 */
export async function fetchRubric(rubricId) {
  const response = await fetch(`/api/rubrics/${rubricId}`);
  if (!response.ok) throw new Error('Failed to fetch rubric');
  return response.json();
}

/**
 * Save rubric to backend
 * @param {Rubric} rubric
 * @returns {Promise<Rubric>}
 */
export async function saveRubric(rubric) {
  const response = await fetch(`/api/rubrics/${rubric.rubricId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(rubric)
  });
  if (!response.ok) throw new Error('Failed to save rubric');
  return response.json();
}

/**
 * Ask LLM to modify rubric
 * @param {string} rubricId
 * @param {string} prompt - User's request
 * @returns {Promise<{rubric: Rubric, explanation: string}>}
 */
export async function askLLM(rubricId, prompt) {
  const response = await fetch(`/api/rubrics/${rubricId}/ai-modify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt })
  });
  if (!response.ok) throw new Error('LLM request failed');
  return response.json();
}
4. LLM Chat Component
svelte
<!-- AIChat.svelte -->
<script>
  import { rubricStore } from './stores/rubricStore.svelte.js';
  import { askLLM } from './api/rubricApi.js';

  let prompt = $state('');
  let loading = $state(false);
  let pendingChanges = $state(null);

  async function submitPrompt() {
    if (!prompt.trim() || !rubricStore.rubric) return;

    loading = true;
    try {
      const result = await askLLM(rubricStore.rubric.rubricId, prompt);
      
      // Show preview of changes
      pendingChanges = {
        rubric: result.rubric,
        explanation: result.explanation,
        changes: rubricStore.getChanges(result.rubric)
      };
    } catch (error) {
      alert('Error: ' + error.message);
    } finally {
      loading = false;
    }
  }

  function acceptChanges() {
    if (pendingChanges) {
      rubricStore.replaceRubric(pendingChanges.rubric);
      pendingChanges = null;
      prompt = '';
    }
  }

  function rejectChanges() {
    pendingChanges = null;
  }
</script>

<div class="ai-chat">
  <div class="input-area">
    <textarea
      bind:value={prompt}
      placeholder="Ask me to modify your rubric..."
      disabled={loading}
    />
    <button onclick={submitPrompt} disabled={loading || !prompt.trim()}>
      {loading ? 'Processing...' : 'Submit'}
    </button>
  </div>

  {#if pendingChanges}
    <div class="changes-preview">
      <h3>Proposed Changes</h3>
      <p>{pendingChanges.explanation}</p>
      
      <div class="changes-list">
        {#if pendingChanges.changes.added.length > 0}
          <div class="added">
            <strong>Added:</strong>
            {#each pendingChanges.changes.added as change}
              <p>+ {change.item.name}</p>
            {/each}
          </div>
        {/if}
        
        {#if pendingChanges.changes.removed.length > 0}
          <div class="removed">
            <strong>Removed:</strong>
            {#each pendingChanges.changes.removed as change}
              <p>- {change.item.name}</p>
            {/each}
          </div>
        {/if}
        
        {#if pendingChanges.changes.modified.length > 0}
          <div class="modified">
            <strong>Modified:</strong>
            {#each pendingChanges.changes.modified as change}
              <p>~ {change.after.name}</p>
            {/each}
          </div>
        {/if}
      </div>

      <div class="actions">
        <button onclick={acceptChanges}>Accept Changes</button>
        <button onclick={rejectChanges}>Reject</button>
      </div>
    </div>
  {/if}
</div>
Key Points
Svelte 5 Runes: Use $state for reactive data, no external state manager needed
Class-based Store: Encapsulates all rubric logic with proper typing via JSDoc
Undo/Redo: Built-in history management using structuredClone
Change Preview: Compare current vs. proposed rubric before applying LLM changes
FastAPI Integration: Simple async functions to communicate with your backend
This approach is cleaner and more performant than Redux/Zustand for Svelte, and takes full advantage of Svelte 5's new reactivity system!
Would you like me to create the FastAPI backend endpoints to go with this frontend code?
ok, write down a description of the json for the rubric you are proposing
Educational Rubric JSON Format Specification
Overview
A structured JSON format designed to be both human-readable and LLM-friendly for representing educational assessment rubrics. This format supports various rubric types and allows for precise programmatic manipulation.
Root Object Structure
javascript
{
  "rubricId": string,      // Unique identifier for the rubric
  "title": string,         // Human-readable title
  "description": string,   // Purpose and context of the rubric
  "metadata": object,      // Additional rubric information
  "criteria": array,       // Array of assessment criteria
  "scoringType": string,   // Type of scoring system used
  "maxScore": number       // Maximum possible score
}
Field Descriptions
rubricId (string, required)
Unique identifier for the rubric
Format: Any string, commonly UUID or slug format
Example: "rubric-essay-writing-2025" or "550e8400-e29b-41d4-a716-446655440000"
Used for database lookups and API operations
title (string, required)
Concise, descriptive name for the rubric
Typically 3-10 words
Example: "Argumentative Essay Rubric", "Science Lab Report Assessment"
description (string, required)
Detailed explanation of the rubric's purpose and scope
Should include: what assignment this assesses, learning objectives, target audience
Example: "This rubric evaluates argumentative essays for 9th grade English students, focusing on thesis development, evidence use, and writing mechanics."
metadata (object, required)
Contains contextual information about the rubric:
javascript
{
  "subject": string,        // Academic subject (e.g., "English", "Mathematics", "Science")
  "gradeLevel": string,     // Target grade(s) (e.g., "9-12", "College", "6th Grade")
  "createdAt": string,      // ISO 8601 datetime of creation
  "modifiedAt": string,     // ISO 8601 datetime of last modification
  "author": string,         // Optional: creator's name or ID
  "version": string,        // Optional: version number (e.g., "1.0", "2.3")
  "tags": array<string>     // Optional: categorization tags
}
Example:
json
{
  "subject": "English Language Arts",
  "gradeLevel": "9-12",
  "createdAt": "2025-10-13T14:30:00Z",
  "modifiedAt": "2025-10-13T16:45:00Z",
  "author": "teacher-id-123",
  "version": "1.0",
  "tags": ["writing", "argumentative", "common-core"]
}
criteria (array, required)
Array of criterion objects. Each criterion represents one dimension of assessment.
Criterion Object Structure:
javascript
{
  "id": string,              // Unique identifier within this rubric
  "name": string,            // Short name/title of the criterion
  "description": string,     // Detailed explanation of what's being assessed
  "weight": number,          // Relative importance (percentage or points)
  "levels": array,           // Array of performance levels
  "order": number            // Optional: display order (0-indexed)
}
Criterion Fields:
id (string, required): Unique within the rubric
Format: "criterion-1", "thesis-statement", "evidence-quality"
Used for programmatic updates and references
name (string, required): Brief, descriptive label
Examples: "Thesis Statement", "Use of Evidence", "Grammar and Mechanics"
Typically 1-5 words
description (string, required): Explains what this criterion measures
Should clarify expectations and scope
Example: "Quality and clarity of the main argument or claim"
weight (number, required): Importance of this criterion
Can be percentage (0-100) or point value
All weights should sum logically (e.g., sum to 100 for percentages)
Example: 20 (meaning 20% of total score or 20 points)
levels (array, required): Performance level descriptors
Must contain at least 2 levels
Typically 3-6 levels (e.g., Beginning, Developing, Proficient, Exemplary)
order (number, optional): Display sequence
Zero-indexed position
If omitted, use array order
levels (array within criterion, required)
Array of performance level objects describing quality gradations.
Level Object Structure:
javascript
{
  "id": string,              // Unique identifier within this criterion
  "score": number,           // Point value for this level
  "label": string,           // Name of the performance level
  "description": string,     // Detailed descriptor of performance at this level
  "order": number            // Optional: display order (typically 0 = highest)
}
Level Fields:
id (string, required): Unique within the criterion
Format: "level-1", "exemplary", "proficient"
Used for cell-specific edits
score (number, required): Point value assigned
Can be any numeric value
Common scales: 1-4, 0-5, 1-10
Example: 4 for highest, 1 for lowest
label (string, required): Name of the performance tier
Common labels: "Exemplary", "Proficient", "Developing", "Beginning"
Alternative: "Advanced", "Intermediate", "Novice"
Or: "Exceeds", "Meets", "Approaching", "Below"
description (string, required): Detailed performance descriptor
Should be specific and observable
Use active language and concrete examples when possible
Example: "Thesis is clear, compelling, and demonstrates sophisticated understanding of the topic with nuanced positioning"
order (number, optional): Display position
Typically 0 = highest performance level (leftmost in table)
If omitted, use array order
scoringType (string, required)
Defines how the rubric calculates scores.
Supported Values:
"points": Traditional point-based (sum of criterion scores)
"percentage": Percentage-based calculation
"holistic": Single overall score using all criteria
"single-point": Single-point rubric format (only describes proficiency)
"checklist": Binary yes/no for each criterion
Example: "points"
maxScore (number, required)
Maximum possible score achievable.
For point-based: sum of all criterion weights
For percentage: typically 100
For holistic: highest possible score value
Example: 100, 50, 4.0
Complete Example
json
{
  "rubricId": "essay-rubric-001",
  "title": "Argumentative Essay Rubric",
  "description": "Rubric for evaluating argumentative essays in 10th grade English, aligned with Common Core writing standards",
  "metadata": {
    "subject": "English Language Arts",
    "gradeLevel": "10",
    "createdAt": "2025-10-13T10:00:00Z",
    "modifiedAt": "2025-10-13T10:00:00Z",
    "author": "teacher-jane-smith",
    "version": "1.0",
    "tags": ["writing", "argumentative", "common-core", "ccss-w-10-1"]
  },
  "criteria": [
    {
      "id": "criterion-thesis",
      "name": "Thesis Statement",
      "description": "Quality, clarity, and sophistication of the main argument",
      "weight": 25,
      "order": 0,
      "levels": [
        {
          "id": "level-exemplary",
          "score": 4,
          "label": "Exemplary",
          "description": "Thesis is clear, compelling, and demonstrates sophisticated understanding with nuanced positioning on the issue",
          "order": 0
        },
        {
          "id": "level-proficient",
          "score": 3,
          "label": "Proficient",
          "description": "Thesis is clear, appropriate, and takes a definite position on the issue",
          "order": 1
        },
        {
          "id": "level-developing",
          "score": 2,
          "label": "Developing",
          "description": "Thesis is present but may be unclear, weak, or not fully developed",
          "order": 2
        },
        {
          "id": "level-beginning",
          "score": 1,
          "label": "Beginning",
          "description": "Thesis is missing, unintelligible, or does not take a clear position",
          "order": 3
        }
      ]
    },
    {
      "id": "criterion-evidence",
      "name": "Use of Evidence",
      "description": "Quality, relevance, and integration of supporting evidence",
      "weight": 30,
      "order": 1,
      "levels": [
        {
          "id": "level-exemplary",
          "score": 4,
          "label": "Exemplary",
          "description": "Evidence is highly relevant, well-integrated, from credible sources, and thoroughly supports all claims",
          "order": 0
        },
        {
          "id": "level-proficient",
          "score": 3,
          "label": "Proficient",
          "description": "Evidence is relevant, adequately supports claims, and comes from appropriate sources",
          "order": 1
        },
        {
          "id": "level-developing",
          "score": 2,
          "label": "Developing",
          "description": "Evidence is present but may be insufficient, poorly integrated, or only partially relevant",
          "order": 2
        },
        {
          "id": "level-beginning",
          "score": 1,
          "label": "Beginning",
          "description": "Evidence is minimal, irrelevant, or missing entirely",
          "order": 3
        }
      ]
    },
    {
      "id": "criterion-organization",
      "name": "Organization",
      "description": "Logical structure, transitions, and flow of ideas",
      "weight": 20,
      "order": 2,
      "levels": [
        {
          "id": "level-exemplary",
          "score": 4,
          "label": "Exemplary",
          "description": "Organization is sophisticated with seamless transitions and a compelling logical progression",
          "order": 0
        },
        {
          "id": "level-proficient",
          "score": 3,
          "label": "Proficient",
          "description": "Organization is clear with effective transitions and logical progression of ideas",
          "order": 1
        },
        {
          "id": "level-developing",
          "score": 2,
          "label": "Developing",
          "description": "Organization is present but may be inconsistent, with weak transitions or unclear progression",
          "order": 2
        },
        {
          "id": "level-beginning",
          "score": 1,
          "label": "Beginning",
          "description": "Organization is unclear, illogical, or difficult to follow",
          "order": 3
        }
      ]
    },
    {
      "id": "criterion-mechanics",
      "name": "Grammar and Mechanics",
      "description": "Spelling, grammar, punctuation, and adherence to conventions",
      "weight": 25,
      "order": 3,
      "levels": [
        {
          "id": "level-exemplary",
          "score": 4,
          "label": "Exemplary",
          "description": "Virtually error-free with sophisticated sentence structure and excellent command of conventions",
          "order": 0
        },
        {
          "id": "level-proficient",
          "score": 3,
          "label": "Proficient",
          "description": "Few errors that do not interfere with meaning; demonstrates solid command of conventions",
          "order": 1
        },
        {
          "id": "level-developing",
          "score": 2,
          "label": "Developing",
          "description": "Multiple errors that occasionally interfere with meaning; inconsistent use of conventions",
          "order": 2
        },
        {
          "id": "level-beginning",
          "score": 1,
          "label": "Beginning",
          "description": "Numerous errors that significantly interfere with meaning and readability",
          "order": 3
        }
      ]
    }
  ],
  "scoringType": "points",
  "maxScore": 100
}
Design Rationale
Why This Structure is LLM-Friendly
Clear Hierarchy: The three-level structure (Rubric → Criteria → Levels) mirrors how educators think about rubrics
Unique Identifiers: Every criterion and level has an ID, making it easy for LLMs to understand commands like "change the description in criterion-thesis, level-proficient"
Semantic Field Names: Field names are self-documenting (description, weight, label) rather than abbreviated
Consistent Patterns: All objects follow the same pattern (id, name/label, description, etc.)
Extensible: Easy to add new fields without breaking existing structure
Validation-Friendly: Clear types and required fields make validation straightforward
Flexibility
This format supports various rubric types:
Analytic rubrics: Multiple criteria with separate scores (default)
Holistic rubrics: Change scoringType to "holistic"
Single-point rubrics: Include only proficient level descriptions
Checklists: Use binary scores (0/1) with scoringType: "checklist"
Usage in LLM Prompts
When sending to an LLM for modification:
Current rubric:
[JSON here]

User request: "Make this appropriate for 6th graders"

Return the complete modified JSON with changes applied.
The structure makes it easy for LLMs to:
Understand the complete rubric context
Make targeted edits to specific cells
Add/remove criteria or levels
Adjust scoring weights
Modify language complexity
Would you like me to create JSON Schema validation rules for this format, or examples of additional rubric types (holistic, single-point, etc.)? 