import { browser } from '$app/environment';

const defaultConfig = {
  api: {
    baseUrl: '/creator',
    lambServer: 'http://localhost:9099'
  },
  assets: {
    path: '/static'
  },
  features: {
    enableOpenWebUi: true,
    enableDebugMode: false
  }
};

/**
 * Config service - retrieves runtime configuration
 * Loads from window.LAMB_CONFIG if available
 */
export const configService = {
  /**
   * Get the complete runtime configuration
   */
  getConfig: () => {
    if (browser && window.LAMB_CONFIG) {
      return window.LAMB_CONFIG;
    }
    return defaultConfig;
  },

  /**
   * Get a specific config value by path (e.g., 'api.baseUrl')
   */
  getConfigValue: (path) => {
    const config = configService.getConfig();
    return path.split('.').reduce((obj, key) => obj?.[key], config);
  },

  /**
   * Get the API base URL
   */
  getApiBaseUrl: () => {
    return configService.getConfigValue('api.baseUrl') || '/creator';
  },

  /**
   * Get the LAMB server URL
   */
  getLambServer: () => {
    return configService.getConfigValue('api.lambServer') || 'http://localhost:9099';
  }
};
