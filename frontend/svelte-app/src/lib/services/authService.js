import { getApiUrl } from '$lib/config'; // Use the new config helper

// This will be proxied to your FastAPI backend

/**
 * Handles user login
 * @param {string} email - User email
 * @param {string} password - User password
 * @returns {Promise<any>} - Promise resolving to login result (adjust 'any' type if possible)
 */
export async function login(email, password) {
	try {
		const formData = new FormData();
		formData.append('email', email);
		formData.append('password', password);

		const response = await fetch(getApiUrl('/login'), {
			method: 'POST',
			body: formData
		});

		let data;
		try {
			const text = await response.text();
			data = text ? JSON.parse(text) : {};
		} catch (e) {
			console.error('Failed to parse response:', e);
			data = {};
		}

		if (!response.ok) {
			throw new Error(data?.error || 'Login failed'); // Safe access to error property
		}

		return data;
	} catch (error) {
		console.error('Login error:', error);
		let message = 'An error occurred during login';
		if (error instanceof Error) {
			message = error.message;
		}
		// Return a consistent error shape if possible
		return {
			success: false,
			error: message
		};
	}
}

/**
 * Handles user signup
 * @param {string} name - User name
 * @param {string} email - User email
 * @param {string} password - User password
 * @param {string} secretKey - Secret key for registration
 * @returns {Promise<any>} - Promise resolving to signup result (adjust 'any' type if possible)
 */
export async function signup(name, email, password, secretKey) {
	try {
		const formData = new FormData();
		formData.append('name', name);
		formData.append('email', email);
		formData.append('password', password);
		formData.append('secret_key', secretKey);

		const response = await fetch(getApiUrl('/signup'), {
			method: 'POST',
			body: formData
		});

		let data;
		try {
			const text = await response.text();
			data = text ? JSON.parse(text) : {};
		} catch (e) {
			console.error('Failed to parse response:', e);
			data = {};
		}

		if (!response.ok) {
			throw new Error(data?.error || 'Signup failed'); // Safe access to error property
		}

		return data;
	} catch (error) {
		console.error('Signup error:', error);
		let message = 'An error occurred during signup';
		if (error instanceof Error) {
			message = error.message;
		}
		// Return a consistent error shape if possible
		return {
			success: false,
			error: message
		};
	}
}

/**
 * Sends a help request to the LAMB assistant
 * @param {string} question - User question
 * @param {string} token - User authentication token
 * @returns {Promise<any>} - Promise resolving to help response (adjust 'any' type if possible)
 */
export async function getHelp(question, token) {
	try {
		const response = await fetch(getApiUrl('/lamb_helper_assistant'), {
			method: 'POST',
			headers: {
				Authorization: `Bearer ${token}`,
				'Content-Type': 'application/json'
			},
			body: JSON.stringify({ question })
		});

		let data;
		try {
			const text = await response.text();
			data = text ? JSON.parse(text) : {};
		} catch (e) {
			console.error('Failed to parse response:', e);
			data = {};
		}

		if (!response.ok) {
			throw new Error(data?.error || 'Help request failed'); // Safe access to error property
		}

		return data;
	} catch (error) {
		console.error('Help request error:', error);
		let message = 'An error occurred while getting help';
		if (error instanceof Error) {
			message = error.message;
		}
		// Return a consistent error shape if possible
		return {
			success: false,
			error: message
		};
	}
}
