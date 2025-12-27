/**
 * Svelte 5 Rubric Store with Runes
 * Manages rubric editing state with undo/redo functionality
 */

class RubricStore {
  #rubric = $state(null);
  #history = $state([]);
  #historyIndex = $state(-1);
  #loading = $state(false);
  #error = $state(null);

  // Computed state
  get rubric() {
    return this.#rubric;
  }

  get history() {
    return this.#history;
  }

  get historyIndex() {
    return this.#historyIndex;
  }

  get canUndo() {
    return this.#historyIndex > 0;
  }

  get canRedo() {
    return this.#historyIndex < this.#history.length - 1;
  }

  get loading() {
    return this.#loading;
  }

  get error() {
    return this.#error;
  }

  /**
   * Load a rubric into the editor
   * @param {Object} rubric - The rubric data to load
   */
  loadRubric(rubric) {
    this.#rubric = JSON.parse(JSON.stringify(rubric)); // Deep copy

    // Ensure all criteria and levels have IDs
    if (this.#rubric?.criteria) {
      this.#rubric.criteria.forEach(criterion => {
        if (!criterion.id) {
          criterion.id = this.#generateId('criterion');
        }
        if (criterion.levels) {
          criterion.levels.forEach(level => {
            if (!level.id) {
              level.id = this.#generateId('level');
            }
          });
        }
      });
    }

    this.#history = [JSON.parse(JSON.stringify(this.#rubric))];
    this.#historyIndex = 0;
    this.#error = null;
  }

  /**
   * Update a cell in the rubric (criterion level description)
   * @param {string} criterionId - The criterion ID
   * @param {string} levelId - The level ID
   * @param {string} field - The field to update ('description', 'score', 'label')
   * @param {any} value - The new value
   */
  updateCell(criterionId, levelId, field, value) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    const criteria = this.#rubric.criteria || [];
    const criterion = criteria.find(c => c.id === criterionId);
    if (!criterion) return;

    const levels = criterion.levels || [];
    const level = levels.find(l => l.id === levelId);
    if (!level) return;

    level[field] = value;
    this.#updateTimestamps();
  }

  /**
   * Update criterion properties
   * @param {string} criterionId - The criterion ID
   * @param {Object} updates - The updates to apply
   */
  updateCriterion(criterionId, updates) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    const criteria = this.#rubric.criteria || [];
    const criterion = criteria.find(c => c.id === criterionId);
    if (!criterion) return;

    Object.assign(criterion, updates);
    this.#updateTimestamps();
  }

  /**
   * Add a new criterion
   * @param {Object} criterion - The criterion to add
   */
  addCriterion(criterion) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    if (!this.#rubric.criteria) {
      this.#rubric.criteria = [];
    }

    // Generate unique ID
    criterion.id = this.#generateId('criterion');

    // Ensure levels have IDs
    if (criterion.levels) {
      criterion.levels.forEach(level => {
        if (!level.id) {
          level.id = this.#generateId('level');
        }
      });
    }

    this.#rubric.criteria.push(criterion);
    this.#updateTimestamps();
  }

  /**
   * Remove a criterion
   * @param {string} criterionId - The criterion ID to remove
   */
  removeCriterion(criterionId) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    const criteria = this.#rubric.criteria || [];
    const index = criteria.findIndex(c => c.id === criterionId);
    if (index !== -1) {
      criteria.splice(index, 1);
      this.#updateTimestamps();
    }
  }

  /**
   * Add a new performance level to all criteria
   * @param {Object} levelData - The level data to add
   */
  addLevel(levelData) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    const criteria = this.#rubric.criteria || [];
    const levelId = this.#generateId('level');

    criteria.forEach(criterion => {
      if (!criterion.levels) {
        criterion.levels = [];
      }
      criterion.levels.push({
        ...levelData,
        id: levelId
      });
    });

    this.#updateTimestamps();
  }

  /**
   * Remove a performance level from all criteria
   * @param {string} levelId - The level ID to remove
   */
  removeLevel(levelId) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    const criteria = this.#rubric.criteria || [];
    criteria.forEach(criterion => {
      if (criterion.levels) {
        criterion.levels = criterion.levels.filter(level => level.id !== levelId);
      }
    });

    this.#updateTimestamps();
  }

  /**
   * Add a performance level to a specific criterion
   * @param {string} criterionId - The criterion ID to add the level to
   * @param {Object} levelData - The level data to add (score, label, description)
   */
  addLevelToCriterion(criterionId, levelData) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    const criteria = this.#rubric.criteria || [];
    const criterion = criteria.find(c => c.id === criterionId);
    if (!criterion) return;

    if (!criterion.levels) {
      criterion.levels = [];
    }

    // Generate unique ID for the level
    const levelWithId = {
      ...levelData,
      id: this.#generateId('level')
    };

    criterion.levels.push(levelWithId);
    this.#updateTimestamps();
  }

  /**
   * Update rubric metadata
   * @param {Object} metadata - The metadata updates
   */
  updateMetadata(metadata) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    if (!this.#rubric.metadata) {
      this.#rubric.metadata = {};
    }

    Object.assign(this.#rubric.metadata, metadata);
    this.#updateTimestamps();
  }

  /**
   * Update rubric basic properties
   * @param {Object} updates - The updates to apply
   */
  updateRubric(updates) {
    if (!this.#rubric) return;

    this.#saveToHistory();

    Object.assign(this.#rubric, updates);
    this.#updateTimestamps();
  }

  /**
   * Replace the entire rubric (used for AI modifications)
   * @param {Object} newRubric - The new rubric data
   */
  replaceRubric(newRubric) {
    this.#rubric = JSON.parse(JSON.stringify(newRubric)); // Deep copy
    this.#history = [JSON.parse(JSON.stringify(newRubric))];
    this.#historyIndex = 0;
    this.#error = null;
    this.#updateTimestamps();
  }

  /**
   * Toggle rubric visibility (for display purposes)
   * @param {boolean} isPublic - Whether rubric should be public
   */
  toggleVisibility(isPublic) {
    if (!this.#rubric) return;

    // This doesn't affect the rubric data itself, just a display flag
    // The actual visibility toggle happens via API call
    console.log('Toggling rubric visibility to:', isPublic);
  }

  /**
   * Undo the last change
   */
  undo() {
    if (!this.canUndo) return;

    this.#historyIndex--;
    this.#rubric = JSON.parse(JSON.stringify(this.#history[this.#historyIndex]));
    console.log('Undid change, history index:', this.#historyIndex);
  }

  /**
   * Redo a previously undone change
   */
  redo() {
    if (!this.canRedo) return;

    this.#historyIndex++;
    this.#rubric = JSON.parse(JSON.stringify(this.#history[this.#historyIndex]));
    console.log('Redid change, history index:', this.#historyIndex);
  }

  /**
   * Get changes summary between current and proposed rubric
   * @param {Object} proposedRubric - The proposed rubric to compare against
   * @returns {Object} Summary of changes
   */
  getChanges(proposedRubric) {
    if (!this.#rubric) return {};

    const changes = {
      criteria_added: [],
      criteria_modified: [],
      criteria_removed: [],
      other_changes: ''
    };

    const currentCriteria = this.#rubric.criteria || [];
    const proposedCriteria = proposedRubric.criteria || [];

    // Check for added criteria
    proposedCriteria.forEach(pc => {
      const existing = currentCriteria.find(cc => cc.id === pc.id);
      if (!existing) {
        changes.criteria_added.push(pc.name);
      } else if (existing.name !== pc.name) {
        changes.criteria_modified.push(pc.name);
      }
    });

    // Check for removed criteria
    currentCriteria.forEach(cc => {
      const existing = proposedCriteria.find(pc => pc.id === cc.id);
      if (!existing) {
        changes.criteria_removed.push(cc.name);
      }
    });

    // Check for other changes
    const otherChanges = [];
    if (this.#rubric.title !== proposedRubric.title) {
      otherChanges.push('title');
    }
    if (this.#rubric.description !== proposedRubric.description) {
      otherChanges.push('description');
    }
    if (JSON.stringify(this.#rubric.metadata) !== JSON.stringify(proposedRubric.metadata)) {
      otherChanges.push('metadata');
    }

    if (otherChanges.length > 0) {
      changes.other_changes = `Modified: ${otherChanges.join(', ')}`;
    }

    return changes;
  }

  /**
   * Reset the store to empty state
   */
  reset() {
    console.log('Resetting rubric store');
    this.#rubric = null;
    this.#history = [];
    this.#historyIndex = -1;
    this.#loading = false;
    this.#error = null;
  }

  /**
   * Set loading state
   * @param {boolean} loading - Whether operation is in progress
   */
  setLoading(loading) {
    this.#loading = loading;
  }

  /**
   * Set error state
   * @param {string|null} error - Error message or null to clear
   */
  setError(error) {
    this.#error = error;
  }

  /**
   * Validate current rubric structure
   * @returns {Object} Validation result {isValid: boolean, errors: string[]}
   */
  validate() {
    if (!this.#rubric) {
      return { isValid: false, errors: ['No rubric loaded'] };
    }

    const errors = [];

    // Required fields
    if (!this.#rubric.title?.trim()) {
      errors.push('Title is required');
    }

    if (!this.#rubric.description?.trim()) {
      errors.push('Description is required');
    }

    // Subject and grade level are optional - no validation needed

    const criteria = this.#rubric.criteria || [];
    if (criteria.length === 0) {
      errors.push('At least one criterion is required');
    }

    // Validate each criterion
    criteria.forEach((criterion, index) => {
      if (!criterion.name?.trim()) {
        errors.push(`Criterion ${index + 1}: Name is required`);
      }

      if (!criterion.description?.trim()) {
        errors.push(`Criterion ${index + 1}: Description is required`);
      }

      if (!criterion.weight || criterion.weight <= 0) {
        errors.push(`Criterion ${index + 1}: Weight must be greater than 0`);
      }

      const levels = criterion.levels || [];
      if (levels.length < 2) {
        errors.push(`Criterion ${index + 1}: At least 2 performance levels required`);
      }

      levels.forEach((level, levelIndex) => {
        if (!level.label?.trim()) {
          errors.push(`Criterion ${index + 1}, Level ${levelIndex + 1}: Label is required`);
        }

        if (!level.description?.trim()) {
          errors.push(`Criterion ${index + 1}, Level ${levelIndex + 1}: Description is required`);
        }
      });
    });

    return {
      isValid: errors.length === 0,
      errors
    };
  }

  /**
   * Get the current rubric data for saving
   * @returns {Object|null} The current rubric data
   */
  getRubricData() {
    return this.#rubric ? JSON.parse(JSON.stringify(this.#rubric)) : null;
  }

  // Private methods

  /**
   * Save current state to history
   */
  #saveToHistory() {
    if (!this.#rubric) return;

    // Remove any history after current index (for when we're not at the end)
    this.#history = this.#history.slice(0, this.#historyIndex + 1);

    // Add current state to history
    this.#history.push(JSON.parse(JSON.stringify(this.#rubric)));

    // Limit history to 50 entries
    if (this.#history.length > 50) {
      this.#history.shift();
    } else {
      this.#historyIndex++;
    }
  }

  /**
   * Update timestamps in rubric metadata
   */
  #updateTimestamps() {
    if (!this.#rubric) return;

    if (!this.#rubric.metadata) {
      this.#rubric.metadata = {};
    }

    this.#rubric.metadata.modifiedAt = new Date().toISOString();
  }

  /**
   * Generate a unique ID with prefix
   * @param {string} prefix - The prefix for the ID
   * @returns {string} Unique ID
   */
  #generateId(prefix) {
    const timestamp = Date.now();
    const random = Math.random().toString(36).substring(2, 8);
    return `${prefix}_${timestamp}_${random}`;
  }
}

// Create and export the store instance
export const rubricStore = new RubricStore();
