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
