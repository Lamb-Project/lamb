import { writable } from 'svelte/store';

/**
 * Config store - holds LAMB runtime configuration
 * Usually loaded from window.LAMB_CONFIG
 */
function createConfigStore() {
  const { subscribe, set } = writable({
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
  });

  return {
    subscribe,
    setConfig: (config) => set(config)
  };
}

export const configStore = createConfigStore();
