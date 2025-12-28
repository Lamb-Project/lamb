/**
 * Analytics Service
 * Provides API calls for assistant chat analytics
 * 
 * Created: December 27, 2025
 */

import { getApiUrl } from '$lib/config';
import { browser } from '$app/environment';
import axios from 'axios';

/**
 * @typedef {Object} ChatSummary
 * @property {string} id - Chat ID
 * @property {string} title - Chat title
 * @property {string} [user_id] - User ID (may be anonymized)
 * @property {string} [user_name] - User name (may be anonymized)
 * @property {string} [user_email] - User email (null if anonymized)
 * @property {number} message_count - Number of messages in chat
 * @property {string} created_at - Chat creation timestamp
 * @property {string} updated_at - Last update timestamp
 */

/**
 * @typedef {Object} ChatListResponse
 * @property {ChatSummary[]} chats - List of chats
 * @property {number} total - Total number of chats
 * @property {number} page - Current page
 * @property {number} per_page - Items per page
 * @property {number} total_pages - Total number of pages
 */

/**
 * @typedef {Object} ChatMessage
 * @property {string} id - Message ID
 * @property {string} role - Message role (user or assistant)
 * @property {string} content - Message content
 * @property {string} [timestamp] - Message timestamp
 */

/**
 * @typedef {Object} ChatDetail
 * @property {string} id - Chat ID
 * @property {string} title - Chat title
 * @property {Object} user - User info
 * @property {string} created_at - Creation timestamp
 * @property {string} updated_at - Update timestamp
 * @property {ChatMessage[]} messages - All messages in the chat
 */

/**
 * @typedef {Object} AnalyticsStats
 * @property {number} total_chats - Total number of chats
 * @property {number} unique_users - Number of unique users
 * @property {number} total_messages - Total messages across all chats
 * @property {number} avg_messages_per_chat - Average messages per chat
 */

/**
 * @typedef {Object} TimelineDataPoint
 * @property {string} date - Date key
 * @property {number} chat_count - Number of chats
 * @property {number} message_count - Number of messages
 */

/**
 * Helper function to get auth headers
 * @returns {Object} Headers object with Authorization
 */
function getAuthHeaders() {
    const token = browser ? localStorage.getItem('userToken') : null;
    if (!token) {
        throw new Error('Not authenticated');
    }
    return {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
}

/**
 * Get list of chats for an assistant
 * @param {number} assistantId - Assistant ID
 * @param {Object} [options] - Filter options
 * @param {string} [options.startDate] - Filter from date (ISO format)
 * @param {string} [options.endDate] - Filter until date (ISO format)
 * @param {string} [options.userId] - Filter by user ID
 * @param {number} [options.page=1] - Page number
 * @param {number} [options.perPage=20] - Items per page
 * @returns {Promise<ChatListResponse>}
 */
export async function getAssistantChats(assistantId, options = {}) {
    if (!browser) {
        throw new Error('This operation is only available in the browser');
    }
    
    const { startDate, endDate, userId, page = 1, perPage = 20 } = options;
    
    const params = new URLSearchParams();
    params.append('page', page.toString());
    params.append('per_page', perPage.toString());
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    if (userId) params.append('user_id', userId);
    
    const url = getApiUrl(`/analytics/assistant/${assistantId}/chats?${params.toString()}`);
    
    const response = await axios.get(url, {
        headers: getAuthHeaders()
    });
    
    return response.data;
}

/**
 * Get detailed chat conversation
 * @param {number} assistantId - Assistant ID
 * @param {string} chatId - Chat ID
 * @returns {Promise<ChatDetail>}
 */
export async function getChatDetail(assistantId, chatId) {
    if (!browser) {
        throw new Error('This operation is only available in the browser');
    }
    
    const url = getApiUrl(`/analytics/assistant/${assistantId}/chats/${chatId}`);
    
    const response = await axios.get(url, {
        headers: getAuthHeaders()
    });
    
    return response.data;
}

/**
 * Get usage statistics for an assistant
 * @param {number} assistantId - Assistant ID
 * @param {Object} [options] - Filter options
 * @param {string} [options.startDate] - Stats from date (ISO format)
 * @param {string} [options.endDate] - Stats until date (ISO format)
 * @returns {Promise<{assistant_id: number, period: Object, stats: AnalyticsStats}>}
 */
export async function getAssistantStats(assistantId, options = {}) {
    if (!browser) {
        throw new Error('This operation is only available in the browser');
    }
    
    const { startDate, endDate } = options;
    
    const params = new URLSearchParams();
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const queryString = params.toString();
    const url = getApiUrl(`/analytics/assistant/${assistantId}/stats${queryString ? '?' + queryString : ''}`);
    
    const response = await axios.get(url, {
        headers: getAuthHeaders()
    });
    
    return response.data;
}

/**
 * Get activity timeline for an assistant
 * @param {number} assistantId - Assistant ID
 * @param {Object} [options] - Filter options
 * @param {string} [options.period='day'] - Aggregation period: day, week, or month
 * @param {string} [options.startDate] - Timeline from date (ISO format)
 * @param {string} [options.endDate] - Timeline until date (ISO format)
 * @returns {Promise<{assistant_id: number, period: string, data: TimelineDataPoint[]}>}
 */
export async function getAssistantTimeline(assistantId, options = {}) {
    if (!browser) {
        throw new Error('This operation is only available in the browser');
    }
    
    const { period = 'day', startDate, endDate } = options;
    
    const params = new URLSearchParams();
    params.append('period', period);
    if (startDate) params.append('start_date', startDate);
    if (endDate) params.append('end_date', endDate);
    
    const url = getApiUrl(`/analytics/assistant/${assistantId}/timeline?${params.toString()}`);
    
    const response = await axios.get(url, {
        headers: getAuthHeaders()
    });
    
    return response.data;
}

/**
 * Format a date for display
 * @param {string} isoDate - ISO date string
 * @returns {string} Formatted date string
 */
export function formatDate(isoDate) {
    if (!isoDate) return '-';
    try {
        const date = new Date(isoDate);
        return date.toLocaleDateString(undefined, {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    } catch {
        return isoDate;
    }
}

/**
 * Format a short date for timeline/table display
 * @param {string} isoDate - ISO date string
 * @returns {string} Short formatted date
 */
export function formatShortDate(isoDate) {
    if (!isoDate) return '-';
    try {
        const date = new Date(isoDate);
        return date.toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric'
        });
    } catch {
        return isoDate;
    }
}

