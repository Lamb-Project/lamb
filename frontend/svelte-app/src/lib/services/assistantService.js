// import { API_CONFIG, getApiUrl } from '$lib/config'; // No longer used directly
import { getApiUrl, getConfig } from '$lib/config'; // Use the new helper
import { browser } from '$app/environment';
import axios from 'axios';

/**
 * @typedef {Object} Assistant - Defines the structure of an assistant object from the API
 * @property {number} id
 * @property {string} name
 * @property {string} [description]
 * // Add other expected fields as needed based on actual API response
 */

/**
 * @typedef {Object} ApiAssistant - Defines the structure returned by getAssistantById API
 * @property {number} id
 * @property {string} name
 * @property {string} [description]
 * @property {string} [owner]
 * @property {boolean} [published] - Note: API uses 'published', frontend store uses 'is_published'
 * @property {string} [system_prompt]
 * @property {string} [prompt_template]
 * @property {string} [api_callback] - Deprecated, use metadata instead
 * @property {string} [metadata] - JSON string containing plugin configuration
 * @property {number} [RAG_Top_k]
 * @property {string} [RAG_collections]
 * @property {string} [group_id]
 * @property {string} [group_name]
 * @property {string} [oauth_consumer_name]
 * @property {number} [published_at]
 * // Add other fields returned by the API like RAG_endpoint etc. if necessary
 */

// NOTE: Keeping the structure, but commenting out functions not needed for Assistants List

// /**
//  * Parse JWT token to get user ID
//  * @param {string} token - JWT token
//  * @returns {string|null} - User ID or null if parsing fails
//  */
// function getUserIdFromToken(token) {
//   try {
//     const base64Url = token.split('.')[1];
//     const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
//     const jsonPayload = decodeURIComponent(atob(base64).split('').map(c => {
//       return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
//     }).join(''));
//     const payload = JSON.parse(jsonPayload);
//     return payload.user_id || payload.sub;
//   } catch (err) {
//     console.error('Error parsing token:', err);
//     return null;
//   }
// }

// /**
//  * Helper function to check browser environment and authentication
//  * @returns {string} The token
//  * @throws {Error} If not in browser or not authenticated
//  */
// function checkBrowserAndAuth() {
//   if (!browser) {
//     throw new Error('This operation is only available in the browser');
//   }
//
//   const token = localStorage.getItem('userToken');
//   if (!token) {
//     throw new Error('Please log in to continue');
//   }
//
//   return token;
// }

// /**
//  * Get API key from local storage or environment
//  * @returns {string} The API key
//  */
// const getApiKey = () => browser ? localStorage.getItem('apiKey') || '' : '';

/**
 * Get assistants list for the logged-in user.
 * @param {number} [limit=10] - Number of assistants per page.
 * @param {number} [offset=0] - Offset for pagination.
 * @returns {Promise<{assistants: import('../stores/assistantStore').Assistant[], total_count: number}>} Object with assistants list and total count.
 * @throws {Error} If not authenticated or fetch fails
 */
export async function getAssistants(limit = 10, offset = 0) {
	if (!browser) {
		console.warn('getAssistants called outside browser context');
		return { assistants: [], total_count: 0 }; // Return empty paginated structure
	}
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}

	// Get the full backend server URL from the runtime config
	// --- DEBUGGING START ---
	console.log(
		'Checking window.LAMB_CONFIG in getAssistants:',
		window.LAMB_CONFIG,
		'typeof:',
		typeof window.LAMB_CONFIG
	);
	if (window.LAMB_CONFIG) {
		console.log(
			'Checking window.LAMB_CONFIG.api:',
			window.LAMB_CONFIG.api,
			'typeof:',
			typeof window.LAMB_CONFIG.api
		);
		if (window.LAMB_CONFIG.api) {
			console.log(
				'Checking window.LAMB_CONFIG.api.lambServer:',
				window.LAMB_CONFIG.api.lambServer,
				'typeof:',
				typeof window.LAMB_CONFIG.api.lambServer
			);
		}
	}
	// --- DEBUGGING END ---
	// const lambServerUrl = window.LAMB_CONFIG?.api?.lambServer; // <-- Removed
	// if (!lambServerUrl) {
	//     // Add more specific error log before throwing
	//     console.error('window.LAMB_CONFIG details before error:', JSON.stringify(window.LAMB_CONFIG, null, 2));
	//     throw new Error('LAMB server URL not configured in window.LAMB_CONFIG.api.lambServer');
	// }

	// Construct the absolute URL with pagination parameters
	// const endpointPath = '/creator/assistant/get_assistants'; // <-- Removed
	const urlParams = new URLSearchParams({
		limit: limit.toString(),
		offset: offset.toString()
	});
	// const apiUrl = `${lambServerUrl.replace(/\/$/, '')}${endpointPath}?${urlParams}`; // <-- Removed
	const apiUrl = getApiUrl(`/assistant/get_assistants?${urlParams}`); // <-- Added
	console.log('Fetching assistants from absolute URL:', apiUrl);

	// Log equivalent curl command for debugging
	console.log(
		`Equivalent curl command:\ncurl -X GET "${apiUrl}" -H "Authorization: Bearer ${token}"`
	);

	const response = await fetch(apiUrl, {
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/json'
		}
	});

	if (!response.ok) {
		let errorDetail = 'Failed to fetch assistants';
		try {
			const error = await response.json();
			errorDetail = error?.detail || errorDetail;
		} catch (e) {
			// Ignore if response is not JSON
		}
		console.error('API error response status:', response.status, 'Detail:', errorDetail);
		throw new Error(errorDetail);
	}

	const data = await response.json();

	// Return the expected structure { assistants: [], total_count: 0 }
	// Ensure defaults if API response is malformed
	return {
		assistants: Array.isArray(data?.assistants) ? data.assistants : [],
		total_count: typeof data?.total_count === 'number' ? data.total_count : 0
	};
}

/**
 * Get details for a specific assistant by ID.
 * @param {number} assistantId - The ID of the assistant to fetch.
 * @returns {Promise<ApiAssistant>} The assistant details.
 * @throws {Error} If not authenticated or fetch fails.
 */
export async function getAssistantById(assistantId) {
	if (!browser) {
		throw new Error('getAssistantById called outside browser context');
	}
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}

	// const lambServerUrl = window.LAMB_CONFIG?.api?.lambServer; // <-- Removed
	// if (!lambServerUrl) {
	//     console.error('window.LAMB_CONFIG details before error:', JSON.stringify(window.LAMB_CONFIG, null, 2));
	//     throw new Error('LAMB server URL not configured in window.LAMB_CONFIG.api.lambServer');
	// }

	// const endpointPath = `/creator/assistant/get_assistant/${assistantId}`; // <-- Removed
	// const apiUrl = `${lambServerUrl.replace(/\/$/, '')}${endpointPath}`; // <-- Removed
	const apiUrl = getApiUrl(`/assistant/get_assistant/${assistantId}`); // <-- Added
	console.log('Fetching assistant by ID from absolute URL:', apiUrl);

	const response = await fetch(apiUrl, {
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/json',
			'Cache-Control': 'no-cache, no-store, must-revalidate',
			Pragma: 'no-cache'
		},
		cache: 'no-store' // Prevent browser caching of GET request
	});

	if (!response.ok) {
		let errorDetail = `Failed to fetch assistant with ID ${assistantId}`;
		try {
			const error = await response.json();
			errorDetail = error?.detail || errorDetail;
		} catch (e) {
			/* Ignore */
		}
		console.error('API error response status:', response.status, 'Detail:', errorDetail);
		throw new Error(errorDetail);
	}

	return await response.json();
}

// --- Functions below are commented out for now ---

// // Get published assistants
// export async function getPublishedAssistants() {
//     const token = localStorage.getItem('userToken');
//     if (!token) {
//         throw new Error('Not authenticated');
//     }

//     const response = await fetch(getApiUrl(`/lamb/v1/assistant/get_published_assistants`), {
//         headers: {
//             'Authorization': `Bearer ${token}`,
//             'Content-Type': 'application/json'
//         }
//     });

//     if (!response.ok) {
//         const error = await response.json();
//         throw new Error(error.detail || 'Failed to fetch published assistants');
//     }

//     return await response.json();
// }

/**
 * Publish assistant by updating its status
 * @param {string} assistantId
 * @param {string} assistantName
 * @param {string} groupName
 * @param {string} oauthConsumerName
 * @returns {Promise<any>}
 */
export async function publishAssistant(assistantId, assistantName, groupName, oauthConsumerName) {
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}

	const apiUrl = getApiUrl(`/assistant/update_assistant/${assistantId}`);

	const bodyData = {
		name: assistantName,
		group_name: groupName,
		oauth_consumer_name: oauthConsumerName,
		is_published: true
	};

	const response = await fetch(apiUrl, {
		method: 'PUT',
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/json'
		},
		body: JSON.stringify(bodyData)
	});

	if (!response.ok) {
		let errorDetail = 'Failed to publish assistant (update failed)';
		try {
			const error = await response.json();
			errorDetail = error?.detail || errorDetail;
		} catch (e) {
			/* Ignore JSON parse error */
		}
		console.error('Publish (update) error:', response.status, errorDetail);
		throw new Error(errorDetail);
	}

	return await response.json();
}

/**
 * Unpublish assistant
 * @param {string} assistantId
 * @param {string} groupId
 * @param {string} userEmail
 * @returns {Promise<any>}
 */
export async function unpublishAssistant(assistantId, groupId, userEmail) {
	// Use the correct publish status endpoint and method
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}
	const apiUrl = getApiUrl(`/assistant/publish/${assistantId}`);
	const response = await fetch(apiUrl, {
		method: 'PUT',
		headers: {
			Authorization: `Bearer ${token}`,
			'Content-Type': 'application/json'
		},
		body: JSON.stringify({ publish_status: false })
	});
	if (!response.ok) {
		let errorDetail = 'Failed to unpublish assistant';
		try {
			const error = await response.json();
			errorDetail = error?.detail || errorDetail;
		} catch (e) {
			/* Ignore */
		}
		console.error('Unpublish error:', response.status, errorDetail);
		throw new Error(errorDetail);
	}
	return await response.json();
}

// // Update assistant publication
// export async function updateAssistantPublication(assistantId, groupName, oauthConsumerName) {
//     const token = checkBrowserAndAuth(); // Use helper
//     const response = await fetch(getApiUrl(`/lamb/v1/assistant/update_assistant_publication/${assistantId}`), {
//         method: 'PUT',
//         headers: {
//             'Authorization': `Bearer ${token}`,
//             'Content-Type': 'application/json'
//         },
//         body: JSON.stringify({
//             group_name: groupName,
//             oauth_consumer_name: oauthConsumerName
//         })
//     });

//     if (!response.ok) {
//         const error = await response.json();
//         throw new Error(error.detail || 'Failed to update assistant publication');
//     }

//     return await response.json();
// }

// // Get assistants by owner
// export async function getAssistantsByOwner(owner) {
//     // This might need different auth depending on usage context
//     const token = checkBrowserAndAuth();
//     const response = await fetch(getApiUrl(`/lamb/v1/assistant/get_assistants_by_owner/${encodeURIComponent(owner)}`), {
//         headers: {
//             'Authorization': `Bearer ${token}`,
//             'Content-Type': 'application/json'
//         }
//     });

//     if (!response.ok) {
//         const error = await response.json();
//         throw new Error(error.detail || 'Failed to fetch assistants');
//     }

//     return await response.json();
// }

/**
 * Delete an assistant
 * @param {string} id - The ID of the assistant to delete
 * @returns {Promise<Object>} Response data
 */
export async function deleteAssistant(id) {
	try {
		const token = localStorage.getItem('userToken');
		if (!token) {
			throw new Error('Not authenticated');
		}
		const userEmail = localStorage.getItem('userEmail');
		if (!userEmail) {
			throw new Error('User email not found in localStorage');
		}

		// Correct endpoint based on likely pattern, confirm if needed
		const apiUrl = getApiUrl(
			`/assistant/delete_assistant/${id}?owner=${encodeURIComponent(userEmail)}`
		);

		const response = await fetch(apiUrl, {
			method: 'DELETE',
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		if (!response.ok) {
			let errorData = { detail: `Error: ${response.status}` };
			try {
				errorData = await response.json();
			} catch (e) {
				/* Ignore parse error */
			}

			if (response.status === 403) {
				throw new Error('You do not have permission to delete this assistant');
			} else if (response.status === 404) {
				throw new Error('Assistant not found');
			} else {
				throw new Error(errorData.detail || `Error: ${response.status}`);
			}
		}

		// Check if response has content before parsing JSON
		const text = await response.text();
		return text ? JSON.parse(text) : {};
	} catch (error) {
		console.error('Error deleting assistant:', error);
		// Rethrow the original error or a new one with more context
		if (error instanceof Error) {
			throw error;
		} else {
			throw new Error('An unknown error occurred during assistant deletion');
		}
	}
}

/**
 * @typedef {Object} SystemCapabilities
 * @property {string[]} [prompt_processors] - List of available prompt processors.
 * @property {Object.<string, any>} [connectors] - Dictionary of available connectors/models.
 * @property {string[]} [rag_processors] - List of available RAG processors.
 */

/**
 * Get system capabilities (connectors, models, etc.)
 * @returns {Promise<SystemCapabilities>} System capabilities
 */
export async function getSystemCapabilities() {
	const token = localStorage.getItem('userToken'); // Simplified auth check for now
	if (!token) {
		throw new Error('Not authenticated');
	}
	// Assuming capabilities endpoint is relative to base URL
	const response = await fetch(getApiUrl(`/system/capabilities`), {
		headers: {
			Authorization: `Bearer ${token}`
		}
	});
	if (!response.ok) {
		let errorDetail = 'Failed to fetch system capabilities';
		try {
			const error = await response.json();
			errorDetail = error?.detail || errorDetail;
		} catch (e) {
			/* Ignore */
		}
		throw new Error(errorDetail);
	}
	return await response.json();
}

/**
 * Creates a new assistant.
 * @param {object} assistantData - The data for the new assistant.
 * @returns {Promise<{assistant_id: number, name: string, description?: string, owner: string, publish_status?: any}>} The created assistant data from the API.
 * @throws {Error} If the request fails, including specific name conflict errors.
 */
export async function createAssistant(assistantData) {
	if (!browser) {
		throw new Error('Cannot create assistant in server environment');
	}
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}

	const url = getApiUrl('/assistant/create_assistant'); // Uses /creator base via helper
	console.log('Creating assistant with data:', assistantData);

	try {
		const response = await axios.post(url, assistantData, {
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			}
		});

		// Assuming success if axios doesn't throw
		console.log('Assistant created successfully:', response.data);
		// Cast the response data to the defined type for the caller
		return response.data;
	} catch (error) {
		console.error('Error creating assistant:', error);
		let errorMessage = 'Failed to create assistant.';

		if (axios.isAxiosError(error) && error.response) {
			const errorData = error.response.data;
			console.error('API Error Response:', errorData);

			// Check for specific name conflict error detail
			if (errorData?.detail?.includes('already exists for this owner')) {
				const match = errorData.detail.match(/named '([^']+)' already exists/);
				const existingName = match ? match[1] : 'this name';
				errorMessage = `An assistant named '${existingName}' already exists. Please choose a different name.`;
			} else {
				// Use detail or message if available, otherwise status text
				errorMessage =
					errorData?.detail ||
					errorData?.message ||
					`Request failed with status ${error.response.status}`;
			}
		} else if (error instanceof Error) {
			// Handle non-Axios errors (e.g., network errors)
			errorMessage = error.message;
		}

		// Throw an error that the form can catch and display
		throw new Error(errorMessage);
	}
}

/**
 * Download assistant data
 * @param {string} assistantId
 * @returns {Promise<void>}
 * @throws {Error}
 */
export async function downloadAssistant(assistantId) {
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}
	// TODO: Confirm this endpoint exists and works as expected
	const apiUrl = getApiUrl(`/assistant/download_assistant/${assistantId}`);

	try {
		const response = await fetch(apiUrl, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		if (!response.ok) {
			let errorDetail = 'Failed to download assistant';
			try {
				const error = await response.json(); // Try to get JSON error detail
				errorDetail = error?.detail || `HTTP error! status: ${response.status}`;
			} catch (e) {
				errorDetail = `HTTP error! status: ${response.status}`; // Fallback if no JSON body
			}
			throw new Error(errorDetail);
		}

		const blob = await response.blob();
		const contentDisposition = response.headers.get('content-disposition');
		let filename = `assistant_${assistantId}.json`; // Default filename
		if (contentDisposition) {
			const filenameMatch = contentDisposition.match(/filename="?(.+?)"?$/i);
			if (filenameMatch && filenameMatch[1]) {
				filename = filenameMatch[1];
			}
		}

		// Create a link and trigger download
		const link = document.createElement('a');
		link.href = URL.createObjectURL(blob);
		link.setAttribute('download', filename);
		document.body.appendChild(link);
		link.click();
		document.body.removeChild(link);
		URL.revokeObjectURL(link.href); // Clean up
	} catch (error) {
		console.error('Download error:', error);
		if (error instanceof Error) {
			throw error; // Re-throw specific error
		} else {
			throw new Error('An unknown error occurred during download.');
		}
	}
}

/**
 * Update an existing assistant.
 * @param {number} assistantId - The ID of the assistant to update.
 * @param {Partial<Assistant>} assistantData - The data to update.
 * @returns {Promise<ApiAssistant>} The updated assistant details.
 * @throws {Error} If not authenticated or update fails.
 */
export async function updateAssistant(assistantId, assistantData) {
	if (!browser) {
		throw new Error('Cannot update assistant in server environment');
	}
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}

	// Ensure assistantData only contains allowed fields for update
	const allowedFields = [
		'name',
		'description',
		'system_prompt',
		'prompt_template',
		'RAG_Top_k',
		'RAG_collections',
		'metadata'
	];
	const filteredData = Object.keys(assistantData)
		.filter((key) => allowedFields.includes(key))
		.reduce((obj, key) => {
			/** @type {Partial<Assistant>} */
			const typedObj = obj; // Cast obj to the correct type
			// Only include non-null/non-undefined values, except for description which can be empty string
			if (assistantData[key] !== null && assistantData[key] !== undefined) {
				typedObj[key] = assistantData[key];
			} else if (key === 'description') {
				typedObj[key] = ''; // Allow empty description
			}
			return typedObj;
		}, /** @type {Partial<Assistant>} */ ({}));

	// Note: Backend expects PUT to /creator/assistant/update_assistant/{id}
	// const endpointPath = `/creator/assistant/update_assistant/${assistantId}`; // <-- Removed
	const url = getApiUrl(`/assistant/update_assistant/${assistantId}`); // <-- Added
	console.log(`Updating assistant ${assistantId} at URL:`, url);
	console.log('With data:', filteredData);

	try {
		const response = await fetch(url, {
			method: 'PUT',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(filteredData)
		});

		if (!response.ok) {
			let errorDetail = `Failed to update assistant with ID ${assistantId}`;
			try {
				const error = await response.json();
				errorDetail = error?.detail || errorDetail;
			} catch (e) {
				/* Ignore */
			}
			console.error('API error response status:', response.status, 'Detail:', errorDetail);
			throw new Error(errorDetail);
		}

		return await response.json();
	} catch (error) {
		console.error('Error updating assistant:', error);
		let errorMessage = 'Failed to update assistant.';

		if (error instanceof Error) {
			errorMessage = error.message;
		}

		throw new Error(errorMessage);
	}
}

/**
 * Sets the publish status of an assistant.
 * @param {number} assistantId - The ID of the assistant.
 * @param {boolean} publishStatus - The desired publish status (true for publish, false for unpublish).
 * @returns {Promise<ApiAssistant>} The full updated assistant details.
 * @throws {Error} If not authenticated, API call fails, or required config is missing.
 */
export async function setAssistantPublishStatus(assistantId, publishStatus) {
	if (!browser) {
		throw new Error('Cannot change publish status in server environment');
	}
	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}

	// Determine the correct endpoint based on the desired status
	// Use getApiUrl for consistency
	const endpointPath = `/assistant/publish/${assistantId}`; // <-- Corrected: Same endpoint for both
	const apiUrl = getApiUrl(endpointPath);
	console.log(`Setting publish status to ${publishStatus} for ${assistantId} at ${apiUrl}`);

	const method = 'PUT'; // <-- Corrected: Always PUT

	try {
		const response = await fetch(apiUrl, {
			method: method,
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ publish_status: publishStatus }) // <-- Added body
		});

		if (!response.ok) {
			let errorDetail = `Failed to set publish status for assistant ${assistantId}`;
			try {
				const error = await response.json();
				errorDetail = error?.detail || errorDetail;
			} catch (e) {
				/* Ignore if response is not JSON */
			}
			console.error('API error response status:', response.status, 'Detail:', errorDetail);
			throw new Error(errorDetail);
		}

		return await response.json(); // Return the full updated assistant data
	} catch (error) {
		console.error('Error setting publish status:', error);
		let errorMessage = 'Failed to set publish status.';

		if (error instanceof Error) {
			errorMessage = error.message;
		}

		throw new Error(errorMessage);
	}
}

/**
 * Get assistants shared with the current user
 * @returns {Promise<{assistants: Assistant[], count: number}>} Object with shared assistants list and count
 * @throws {Error} If not authenticated or fetch fails
 */
export async function getSharedAssistants() {
	if (!browser) {
		console.warn('getSharedAssistants called outside browser context');
		return { assistants: [], count: 0 };
	}

	const token = localStorage.getItem('userToken');
	if (!token) {
		throw new Error('Not authenticated');
	}

	try {
		// Get the base URL without /creator prefix for lamb endpoints
		const config = getConfig();
		const baseUrl = config.api.lambServer || 'http://localhost:9099';
		const apiUrl = `${baseUrl}/lamb/v1/assistant-sharing/shared-with-me`;
		console.log('Fetching shared assistants from:', apiUrl);

		const response = await fetch(apiUrl, {
			headers: {
				Authorization: `Bearer ${token}`
			}
		});

		if (!response.ok) {
			const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
			throw new Error(errorData.detail || 'Failed to fetch shared assistants');
		}

		const data = await response.json();
		console.log('Received shared assistants:', data);

		return {
			assistants: data.assistants || [],
			count: data.count || 0
		};
	} catch (error) {
		console.error('Error fetching shared assistants:', error);
		throw error;
	}
}

// // ... other functions ...
