/**
 * LAMB Frontend Configuration
 * 
 * This file contains runtime configuration for the LAMB frontend.
 * It is loaded dynamically after the app is built and can be modified
 * without rebuilding the application.
 * 
 * IMPORTANT: The lambServer URL should match LAMB_WEB_HOST environment variable
 * - Development: http://localhost:9099
 * - Production: Your public-facing domain (e.g., https://lamb.yourdomain.com)
 */
window.LAMB_CONFIG = {
  // API endpoints
	api: {
		// Base URL for the LAMB backend API (use absolute URL in dev)
		baseUrl: 'http://localhost:9099/creator',

		// Full URL to the LAMB server (used for browser-side requests)
		// This should match the LAMB_WEB_HOST environment variable
		// Dev: http://localhost:9099
		// Production: https://lamb.yourdomain.com
		lambServer: 'http://localhost:9099',

		// Full URL to the OpenWebUI server (if applicable)
		openWebUiServer: 'http://localhost:8080',

    // API key for LAMB server authentication
    // Note: lambApiKey removed for security - now using user authentication tokens
  },
  
  // Static assets configuration
  assets: {
    // Path to static assets
    path: '/static'
  },
  
  // Feature flags
  features: {
    // Enable/disable features as needed
    enableOpenWebUi: true,
    enableDebugMode: true
  }
};
