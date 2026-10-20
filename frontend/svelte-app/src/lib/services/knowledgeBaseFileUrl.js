/** Normalize only the separator before a KB static path in an absolute HTTP URL.
 * Older KB configurations ending in '/' saved URLs containing '//static/'.
 * Preserve the origin, deployment prefix, filename, query and fragment.
 */
export function knowledgeBaseFileUrl(value) {
    if (typeof value !== 'string' || !/^https?:\/\//i.test(value)) return value;
    try {
        const url = new URL(value);
        if (!/\/{2,}static\//.test(url.pathname)) return value;
        url.pathname = url.pathname.replace(/\/{2,}(?=static\/)/g, '/');
        return url.href;
    } catch {
        return value;
    }
}
