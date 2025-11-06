/**
 * Name Sanitization Utility for Frontend
 * 
 * Mirrors the backend sanitization logic to provide real-time preview
 * of how names will be sanitized.
 */

/**
 * Sanitize a name according to LAMB naming rules
 * 
 * Rules:
 * - Convert to lowercase
 * - Replace spaces with underscores
 * - Remove all non-ASCII letters, numbers, and underscores
 * - Collapse multiple underscores
 * - Remove leading/trailing underscores
 * - Max 50 characters
 * - Return "untitled" if empty
 * 
 * @param {string} name - Original name
 * @param {number} maxLength - Maximum length (default: 50)
 * @returns {{sanitized: string, wasModified: boolean}}
 */
export function sanitizeName(name, maxLength = 50) {
    if (!name) {
        return { sanitized: '', wasModified: false };
    }
    
    const originalName = name;
    
    // 1. Trim whitespace
    name = name.trim();
    
    // 2. Convert to lowercase
    name = name.toLowerCase();
    
    // 3. Replace spaces with underscores
    name = name.replace(/\s+/g, '_');
    
    // 4. Remove all characters except ASCII letters, numbers, and underscores
    name = name.replace(/[^a-z0-9_]/g, '');
    
    // 5. Collapse multiple underscores
    name = name.replace(/_+/g, '_');
    
    // 6. Remove leading/trailing underscores
    name = name.replace(/^_+|_+$/g, '');
    
    // 7. Enforce maximum length
    if (name.length > maxLength) {
        name = name.substring(0, maxLength);
        // Remove trailing underscore if truncation created one
        name = name.replace(/_+$/, '');
    }
    
    // 8. Fallback if empty after sanitization
    if (!name) {
        name = 'untitled';
    }
    
    const wasModified = name !== originalName.trim().toLowerCase() && originalName.trim() !== '';
    
    return {
        sanitized: name,
        wasModified: wasModified
    };
}

/**
 * Sanitize assistant name and add user ID prefix preview
 * 
 * Note: This is for preview only. Backend will handle actual duplicate checking.
 * 
 * @param {string} name - Original name
 * @param {number} userId - User ID for prefix
 * @param {number} maxLength - Maximum length (default: 50)
 * @returns {{sanitized: string, prefixed: string, wasModified: boolean}}
 */
export function sanitizeAssistantName(name, userId, maxLength = 50) {
    const result = sanitizeName(name, maxLength);
    
    // Create prefixed version for preview
    const prefixed = userId ? `${userId}_${result.sanitized}` : result.sanitized;
    
    return {
        sanitized: result.sanitized,
        prefixed: prefixed,
        wasModified: result.wasModified
    };
}

/**
 * Check if a name needs sanitization
 * 
 * @param {string} name - Name to check
 * @returns {boolean} - True if name needs sanitization
 */
export function needsSanitization(name) {
    if (!name) return false;
    
    const { sanitized, wasModified } = sanitizeName(name);
    return wasModified;
}

