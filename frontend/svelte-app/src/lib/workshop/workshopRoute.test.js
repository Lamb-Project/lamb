// src/lib/workshop/workshopRoute.test.js
import { describe, test, expect } from 'vitest';
import { isWorkshopPath, WORKSHOP_ROUTE_PREFIX } from './workshopRoute.js';

describe('isWorkshopPath', () => {
	test('matches the student wizard route', () => {
		expect(isWorkshopPath('/m/workshop/12')).toBe(true);
		expect(isWorkshopPath('/m/workshop/12/')).toBe(true);
	});

	test('honours a deployment base path', () => {
		expect(isWorkshopPath('/lamb/m/workshop/12', '/lamb')).toBe(true);
		expect(isWorkshopPath('/m/workshop/12', '/lamb')).toBe(false);
	});

	test('rejects creator routes', () => {
		expect(isWorkshopPath('/assistants')).toBe(false);
		expect(isWorkshopPath('/')).toBe(false);
		expect(isWorkshopPath('/m/other/1')).toBe(false);
	});

	test('rejects a prefix that is not the workshop mount', () => {
		expect(isWorkshopPath('/m/workshop-other/1')).toBe(false);
	});

	test('is defensive about empty input', () => {
		expect(isWorkshopPath('')).toBe(false);
		expect(isWorkshopPath(undefined)).toBe(false);
	});

	test('prefix constant is the wizard mount', () => {
		expect(WORKSHOP_ROUTE_PREFIX).toBe('/m/workshop/');
	});
});