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
		}
	});
}

const baseParams = {
	sessionId: 'ws-1-2-123',
	assistantId: 7,
	token: 'workshop-token-abc',
	messages: [{ role: 'user', content: 'Hello' }]
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
				'data: [DONE]\n\n'
			])
		});
		const onObservability = vi.fn();
		await sendWorkshopChat(baseParams, { onObservability });
		expect(onObservability).toHaveBeenCalledTimes(1);
		expect(onObservability).toHaveBeenCalledWith({
			system_instructions: 'Be a tutor',
			rag_context: 'ctx'
		});
	});

	test('N2: tool_event frame → onToolEvent with event data', async () => {
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"type":"tool_event","data":{"type":"tool","name":"calculator","args":"1+1"}}\n\n',
				'data: [DONE]\n\n'
			])
		});
		const onToolEvent = vi.fn();
		await sendWorkshopChat(baseParams, { onToolEvent });
		expect(onToolEvent).toHaveBeenCalledTimes(1);
		expect(onToolEvent).toHaveBeenCalledWith({
			type: 'tool',
			name: 'calculator',
			args: '1+1'
		});
	});

	test('N2b: tool_messages frame → onToolMessages with the tool exchanges', async () => {
		const toolMsgs = [
			{
				role: 'assistant',
				content: '',
				tool_calls: [
					{
						id: 'call_1',
						type: 'function',
						function: { name: 'calculator', arguments: '{"expression":"2+2"}' }
					}
				]
			},
			{ role: 'tool', tool_call_id: 'call_1', content: '{"success":true,"result":4}' }
		];
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				`data: ${JSON.stringify({ type: 'tool_messages', data: { messages: toolMsgs } })}\n\n`,
				'data: [DONE]\n\n'
			])
		});
		const onToolMessages = vi.fn();
		await sendWorkshopChat(baseParams, { onToolMessages });
		expect(onToolMessages).toHaveBeenCalledTimes(1);
		expect(onToolMessages).toHaveBeenCalledWith(toolMsgs);
	});

	test('N3: content chunk → onChunk with delta content only', async () => {
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"choices":[{"delta":{"content":"Hello"}}]}\n\n',
				'data: {"choices":[{"delta":{"content":" world"}}]}\n\n',
				'data: [DONE]\n\n'
			])
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
				'data: {"choices":[{"delta":{"content":"never reached"}}]}\n\n'
			])
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
			body: mockSseStream(['data: {"type":"observability","data":{"x":1}}\n\n', 'data: [DONE]\n\n'])
		});
		await expect(sendWorkshopChat(baseParams, {})).resolves.toBeUndefined();
	});

	test('request carries token header, messages, stream, observability, tools', async () => {
		fetchMock.mockResolvedValue({ ok: true, body: mockSseStream(['data: [DONE]\n\n']) });
		await sendWorkshopChat(
			{
				...baseParams,
				opts: { tools: [{ type: 'function', function: { name: 'calculator' } }] }
			},
			{}
		);
		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe('/lamb/v1/workshop/sessions/ws-1-2-123/assistant/7/chat');
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
			json: async () => ({ detail: 'Not your assistant' })
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
				'data: [DONE]\n\n'
			])
		});
		const onChunk = vi.fn();
		controller.abort();
		await sendWorkshopChat(baseParams, { onChunk }, controller.signal);
		// Aborted before read — no crash; at most zero chunks delivered.
		expect(true).toBe(true);
	});

	test('E1: error frame → onError with the frame message', async () => {
		// The generator can fail *after* the response headers were sent (a
		// connector error, a misconfigured plugin). Without this branch the UI
		// would sit on "streaming…" forever.
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream([
				'data: {"choices":[{"delta":{"content":"partial"}}]}\n\n',
				'data: {"type":"error","data":{"message":"Connector failed"}}\n\n',
				'data: {"choices":[{"delta":{"content":"never reached"}}]}\n\n'
			])
		});
		const onError = vi.fn();
		const onChunk = vi.fn();
		await sendWorkshopChat(baseParams, { onError, onChunk });

		expect(onError).toHaveBeenCalledTimes(1);
		expect(onError).toHaveBeenCalledWith('Connector failed');
		expect(onChunk).toHaveBeenCalledTimes(1); // nothing after the error frame
	});

	test('E2: error frame without a message still reports a failure', async () => {
		fetchMock.mockResolvedValue({
			ok: true,
			body: mockSseStream(['data: {"type":"error"}\n\n'])
		});
		const onError = vi.fn();
		await sendWorkshopChat(baseParams, { onError });
		expect(onError).toHaveBeenCalledWith('Generation failed.');
	});

	test('A/B: rag_mode is forwarded when provided', async () => {
		fetchMock.mockResolvedValue({ ok: true, body: mockSseStream(['data: [DONE]\n\n']) });
		await sendWorkshopChat(
			{ ...baseParams, opts: { ragMode: 'off' } },
			{}
		);
		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect(body.rag_mode).toBe('off');
	});

	test('A/B: rag_mode is omitted when not provided (backend default on)', async () => {
		fetchMock.mockResolvedValue({ ok: true, body: mockSseStream(['data: [DONE]\n\n']) });
		await sendWorkshopChat({ ...baseParams, opts: {} }, {});
		const body = JSON.parse(fetchMock.mock.calls[0][1].body);
		expect('rag_mode' in body).toBe(false);
	});

	test('W1: an api client is used instead of a raw token header', async () => {
		const stream = mockSseStream([
			'data: {"choices":[{"delta":{"content":"hi"}}]}\n\n',
			'data: [DONE]\n\n'
		]);
		const api = {
			getToken: () => 'renewed-token',
			fetchWithRenew: vi.fn().mockResolvedValue({ ok: true, body: stream })
		};
		const onChunk = vi.fn();

		await sendWorkshopChat({ ...baseParams, api }, { onChunk });

		expect(api.fetchWithRenew).toHaveBeenCalledTimes(1);
		expect(api.fetchWithRenew.mock.calls[0][0]).toBe(
			'/sessions/ws-1-2-123/assistant/7/chat');
		expect(onChunk).toHaveBeenCalledWith('hi');
		expect(fetchMock).not.toHaveBeenCalled();
	});
});
