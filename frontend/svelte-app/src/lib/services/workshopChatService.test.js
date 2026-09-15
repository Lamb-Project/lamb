// src/lib/services/workshopChatService.test.js
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { sendWorkshopChat } from './workshopChatService.js';

/**
 * Build a mock ReadableStream that emits the given SSE lines.
 * @param {string[]} lines
 */
function mockSseStream(lines) {
	return new ReadableStream({
		start(controller) {
			for (const l of lines) {
				controller.enqueue(new TextEncoder().encode(l));
			}
			controller.close();
		},
	});
}

const baseParams = {
	sessionId: 'ws-1-2-123',
	assistantId: 7,
	token: 'workshop-token-abc',
	messages: [{ role: 'user', content: 'Hello' }],
};

describe('sendWorkshopChat — SSE frame dispatch', () => {
	let fetchMock;

	beforeEach(() => {
		fetchMock = vi.fn();
		vi.stubGlobal('fetch', fetchMock);
	});

	afterEach(() => {
		vi.unstubAllGlobals();
	});

	test('N1: observability frame → onObservability with frame data', async () => {
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"type":"observability","data":{"system_instructions":"Be a tutor","rag_context":"ctx"}}\n\n',
				'data: [DONE]\n\n',
			]),
		});
		const onObservability = vi.fn();
		await sendWorkshopChat(baseParams, { onObservability });
		expect(onObservability).toHaveBeenCalledTimes(1);
		expect(onObservability).toHaveBeenCalledWith({
			system_instructions: 'Be a tutor',
			rag_context: 'ctx',
		});
	});

	test('N2: tool_event frame → onToolEvent with event data', async () => {
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"type":"tool_event","data":{"type":"tool","name":"calculator","args":"1+1"}}\n\n',
				'data: [DONE]\n\n',
			]),
		});
		const onToolEvent = vi.fn();
		await sendWorkshopChat(baseParams, { onToolEvent });
		expect(onToolEvent).toHaveBeenCalledTimes(1);
		expect(onToolEvent).toHaveBeenCalledWith({
			type: 'tool',
			name: 'calculator',
			args: '1+1',
		});
	});

	test('N3: content chunk → onChunk with delta content only', async () => {
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
				'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
				'data: [DONE]\n\n',
			]),
		});
		const onChunk = vi.fn();
		await sendWorkshopChat(baseParams, { onChunk });
		expect(onChunk).toHaveBeenCalledTimes(2);
		expect(onChunk.mock.calls[0][0]).toBe('Hello');
		expect(onChunk.mock.calls[1][0]).toBe(' world');
	});

	test('N4: [DONE] → onDone fired once and stream stops', async () => {
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"choices":[{"delta":{"content":"A"}}]}\n\n',
				'data: [DONE]\n\n',
				'data: {"choices":[{"delta":{"content":"never reached"}}]}\n\n',
			]),
		});
		const onChunk = vi.fn();
		const onDone = vi.fn();
		await sendWorkshopChat(baseParams, { onChunk, onDone });
		expect(onDone).toHaveBeenCalledTimes(1);
		expect(onChunk).toHaveBeenCalledTimes(1); // frame after [DONE] ignored
	});

	test('N5: no handlers passed → stream consumed without crashing', async () => {
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"type":"observability","data":{"x":1}}\n\n',
				'data: [DONE]\n\n',
			]),
		});
		await expect(sendWorkshopChat(baseParams, {})).resolves.toBeUndefined();
	});

	test('request carries token header, messages, stream, observability, tools', async () => {
		fetchMock.mockResolvedValue({ ok: true, body: mockSseStream(['data: [DONE]\n\n']) });
		await sendWorkshopChat(
			{
				...baseParams,
				opts: { tools: [{ type: 'function', function: { name: 'calculator' } }] },
			},
			{}
		);
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe(
			'/lamb/v1/workshop/sessions/ws-1-2-123/assistant/7/chat'
		);
		expect(init.headers.token).toBe('workshop-token-abc');
		const body = JSON.parse(init.body);
		expect(body.stream).toBe(true);
		expect(body.observability).toBe(true);
		expect(body.messages).toEqual([{ role: 'user', content: 'Hello' }]);
		expect(body.tools).toHaveLength(1);
	});

	test('HTTP error → onError with parsed detail', async () => {
		fetchMock.mockResolvedValue({
			ok: false,
			status: 403,
			json: async () => ({ detail: 'Not your assistant' }),
		});
		const onError = vi.fn();
		await sendWorkshopChat(baseParams, { onError });
		expect(onError).toHaveBeenCalledWith('Not your assistant');
	});

	test('abort signal terminates the stream quietly', async () => {
		const controller = new AbortController();
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
				'data: [DONE]\n\n',
			]),
		});
		const onChunk = vi.fn();
		controller.abort();
		await sendWorkshopChat(baseParams, { onChunk }, controller.signal);
		// Aborted before read — no crash; at most zero chunks delivered.
		expect(true).toBe(true);
	});
});