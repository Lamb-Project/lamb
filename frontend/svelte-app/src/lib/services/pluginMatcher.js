/**
 * @module pluginMatcher
 *
 * Pure helpers for matching import plugins to uploaded files. The matcher
 * has zero UI side-effects so it can be unit-tested in isolation. The
 * tie-break (showing a picker modal when more than one plugin matches) is
 * delegated to the caller — see ``PluginPickerModal.svelte``.
 *
 * Source of truth for which extensions a plugin accepts is the plugin's
 * own ``file_extensions`` metadata returned by ``/creator/libraries/plugins``.
 * The frontend never hardcodes extension → plugin mappings.
 */

/**
 * @typedef {Object} PluginMeta
 * @property {string} name
 * @property {string} [description]
 * @property {string} [human_label]
 * @property {string[]} [file_extensions]
 * @property {string[]} [supported_source_types]
 */

/**
 * Extract the lower-cased extension of a filename, without the leading dot.
 * Returns an empty string when no extension is found.
 *
 * @param {string} filename
 * @returns {string}
 */
export function fileExtension(filename) {
	if (!filename || typeof filename !== 'string') return '';
	const dot = filename.lastIndexOf('.');
	if (dot < 0 || dot === filename.length - 1) return '';
	return filename.slice(dot + 1).toLowerCase();
}

/**
 * Return the subset of ``plugins`` whose ``file_extensions`` includes the
 * given file's extension. Matching is case-insensitive and tolerates leading
 * dots in either source.
 *
 * Plugins with no declared extensions (URL / YouTube imports, etc.) are
 * always excluded — they're not file-based.
 *
 * @param {File|{ name?: string }|string} file - File, file-like object, or filename.
 * @param {PluginMeta[]} plugins
 * @returns {PluginMeta[]}
 */
export function matchPluginsForFile(file, plugins) {
	if (!Array.isArray(plugins) || plugins.length === 0) return [];
	const filename = typeof file === 'string' ? file : (file?.name ?? '');
	const ext = fileExtension(filename);
	if (!ext) return [];
	return plugins.filter((p) => {
		const exts = Array.isArray(p?.file_extensions) ? p.file_extensions : [];
		return exts.some((e) => String(e).toLowerCase().replace(/^\./, '') === ext);
	});
}
