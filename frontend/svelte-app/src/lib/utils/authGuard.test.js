import { describe, test, expect } from 'vitest';
import { isPublicPath, needsLogin } from './authGuard.js';

describe('authGuard', () => {
	test('only the landing page is public', () => {
		expect(isPublicPath('/')).toBe(true);
		expect(isPublicPath('/lamb/', '/lamb')).toBe(true);
		expect(isPublicPath('/lamb', '/lamb')).toBe(true);
		for (const p of ['/assistants', '/knowledgebases', '/admin', '/moodle', '/api-keys', '/lamb/assistants']) {
			expect(isPublicPath(p, p.startsWith('/lamb') ? '/lamb' : '')).toBe(false);
		}
	});

	test('protected pages need a session', () => {
		expect(needsLogin('/assistants', false)).toBe(true);
		expect(needsLogin('/assistants', true)).toBe(false);
		expect(needsLogin('/', false)).toBe(false);
	});
});
