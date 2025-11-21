/**
 * Date Helpers - Utility functions for formatting dates
 * 
 * These functions provide reusable date formatting logic for displaying
 * timestamps in a user-friendly format.
 */

/**
 * Format a Unix timestamp (seconds) to a readable date string
 * @param {number|null|undefined} timestamp - Unix timestamp in seconds
 * @param {Object} options - Formatting options
 * @param {boolean} [options.includeTime=true] - Whether to include time
 * @param {boolean} [options.relative=false] - Whether to show relative time (e.g., "2 hours ago")
 * @returns {string} Formatted date string, or '-' if timestamp is invalid
 * 
 * @example
 * formatDate(1678886400) // "2023-03-15 10:00:00"
 * formatDate(1678886400, { includeTime: false }) // "2023-03-15"
 * formatDate(1678886400, { relative: true }) // "2 hours ago"
 */
export function formatDate(timestamp, options = {}) {
  const { includeTime = true, relative = false } = options;
  
  if (!timestamp || timestamp === null || timestamp === undefined) {
    return '-';
  }
  
  try {
    // Convert seconds to milliseconds if needed
    const date = new Date(timestamp * 1000);
    
    // Check if date is valid
    if (isNaN(date.getTime())) {
      return '-';
    }
    
    if (relative) {
      return getRelativeTime(date);
    }
    
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    
    if (includeTime) {
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } else {
      return `${year}-${month}-${day}`;
    }
  } catch (error) {
    console.error('Error formatting date:', error);
    return '-';
  }
}

/**
 * Get relative time string (e.g., "2 hours ago", "3 days ago")
 * @param {Date} date - Date object
 * @returns {string} Relative time string
 */
function getRelativeTime(date) {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);
  const diffWeeks = Math.floor(diffDays / 7);
  const diffMonths = Math.floor(diffDays / 30);
  const diffYears = Math.floor(diffDays / 365);
  
  if (diffSeconds < 60) {
    return 'Just now';
  } else if (diffMinutes < 60) {
    return `${diffMinutes} minute${diffMinutes !== 1 ? 's' : ''} ago`;
  } else if (diffHours < 24) {
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  } else if (diffDays < 7) {
    return `${diffDays} day${diffDays !== 1 ? 's' : ''} ago`;
  } else if (diffWeeks < 4) {
    return `${diffWeeks} week${diffWeeks !== 1 ? 's' : ''} ago`;
  } else if (diffMonths < 12) {
    return `${diffMonths} month${diffMonths !== 1 ? 's' : ''} ago`;
  } else {
    return `${diffYears} year${diffYears !== 1 ? 's' : ''} ago`;
  }
}

/**
 * Format date for table display (compact format)
 * @param {number|null|undefined} timestamp - Unix timestamp in seconds
 * @returns {string} Formatted date string
 */
export function formatDateForTable(timestamp) {
  return formatDate(timestamp, { includeTime: true, relative: false });
}

