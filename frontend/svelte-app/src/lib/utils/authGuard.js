/**
 * Route guard for the SPA (#260, #218). Only the landing page, which renders the
 * login and signup forms, is public; every other page needs a session.
 * @param {string} pathname
 * @param {string} base
 * @returns {boolean}
 */
export function isPublicPath(pathname, base = '') {
	const path = pathname.replace(/\/+$/, '');
	return path === '' || path === base.replace(/\/+$/, '');
}

/**
 * @param {string} pathname
 * @param {boolean} loggedIn
 * @param {string} base
 * @returns {boolean} true when the page must not render and the user goes to login
 */
export function needsLogin(pathname, loggedIn, base = '') {
	return !loggedIn && !isPublicPath(pathname, base);
}
