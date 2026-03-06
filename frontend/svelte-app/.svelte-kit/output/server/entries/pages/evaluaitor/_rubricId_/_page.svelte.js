import { b as attr, e as ensure_array_like, a as attr_class, s as stringify, c as store_get, u as unsubscribe_stores, h as head } from "../../../../chunks/index2.js";
import { p as page } from "../../../../chunks/stores.js";
import "@sveltejs/kit/internal";
import "../../../../chunks/exports.js";
import "../../../../chunks/utils.js";
import "clsx";
import "@sveltejs/kit/internal/server";
import "../../../../chunks/state.svelte.js";
import { C as ConfirmationModal } from "../../../../chunks/ConfirmationModal.js";
import { e as escape_html } from "../../../../chunks/context.js";
import "../../../../chunks/i18n.js";
import { $ as $locale, a as $format } from "../../../../chunks/runtime.js";
async function fetchRubric(rubricId) {
  {
    throw new Error("fetchRubric called outside browser context");
  }
}
class RubricStore {
  #rubric = null;
  #history = [];
  #historyIndex = -1;
  #loading = false;
  #error = null;
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
    this.#rubric = JSON.parse(JSON.stringify(rubric));
    if (this.#rubric?.criteria) {
      this.#rubric.criteria.forEach((criterion) => {
        if (!criterion.id) {
          criterion.id = this.#generateId("criterion");
        }
        if (criterion.levels) {
          criterion.levels.forEach((level) => {
            if (!level.id) {
              level.id = this.#generateId("level");
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
    const criterion = criteria.find((c) => c.id === criterionId);
    if (!criterion) return;
    const levels = criterion.levels || [];
    const level = levels.find((l) => l.id === levelId);
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
    const criterion = criteria.find((c) => c.id === criterionId);
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
    criterion.id = this.#generateId("criterion");
    if (criterion.levels) {
      criterion.levels.forEach((level) => {
        if (!level.id) {
          level.id = this.#generateId("level");
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
    const index = criteria.findIndex((c) => c.id === criterionId);
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
    const levelId = this.#generateId("level");
    criteria.forEach((criterion) => {
      if (!criterion.levels) {
        criterion.levels = [];
      }
      criterion.levels.push({ ...levelData, id: levelId });
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
    criteria.forEach((criterion) => {
      if (criterion.levels) {
        criterion.levels = criterion.levels.filter((level) => level.id !== levelId);
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
    const criterion = criteria.find((c) => c.id === criterionId);
    if (!criterion) return;
    if (!criterion.levels) {
      criterion.levels = [];
    }
    const levelWithId = { ...levelData, id: this.#generateId("level") };
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
    this.#rubric = JSON.parse(JSON.stringify(newRubric));
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
    console.log("Toggling rubric visibility to:", isPublic);
  }
  /**
   * Undo the last change
   */
  undo() {
    if (!this.canUndo) return;
    this.#historyIndex--;
    this.#rubric = JSON.parse(JSON.stringify(this.#history[this.#historyIndex]));
    console.log("Undid change, history index:", this.#historyIndex);
  }
  /**
   * Redo a previously undone change
   */
  redo() {
    if (!this.canRedo) return;
    this.#historyIndex++;
    this.#rubric = JSON.parse(JSON.stringify(this.#history[this.#historyIndex]));
    console.log("Redid change, history index:", this.#historyIndex);
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
      other_changes: ""
    };
    const currentCriteria = this.#rubric.criteria || [];
    const proposedCriteria = proposedRubric.criteria || [];
    proposedCriteria.forEach((pc) => {
      const existing = currentCriteria.find((cc) => cc.id === pc.id);
      if (!existing) {
        changes.criteria_added.push(pc.name);
      } else if (existing.name !== pc.name) {
        changes.criteria_modified.push(pc.name);
      }
    });
    currentCriteria.forEach((cc) => {
      const existing = proposedCriteria.find((pc) => pc.id === cc.id);
      if (!existing) {
        changes.criteria_removed.push(cc.name);
      }
    });
    const otherChanges = [];
    if (this.#rubric.title !== proposedRubric.title) {
      otherChanges.push("title");
    }
    if (this.#rubric.description !== proposedRubric.description) {
      otherChanges.push("description");
    }
    if (JSON.stringify(this.#rubric.metadata) !== JSON.stringify(proposedRubric.metadata)) {
      otherChanges.push("metadata");
    }
    if (otherChanges.length > 0) {
      changes.other_changes = `Modified: ${otherChanges.join(", ")}`;
    }
    return changes;
  }
  /**
   * Reset the store to empty state
   */
  reset() {
    console.log("Resetting rubric store");
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
      return { isValid: false, errors: ["No rubric loaded"] };
    }
    const errors = [];
    if (!this.#rubric.title?.trim()) {
      errors.push("Title is required");
    }
    if (!this.#rubric.description?.trim()) {
      errors.push("Description is required");
    }
    const criteria = this.#rubric.criteria || [];
    if (criteria.length === 0) {
      errors.push("At least one criterion is required");
    }
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
    return { isValid: errors.length === 0, errors };
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
    this.#history = this.#history.slice(0, this.#historyIndex + 1);
    this.#history.push(JSON.parse(JSON.stringify(this.#rubric)));
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
    this.#rubric.metadata.modifiedAt = (/* @__PURE__ */ new Date()).toISOString();
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
const rubricStore = new RubricStore();
function RubricTable($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let { isEditMode = false } = $$props;
    let editingCell = null;
    let showDeleteCriterionModal = false;
    let criterionToDelete = null;
    let showDeleteLevelModal = false;
    let levelToDelete = null;
    function confirmRemoveCriterion() {
      if (criterionToDelete) {
        rubricStore.removeCriterion(criterionToDelete);
      }
      showDeleteCriterionModal = false;
      criterionToDelete = null;
    }
    function cancelRemoveCriterion() {
      showDeleteCriterionModal = false;
      criterionToDelete = null;
    }
    function confirmRemoveLevel() {
      if (levelToDelete) {
        rubricStore.removeLevel(levelToDelete);
      }
      showDeleteLevelModal = false;
      levelToDelete = null;
    }
    function cancelRemoveLevel() {
      showDeleteLevelModal = false;
      levelToDelete = null;
    }
    function getCommonLevels() {
      if (!rubricStore.rubric?.criteria?.length) return [];
      const firstCriterion = rubricStore.rubric.criteria[0];
      return firstCriterion.levels || [];
    }
    function getCriterionLevel(criterion, targetScore) {
      return criterion.levels?.find((level) => level.score === targetScore) || null;
    }
    function getTotalWeight() {
      if (!rubricStore.rubric?.criteria?.length) return 0;
      return rubricStore.rubric.criteria.reduce(
        (sum, criterion) => {
          const weight = parseFloat(criterion.weight) || 0;
          return sum + weight;
        },
        0
      );
    }
    let totalWeight = getTotalWeight();
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      $$renderer3.push(`<div class="bg-white shadow rounded-lg"><div class="px-6 py-4 border-b border-gray-200"><div class="flex justify-between items-center"><h3 class="text-lg font-medium text-gray-900">Rubric Criteria</h3> <div class="flex space-x-2"><button${attr("disabled", !isEditMode, true)} class="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"><svg class="-ml-1 mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg> Add Criterion</button> <button${attr("disabled", !isEditMode, true)} class="inline-flex items-center px-3 py-1 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"><svg class="-ml-1 mr-1 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg> Add Level</button></div></div></div> <div class="overflow-x-auto"><table class="min-w-full divide-y divide-gray-200"><thead class="bg-gray-50"><tr><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Criterion</th><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Weight</th><!--[-->`);
      const each_array = ensure_array_like(getCommonLevels());
      for (let $$index = 0, $$length = each_array.length; $$index < $$length; $$index++) {
        let levelTemplate = each_array[$$index];
        $$renderer3.push(`<th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"><div class="flex items-center justify-between"><span>${escape_html(levelTemplate.label || "Level")} (${escape_html(levelTemplate.score || "?")})</span> `);
        if (getCommonLevels().length > 2) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<button${attr("disabled", !isEditMode, true)} class="ml-2 text-red-400 hover:text-red-600 disabled:opacity-50 disabled:cursor-not-allowed" title="Remove this level"><svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></div></th>`);
      }
      $$renderer3.push(`<!--]--><th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th></tr></thead><tbody class="bg-white divide-y divide-gray-200"><!--[-->`);
      const each_array_1 = ensure_array_like(rubricStore.rubric?.criteria || []);
      for (let criterionIndex = 0, $$length = each_array_1.length; criterionIndex < $$length; criterionIndex++) {
        let criterion = each_array_1[criterionIndex];
        $$renderer3.push(`<tr class="hover:bg-gray-50"><td class="px-6 py-4"><div class="space-y-2">`);
        if (editingCell?.criterionId === criterion.id && editingCell?.field === "name") ;
        else {
          $$renderer3.push("<!--[!-->");
          $$renderer3.push(`<div role="button" tabindex="0"${attr_class(`${stringify(isEditMode ? "cursor-pointer hover:bg-blue-50 hover:border-blue-200 border border-transparent" : "cursor-default")} p-1 rounded text-sm font-medium text-gray-900`)}>${escape_html(criterion.name || "Unnamed Criterion")}</div>`);
        }
        $$renderer3.push(`<!--]--> `);
        if (editingCell?.criterionId === criterion.id && editingCell?.field === "description") ;
        else {
          $$renderer3.push("<!--[!-->");
          $$renderer3.push(`<div role="button" tabindex="0"${attr_class(`${stringify(isEditMode ? "cursor-pointer hover:bg-blue-50 hover:border-blue-200 border border-transparent" : "cursor-default")} p-1 rounded text-sm text-gray-600`)}>${escape_html(criterion.description || "No description")}</div>`);
        }
        $$renderer3.push(`<!--]--></div></td><td class="px-6 py-4 whitespace-nowrap">`);
        if (editingCell?.criterionId === criterion.id && editingCell?.field === "weight") ;
        else {
          $$renderer3.push("<!--[!-->");
          $$renderer3.push(`<div role="button" tabindex="0"${attr_class(`${stringify(isEditMode ? "cursor-pointer hover:bg-blue-50 hover:border-blue-200 border border-transparent" : "cursor-default")} p-1 rounded text-sm text-center font-medium`)}>${escape_html(criterion.weight || 0)}%</div>`);
        }
        $$renderer3.push(`<!--]--></td><!--[-->`);
        const each_array_2 = ensure_array_like(getCommonLevels());
        for (let $$index_1 = 0, $$length2 = each_array_2.length; $$index_1 < $$length2; $$index_1++) {
          let levelTemplate = each_array_2[$$index_1];
          const level = getCriterionLevel(criterion, levelTemplate.score);
          $$renderer3.push(`<td class="px-6 py-4">`);
          if (editingCell?.criterionId === criterion.id && editingCell?.levelId === level?.id && editingCell?.field === "description") ;
          else {
            $$renderer3.push("<!--[!-->");
            $$renderer3.push(`<div role="button"${attr("tabindex", isEditMode ? 0 : -1)}${attr_class(`${stringify(isEditMode ? "cursor-pointer hover:bg-blue-50 hover:border-blue-200 border border-transparent" : "cursor-default")} p-2 rounded text-sm text-gray-700 min-h-[60px]`)}>${escape_html(level?.description || "No description")}</div>`);
          }
          $$renderer3.push(`<!--]--></td>`);
        }
        $$renderer3.push(`<!--]--><td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">`);
        if (rubricStore.rubric?.criteria?.length > 1) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<button${attr("disabled", !isEditMode, true)} class="text-red-600 hover:text-red-900 disabled:opacity-50 disabled:cursor-not-allowed" title="Remove criterion"><svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg></button>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></td></tr>`);
      }
      $$renderer3.push(`<!--]-->`);
      if (rubricStore.rubric?.criteria?.length) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<tr class="bg-gray-50 border-t-2 border-gray-300 font-semibold"><td class="px-6 py-4 text-sm text-gray-900" colspan="2">Total</td><td class="px-6 py-4 text-sm text-center"><div class="flex items-center justify-center"><span${attr_class(totalWeight === 100 ? "text-green-600" : totalWeight > 100 ? "text-red-600" : "text-yellow-600")}>${escape_html(totalWeight.toFixed(1))}%</span> `);
        if (totalWeight === 100) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<svg class="ml-2 h-5 w-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`);
        } else {
          $$renderer3.push("<!--[!-->");
          if (totalWeight > 100) {
            $$renderer3.push("<!--[-->");
            $$renderer3.push(`<svg class="ml-2 h-5 w-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>`);
          } else {
            $$renderer3.push("<!--[!-->");
            $$renderer3.push(`<svg class="ml-2 h-5 w-5 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>`);
          }
          $$renderer3.push(`<!--]-->`);
        }
        $$renderer3.push(`<!--]--></div> `);
        if (totalWeight !== 100) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<div${attr_class(`text-xs ${stringify(totalWeight > 100 ? "text-red-500" : "text-yellow-500")} mt-1`)}>${escape_html(totalWeight > 100 ? "Exceeds 100%" : "Should equal 100%")}</div>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></td><!--[-->`);
        const each_array_3 = ensure_array_like(getCommonLevels());
        for (let $$index_3 = 0, $$length = each_array_3.length; $$index_3 < $$length; $$index_3++) {
          each_array_3[$$index_3];
          $$renderer3.push(`<td class="px-6 py-4"></td>`);
        }
        $$renderer3.push(`<!--]-->`);
        if (isEditMode) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<td class="px-6 py-4"></td>`);
        } else {
          $$renderer3.push("<!--[!-->");
        }
        $$renderer3.push(`<!--]--></tr>`);
      } else {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--></tbody></table></div> `);
      if (rubricStore.error) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="px-6 py-4 bg-red-50 border-t border-red-200"><div class="text-sm text-red-700">${escape_html(rubricStore.error)}</div></div>`);
      } else {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      if (!rubricStore.rubric?.criteria?.length) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="px-6 py-12 text-center"><svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg> <h3 class="mt-2 text-sm font-medium text-gray-900">No criteria yet</h3> <p class="mt-1 text-sm text-gray-500">Get started by adding your first criterion.</p> <div class="mt-6"><button class="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"><svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg> Add Criterion</button></div></div>`);
      } else {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--></div> `);
      ConfirmationModal($$renderer3, {
        title: "Remove Criterion",
        message: "Are you sure you want to remove this criterion? This will delete all associated performance level descriptions.",
        confirmText: "Remove",
        variant: "danger",
        onconfirm: confirmRemoveCriterion,
        oncancel: cancelRemoveCriterion,
        get isOpen() {
          return showDeleteCriterionModal;
        },
        set isOpen($$value) {
          showDeleteCriterionModal = $$value;
          $$settled = false;
        }
      });
      $$renderer3.push(`<!----> `);
      ConfirmationModal($$renderer3, {
        title: "Remove Performance Level",
        message: "Are you sure you want to remove this performance level from all criteria? This action cannot be undone.",
        confirmText: "Remove",
        variant: "danger",
        onconfirm: confirmRemoveLevel,
        oncancel: cancelRemoveLevel,
        get isOpen() {
          return showDeleteLevelModal;
        },
        set isOpen($$value) {
          showDeleteLevelModal = $$value;
          $$settled = false;
        }
      });
      $$renderer3.push(`<!---->`);
    }
    do {
      $$settled = true;
      $$inner_renderer = $$renderer2.copy();
      $$render_inner($$inner_renderer);
    } while (!$$settled);
    $$renderer2.subsume($$inner_renderer);
  });
}
function RubricMetadataForm($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let { isEditMode = false } = $$props;
    let title = "";
    let description = "";
    let scoringType = "points";
    let maxScore = 10;
    let subject = "";
    let gradeLevel = "";
    function handleScoringTypeChange() {
      rubricStore.updateRubric({ scoringType });
    }
    $$renderer2.push(`<div class="bg-white shadow rounded-lg"><div class="px-6 py-4 border-b border-gray-200"><h3 class="text-lg font-medium text-gray-900">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.heading", { default: "Rubric Information" }) : "Rubric Information")}</h3></div> <div class="px-8 py-6 space-y-6"><div class="space-y-4"><div><label for="title" class="block text-sm font-medium text-gray-700">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.form.title", { default: "Title" }) : "Title")} <span class="text-red-500">*</span></label> <input id="title" type="text"${attr("value", title)}${attr("placeholder", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.titlePlaceholder", { default: "Enter rubric title" }) : "Enter rubric title")} class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 text-lg"${attr("readonly", !isEditMode, true)} required/></div> <div><label for="description" class="block text-sm font-medium text-gray-700">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.form.descriptionLabel", { default: "Description" }) : "Description")} <span class="text-red-500">*</span></label> <textarea id="description" rows="3"${attr("placeholder", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.descriptionPlaceholder", { default: "Describe the purpose and context of this rubric" }) : "Describe the purpose and context of this rubric")} class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"${attr("readonly", !isEditMode, true)} required>`);
    const $$body = escape_html(description);
    if ($$body) {
      $$renderer2.push(`${$$body}`);
    }
    $$renderer2.push(`</textarea></div></div> <div class="pt-4 border-t border-gray-200"><h4 class="text-md font-medium text-gray-900 mb-4">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.scoringConfig", { default: "Scoring Configuration" }) : "Scoring Configuration")}</h4> <div class="grid grid-cols-1 md:grid-cols-2 gap-6"><div><label for="scoringType" class="block text-sm font-medium text-gray-700">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.form.scoringType", { default: "Scoring Type" }) : "Scoring Type")} <span class="text-red-500">*</span></label> `);
    if (isEditMode) {
      $$renderer2.push("<!--[-->");
      $$renderer2.select(
        {
          id: "scoringType",
          value: scoringType,
          onchange: handleScoringTypeChange,
          class: "mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"
        },
        ($$renderer3) => {
          $$renderer3.option({ value: "points" }, ($$renderer4) => {
            $$renderer4.push(`${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.points", { default: "Points" }) : "Points")}`);
          });
          $$renderer3.option({ value: "percentage" }, ($$renderer4) => {
            $$renderer4.push(`${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.percentage", { default: "Percentage" }) : "Percentage")}`);
          });
          $$renderer3.option({ value: "holistic" }, ($$renderer4) => {
            $$renderer4.push(`${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.holistic", { default: "Holistic" }) : "Holistic")}`);
          });
          $$renderer3.option({ value: "single-point" }, ($$renderer4) => {
            $$renderer4.push(`${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.singlePoint", { default: "Single Point" }) : "Single Point")}`);
          });
          $$renderer3.option({ value: "checklist" }, ($$renderer4) => {
            $$renderer4.push(`${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.checklist", { default: "Checklist" }) : "Checklist")}`);
          });
        }
      );
    } else {
      $$renderer2.push("<!--[!-->");
      $$renderer2.push(`<div class="mt-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-sm text-gray-900">${escape_html(scoringType)}</div>`);
    }
    $$renderer2.push(`<!--]--></div> <div><label for="maxScore" class="block text-sm font-medium text-gray-700">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.form.maxScore", { default: "Maximum Score" }) : "Maximum Score")} <span class="text-red-500">*</span></label> `);
    if (isEditMode) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<input id="maxScore" type="number" min="1" max="1000"${attr("value", maxScore)} placeholder="10" class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"/>`);
    } else {
      $$renderer2.push("<!--[!-->");
      $$renderer2.push(`<div class="mt-1 px-3 py-2 bg-gray-50 border border-gray-300 rounded-md text-sm text-gray-900">${escape_html(maxScore)}</div>`);
    }
    $$renderer2.push(`<!--]--></div></div></div> <div class="pt-4 border-t border-gray-200"><h4 class="text-md font-medium text-gray-900 mb-2">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.optionalInfo", { default: "Optional Information" }) : "Optional Information")}</h4> <p class="text-sm text-gray-500 mb-4">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.optionalHint", {
      default: "These fields are completely optional. Leave blank if not applicable to your rubric."
    }) : "These fields are completely optional. Leave blank if not applicable to your rubric.")}</p> <div class="grid grid-cols-1 md:grid-cols-2 gap-6"><div><label for="subject" class="block text-sm font-medium text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.form.subject", { default: "Subject" }) : "Subject")} <span class="text-xs text-gray-400">(${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.optional", { default: "optional" }) : "optional")})</span></label> <input id="subject" type="text"${attr("value", subject)}${attr("placeholder", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.form.subjectPlaceholder", { default: "e.g., Mathematics, English, Science" }) : "e.g., Mathematics, English, Science")} class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"${attr("readonly", !isEditMode, true)}/></div> <div><label for="gradeLevel" class="block text-sm font-medium text-gray-500">${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.form.gradeLevel", { default: "Grade Level" }) : "Grade Level")} <span class="text-xs text-gray-400">(${escape_html(store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.optional", { default: "optional" }) : "optional")})</span></label> <input id="gradeLevel" type="text"${attr("value", gradeLevel)}${attr("placeholder", store_get($$store_subs ??= {}, "$locale", $locale) ? store_get($$store_subs ??= {}, "$_", $format)("rubrics.metadataForm.gradeLevelPlaceholder", { default: "e.g., 6-8, 9-12, K-2, Adult Education" }) : "e.g., 6-8, 9-12, K-2, Adult Education")} class="mt-1 block w-full border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500"${attr("readonly", !isEditMode, true)}/></div></div></div> `);
    if (rubricStore.error) {
      $$renderer2.push("<!--[-->");
      $$renderer2.push(`<div class="bg-red-50 border border-red-200 rounded-md p-4"><div class="text-sm text-red-700">${escape_html(rubricStore.error)}</div></div>`);
    } else {
      $$renderer2.push("<!--[!-->");
    }
    $$renderer2.push(`<!--]--></div></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
function RubricEditor($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    let { rubricId } = $$props;
    let loading = true;
    let error = null;
    let isNewRubric = false;
    let isEditMode = false;
    let showDiscardModal = false;
    function confirmDiscard() {
      loadRubric();
      isEditMode = false;
      showDiscardModal = false;
    }
    function cancelDiscard() {
      showDiscardModal = false;
    }
    async function loadRubric() {
      if (!rubricId) {
        error = "No rubric ID provided";
        loading = false;
        return;
      }
      try {
        loading = true;
        const rubricData = await fetchRubric(rubricId);
        rubricStore.loadRubric(rubricData.rubric_data);
      } catch (err) {
        error = err.message || "Failed to load rubric";
        console.error("Error loading rubric:", err);
      } finally {
        loading = false;
      }
    }
    let $$settled = true;
    let $$inner_renderer;
    function $$render_inner($$renderer3) {
      $$renderer3.push(`<div class="min-h-screen bg-gray-50">`);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> `);
      {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--> <div class="bg-white shadow"><div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8"><div class="py-6"><div class="flex items-center justify-between mb-4"><button class="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100" aria-label="Go back"><svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"></path></svg></button> <div class="flex items-center space-x-3">`);
      if (isEditMode || isNewRubric) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<span class="inline-flex items-center px-3 py-1 rounded-md text-sm font-medium bg-blue-100 text-blue-800 border border-blue-200"><svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg> Editing Rubric</span> <button${attr("disabled", !rubricStore.canUndo, true)} class="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed" title="Undo"><svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h10a8 8 0 018 8v2M3 10l6 6m-6-6l6-6"></path></svg></button> <button${attr("disabled", !rubricStore.canRedo, true)} class="p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed" title="Redo"><svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 10H11a8 8 0 00-8 8v2M21 10l-6 6m6-6l-6-6"></path></svg></button> `);
        {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<button${attr("disabled", loading, true)} class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"><svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg> Cancel</button>`);
        }
        $$renderer3.push(`<!--]--> <button${attr("disabled", loading, true)} class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed">`);
        {
          $$renderer3.push("<!--[!-->");
          $$renderer3.push(`<svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>${escape_html("Update Rubric")}`);
        }
        $$renderer3.push(`<!--]--></button> `);
        {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<button${attr("disabled", loading, true)} class="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed">Save as New Version</button>`);
        }
        $$renderer3.push(`<!--]-->`);
      } else {
        $$renderer3.push("<!--[!-->");
        $$renderer3.push(`<span class="inline-flex items-center px-3 py-1 rounded-md text-sm font-medium bg-gray-100 text-gray-700 border border-gray-300"><svg class="-ml-0.5 mr-2 h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"></path><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"></path></svg> View Only</span> <button class="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-blue-600 hover:bg-blue-700"><svg class="-ml-1 mr-2 h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"></path></svg> Edit</button>`);
      }
      $$renderer3.push(`<!--]--></div></div> <h1 class="text-3xl font-bold text-gray-900 mb-3">${escape_html(rubricStore.rubric?.title || "Loading...")}</h1> `);
      if (rubricStore.rubric?.description) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="bg-gray-50 border border-gray-200 rounded-md p-4"><p class="text-sm text-gray-700 leading-relaxed">${escape_html(rubricStore.rubric.description)}</p></div>`);
      } else {
        $$renderer3.push("<!--[!-->");
      }
      $$renderer3.push(`<!--]--></div></div></div> <div class="max-w-none mx-auto py-6 px-6 lg:px-12">`);
      if (loading) {
        $$renderer3.push("<!--[-->");
        $$renderer3.push(`<div class="text-center py-12"><div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div> <p class="mt-4 text-lg text-gray-600">Loading rubric...</p></div>`);
      } else {
        $$renderer3.push("<!--[!-->");
        if (error) {
          $$renderer3.push("<!--[-->");
          $$renderer3.push(`<div class="bg-red-50 border border-red-200 rounded-md p-4 mb-6"><div class="flex"><div class="flex-shrink-0"><svg class="h-5 w-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"></path></svg></div> <div class="ml-3"><h3 class="text-sm font-medium text-red-800">Error</h3> <div class="mt-2 text-sm text-red-700">${escape_html(error)}</div> <div class="mt-4"><button class="bg-red-100 px-3 py-2 rounded-md text-sm font-medium text-red-800 hover:bg-red-200">Back to Rubrics</button></div></div></div></div>`);
        } else {
          $$renderer3.push("<!--[!-->");
          $$renderer3.push(`<div${attr_class(`grid grid-cols-1 ${stringify("")} gap-8`)}><div${attr_class(`${stringify("")} space-y-8`)}>`);
          RubricMetadataForm($$renderer3, { isEditMode });
          $$renderer3.push(`<!----> `);
          RubricTable($$renderer3, { isEditMode });
          $$renderer3.push(`<!----></div> `);
          {
            $$renderer3.push("<!--[!-->");
          }
          $$renderer3.push(`<!--]--></div>`);
        }
        $$renderer3.push(`<!--]-->`);
      }
      $$renderer3.push(`<!--]--></div></div> `);
      ConfirmationModal($$renderer3, {
        title: "Discard Changes",
        message: "Are you sure you want to discard all changes and exit edit mode? Any unsaved changes will be lost.",
        confirmText: "Discard",
        variant: "warning",
        onconfirm: confirmDiscard,
        oncancel: cancelDiscard,
        get isOpen() {
          return showDiscardModal;
        },
        set isOpen($$value) {
          showDiscardModal = $$value;
          $$settled = false;
        }
      });
      $$renderer3.push(`<!---->`);
    }
    do {
      $$settled = true;
      $$inner_renderer = $$renderer2.copy();
      $$render_inner($$inner_renderer);
    } while (!$$settled);
    $$renderer2.subsume($$inner_renderer);
  });
}
function _page($$renderer, $$props) {
  $$renderer.component(($$renderer2) => {
    var $$store_subs;
    let rubricId = store_get($$store_subs ??= {}, "$page", page).params.rubricId;
    head("h7xoj6", $$renderer2, ($$renderer3) => {
      $$renderer3.title(($$renderer4) => {
        $$renderer4.push(`<title>Rubric Editor - Evaluaitor</title>`);
      });
    });
    $$renderer2.push(`<div class="min-h-screen bg-gray-50"><div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">`);
    RubricEditor($$renderer2, { rubricId });
    $$renderer2.push(`<!----></div></div>`);
    if ($$store_subs) unsubscribe_stores($$store_subs);
  });
}
export {
  _page as default
};
