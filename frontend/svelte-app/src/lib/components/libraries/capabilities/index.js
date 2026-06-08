/**
 * @module libraries/capabilities
 *
 * Auto-import registry for capability renderers. Every ``*Renderer.svelte``
 * file in this folder is registered automatically via Vite's
 * ``import.meta.glob`` with ``eager: true`` so the renderer map is built at
 * module load time with no runtime fetch.
 *
 * Drop-in convention: name the file ``XxxRenderer.svelte`` and the
 * capability key is inferred as ``xxx`` (lower-cased). The capability key
 * must match a value of the backend ``Capability`` enum
 * (``library-manager/backend/plugins/content_handlers/capability.py``);
 * mismatches yield a renderer that is never resolved by the viewer.
 *
 * Adding a new capability renderer = drop one ``.svelte`` file here. No
 * source edits required elsewhere.
 */

const modules = /** @type {Record<string, { default: any }>} */ (
	import.meta.glob('./*Renderer.svelte', { eager: true })
);

/**
 * Map of capability key (lowercase) → Svelte component class.
 * Built from filenames at import time.
 *
 * @type {Record<string, any>}
 */
export const CAPABILITY_RENDERERS = (() => {
	/** @type {Record<string, any>} */
	const out = {};
	for (const [path, mod] of Object.entries(modules)) {
		// path is like "./TextRenderer.svelte" → "text"
		const match = /\/([A-Za-z0-9_]+)Renderer\.svelte$/.exec(path);
		if (!match) continue;
		const key = match[1].toLowerCase();
		out[key] = mod?.default;
	}
	return out;
})();

/**
 * Return the renderer component for a capability key, or ``null`` when no
 * renderer is registered. Callers fall back to a "View raw" download link
 * in that case.
 *
 * @param {string} capability
 * @returns {any|null}
 */
export function getRenderer(capability) {
	if (!capability) return null;
	return CAPABILITY_RENDERERS[String(capability).toLowerCase()] ?? null;
}
