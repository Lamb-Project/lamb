// The kinds of activity the setup page offers.
//
// Marc, 15 November 2026: once the organization is chosen, LAMB tells the kinds of activity
// available there. The server works the list out for this teacher, organization by organization
// (`org_modules` in the answer of /lamb/v1/lti/setup/info: a chat needs a published assistant,
// file evaluation one with a rubric, LLM access the organization's setup and room in the
// teacher's allowance). A kind that cannot be created is not shown at all.

/**
 * @param {{ modules?: Array<{ name: string }>, org_modules?: Record<string, string[]> } | null | undefined} info
 *        answer of /lamb/v1/lti/setup/info
 * @param {string | number | null | undefined} organizationId the chosen organization, if any
 * @returns {Array<{ name: string, [key: string]: any }>} the kinds to offer, in the server's order
 */
export function kindsFor(info, organizationId) {
	const described = Array.isArray(info?.modules) ? info.modules : [];
	if (organizationId === null || organizationId === undefined || organizationId === '') return [];
	const lists = info?.org_modules;
	// A server from before this rule sends no lists: every kind it describes is offered, as it was.
	if (!lists || typeof lists !== 'object') return described;
	const names = lists[String(organizationId)];
	if (!Array.isArray(names)) return [];
	return described.filter((kind) => names.includes(kind.name));
}

/**
 * The kind to keep selected after the list changed: the current one while it is still offered,
 * else the first of the list, else none.
 * @param {string} current
 * @param {Array<{ name: string }>} kinds
 * @returns {string}
 */
export function keepOrFirst(current, kinds) {
	if (kinds.some((kind) => kind.name === current)) return current;
	return kinds.length > 0 ? kinds[0].name : '';
}
