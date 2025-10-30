/**
 * Template Store
 * 
 * Svelte store for managing prompt templates state.
 * Handles template lists, pagination, and selection.
 */

import { writable, derived, get } from 'svelte/store';
import * as templateService from '../services/templateService';

// Store for user's own templates
export const userTemplates = writable([]);
export const userTemplatesTotal = writable(0);
export const userTemplatesPage = writable(1);
export const userTemplatesLimit = writable(20);
export const userTemplatesLoading = writable(false);

// Store for shared templates
export const sharedTemplates = writable([]);
export const sharedTemplatesTotal = writable(0);
export const sharedTemplatesPage = writable(1);
export const sharedTemplatesLimit = writable(20);
export const sharedTemplatesLoading = writable(false);

// Current selected tab ('my' or 'shared')
export const currentTab = writable('my');

// Currently selected templates (for bulk operations like export)
export const selectedTemplateIds = writable([]);

// Modal state for template selection
export const templateSelectModalOpen = writable(false);
export const templateSelectCallback = writable(null);

// Error state
export const templateError = writable(null);

/**
 * Load user's templates
 */
export async function loadUserTemplates() {
    try {
        userTemplatesLoading.set(true);
        templateError.set(null);
        
        const page = get(userTemplatesPage);
        const limit = get(userTemplatesLimit);
        const offset = (page - 1) * limit;
        
        const result = await templateService.listUserTemplates(limit, offset);
        
        userTemplates.set(result.templates);
        userTemplatesTotal.set(result.total);
        
    } catch (error) {
        console.error('Error loading user templates:', error);
        templateError.set(error.message || 'Failed to load templates');
    } finally {
        userTemplatesLoading.set(false);
    }
}

/**
 * Load shared templates
 */
export async function loadSharedTemplates() {
    try {
        sharedTemplatesLoading.set(true);
        templateError.set(null);
        
        const page = get(sharedTemplatesPage);
        const limit = get(sharedTemplatesLimit);
        const offset = (page - 1) * limit;
        
        const result = await templateService.listSharedTemplates(limit, offset);
        
        sharedTemplates.set(result.templates);
        sharedTemplatesTotal.set(result.total);
        
    } catch (error) {
        console.error('Error loading shared templates:', error);
        templateError.set(error.message || 'Failed to load shared templates');
    } finally {
        sharedTemplatesLoading.set(false);
    }
}

/**
 * Reload templates based on current tab
 */
export async function reloadTemplates() {
    const tab = get(currentTab);
    if (tab === 'my') {
        await loadUserTemplates();
    } else {
        await loadSharedTemplates();
    }
}

/**
 * Create a new template
 */
export async function createTemplate(templateData) {
    try {
        templateError.set(null);
        const newTemplate = await templateService.createTemplate(templateData);
        
        // Reload user templates to show the new one
        await loadUserTemplates();
        
        return newTemplate;
    } catch (error) {
        console.error('Error creating template:', error);
        templateError.set(error.response?.data?.detail || error.message || 'Failed to create template');
        throw error;
    }
}

/**
 * Update a template
 */
export async function updateTemplate(templateId, updates) {
    try {
        templateError.set(null);
        const updatedTemplate = await templateService.updateTemplate(templateId, updates);
        
        // Update in the appropriate list
        const tab = get(currentTab);
        if (tab === 'my') {
            userTemplates.update(templates => 
                templates.map(t => t.id === templateId ? updatedTemplate : t)
            );
        } else {
            sharedTemplates.update(templates => 
                templates.map(t => t.id === templateId ? updatedTemplate : t)
            );
        }
        
        return updatedTemplate;
    } catch (error) {
        console.error('Error updating template:', error);
        templateError.set(error.response?.data?.detail || error.message || 'Failed to update template');
        throw error;
    }
}

/**
 * Delete a template
 */
export async function deleteTemplate(templateId) {
    try {
        templateError.set(null);
        await templateService.deleteTemplate(templateId);
        
        // Remove from the appropriate list
        const tab = get(currentTab);
        if (tab === 'my') {
            userTemplates.update(templates => templates.filter(t => t.id !== templateId));
            userTemplatesTotal.update(total => total - 1);
        } else {
            sharedTemplates.update(templates => templates.filter(t => t.id !== templateId));
            sharedTemplatesTotal.update(total => total - 1);
        }
    } catch (error) {
        console.error('Error deleting template:', error);
        templateError.set(error.response?.data?.detail || error.message || 'Failed to delete template');
        throw error;
    }
}

/**
 * Duplicate a template
 */
export async function duplicateTemplate(templateId, newName = null) {
    try {
        templateError.set(null);
        const newTemplate = await templateService.duplicateTemplate(templateId, newName);
        
        // Reload user templates to show the duplicate
        await loadUserTemplates();
        
        return newTemplate;
    } catch (error) {
        console.error('Error duplicating template:', error);
        templateError.set(error.response?.data?.detail || error.message || 'Failed to duplicate template');
        throw error;
    }
}

/**
 * Toggle template sharing
 */
export async function toggleSharing(templateId, isShared) {
    try {
        templateError.set(null);
        const updatedTemplate = await templateService.toggleTemplateSharing(templateId, isShared);
        
        // Update in user templates list
        userTemplates.update(templates => 
            templates.map(t => t.id === templateId ? updatedTemplate : t)
        );
        
        return updatedTemplate;
    } catch (error) {
        console.error('Error toggling sharing:', error);
        templateError.set(error.response?.data?.detail || error.message || 'Failed to toggle sharing');
        throw error;
    }
}

/**
 * Export selected templates
 */
export async function exportSelected() {
    try {
        templateError.set(null);
        const ids = get(selectedTemplateIds);
        
        if (ids.length === 0) {
            throw new Error('No templates selected');
        }
        
        await templateService.downloadTemplatesExport(ids);
        
        // Clear selection after export
        selectedTemplateIds.set([]);
    } catch (error) {
        console.error('Error exporting templates:', error);
        templateError.set(error.message || 'Failed to export templates');
        throw error;
    }
}

/**
 * Toggle template selection (for bulk operations)
 */
export function toggleTemplateSelection(templateId) {
    selectedTemplateIds.update(ids => {
        if (ids.includes(templateId)) {
            return ids.filter(id => id !== templateId);
        } else {
            return [...ids, templateId];
        }
    });
}

/**
 * Select all templates in current view
 */
export function selectAllTemplates() {
    const tab = get(currentTab);
    const templates = tab === 'my' ? get(userTemplates) : get(sharedTemplates);
    const ids = templates.map(t => t.id);
    selectedTemplateIds.set(ids);
}

/**
 * Clear all selections
 */
export function clearSelection() {
    selectedTemplateIds.set([]);
}

/**
 * Open template selection modal
 * @param {Function} callback - Function to call with selected template
 */
export function openTemplateSelectModal(callback) {
    templateSelectCallback.set(callback);
    templateSelectModalOpen.set(true);
}

/**
 * Close template selection modal
 */
export function closeTemplateSelectModal() {
    templateSelectModalOpen.set(false);
    templateSelectCallback.set(null);
}

/**
 * Select a template from the modal
 */
export function selectTemplateFromModal(template) {
    const callback = get(templateSelectCallback);
    if (callback) {
        callback(template);
    }
    closeTemplateSelectModal();
}

/**
 * Set current tab and reload
 */
export async function switchTab(tab) {
    currentTab.set(tab);
    clearSelection();
    await reloadTemplates();
}

// Derived store for total pages
export const userTemplatesTotalPages = derived(
    [userTemplatesTotal, userTemplatesLimit],
    ([$total, $limit]) => Math.ceil($total / $limit) || 1
);

export const sharedTemplatesTotalPages = derived(
    [sharedTemplatesTotal, sharedTemplatesLimit],
    ([$total, $limit]) => Math.ceil($total / $limit) || 1
);

// Derived store for current templates based on tab
export const currentTemplates = derived(
    [currentTab, userTemplates, sharedTemplates],
    ([$tab, $user, $shared]) => $tab === 'my' ? $user : $shared
);

// Derived store for current loading state
export const currentLoading = derived(
    [currentTab, userTemplatesLoading, sharedTemplatesLoading],
    ([$tab, $userLoading, $sharedLoading]) => $tab === 'my' ? $userLoading : $sharedLoading
);

// Derived store for current total
export const currentTotal = derived(
    [currentTab, userTemplatesTotal, sharedTemplatesTotal],
    ([$tab, $userTotal, $sharedTotal]) => $tab === 'my' ? $userTotal : $sharedTotal
);

/**
 * Load all user templates (for client-side filtering)
 */
export async function loadAllUserTemplates() {
    try {
        userTemplatesLoading.set(true);
        templateError.set(null);
        
        // Fetch with high limit for client-side processing
        const result = await templateService.listUserTemplates(1000, 0);
        
        userTemplates.set(result.templates);
        userTemplatesTotal.set(result.total);
        
    } catch (error) {
        console.error('Error loading user templates:', error);
        templateError.set(error.message || 'Failed to load templates');
    } finally {
        userTemplatesLoading.set(false);
    }
}

/**
 * Load all shared templates (for client-side filtering)
 */
export async function loadAllSharedTemplates() {
    try {
        sharedTemplatesLoading.set(true);
        templateError.set(null);
        
        // Fetch with high limit for client-side processing
        const result = await templateService.listSharedTemplates(1000, 0);
        
        sharedTemplates.set(result.templates);
        sharedTemplatesTotal.set(result.total);
        
    } catch (error) {
        console.error('Error loading shared templates:', error);
        templateError.set(error.message || 'Failed to load shared templates');
    } finally {
        sharedTemplatesLoading.set(false);
    }
}

