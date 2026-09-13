// Only enabled model IDs from the authoritative capability list can be defaults.
export function reconcileModelDefaults(defaults, capabilities) {
 const connectors = capabilities?.connectors || {};
 const models = (name) => connectors[name]?.available_llms || [];
 let connector = defaults.connector;
 if (!models(connector).length) {
  // Never silently select a debug connector for a real assistant.
  connector = Object.keys(connectors).find(name => name !== 'bypass' && models(name).length) || '';
 }
 const llm = models(connector).includes(defaults.llm) ? defaults.llm : (models(connector)[0] || '');
 return { ...defaults, connector, llm };
}

export function validateModelSelection(connector, llm, capabilities, loading = false) {
 if (loading) return 'Please wait for the available models to load.';
 if (!llm || !capabilities?.connectors?.[connector]?.available_llms?.includes(llm)) {
  return 'Select a model enabled for your organization. If none are available, contact your administrator.';
 }
 return null;
}
