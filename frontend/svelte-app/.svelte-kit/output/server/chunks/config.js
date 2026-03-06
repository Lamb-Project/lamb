const defaultConfig = {
  api: {
    baseUrl: "/creator",
    // Default or fallback base URL
    lambServer: "http://localhost:9099"
    // Default LAMB server URL
    // Note: lambApiKey removed for security - now using user authentication
  },
  // Static assets configuration
  assets: {
    path: "/static"
  },
  // Feature flags
  features: {
    enableOpenWebUi: true,
    enableDebugMode: true
  }
};
function getConfig() {
  console.warn("LAMB_CONFIG not found on window, using default.");
  return defaultConfig;
}
function getApiUrl(endpoint) {
  const config = getConfig();
  const base = config?.api?.baseUrl || defaultConfig.api.baseUrl;
  return `${base.replace(/\/$/, "")}/${endpoint.replace(/^\//, "")}`;
}
export {
  getConfig as a,
  getApiUrl as g
};
