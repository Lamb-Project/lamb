import { describe, test, expect } from 'vitest';
import { turnEndText } from './aacTurnStatus.js';

describe('turnEndText', () => {
	test('says the agent is done or waits for approval, in the session language', () => {
		expect(turnEndText('es', false)).toBe('Hecho · esperando tus instrucciones');
		expect(turnEndText('ca', true)).toBe('Esperant la teva aprovació');
		expect(turnEndText('eu-ES', false)).toBe('Eginda · zure argibideen zain');
		expect(turnEndText(undefined, false)).toBe('Done · waiting for your instructions');
		expect(turnEndText('fr', true)).toBe('Waiting for your approval');
	});
});
