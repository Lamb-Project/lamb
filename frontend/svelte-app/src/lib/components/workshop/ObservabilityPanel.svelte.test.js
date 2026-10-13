// src/lib/components/workshop/ObservabilityPanel.svelte.test.js
import { describe, test, expect, beforeAll } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
import { waitLocale } from 'svelte-i18n';
import { setupI18n } from '$lib/i18n';
import ObservabilityPanel from './ObservabilityPanel.svelte';

beforeAll(async () => {
	setupI18n();
	await waitLocale();
});

const sampleObs = {
	system_instructions: 'You are a helpful tutor.',
	rag_context: 'Fraction context…',
	retrieved_sources: [
		{ document_id: 'd1', chunk_id: 'c1', similarity: 0.91, content: 'Fractions are parts of a whole.' },
	],
	final_llm_messages: [
		{ role: 'system', content: 'You are a helpful tutor.' },
		{ role: 'user', content: 'What is 1/2 + 1/4?' },
	],
};

describe('ObservabilityPanel — renders observability data', () => {
	test('C1: renders RAG context, sources and the LLM message list', () => {
		render(ObservabilityPanel, {
			props: { obsData: sampleObs, toolEvents: [] },
		});
		// The stored system prompt is surfaced in its own block.
		expect(screen.getByText('Active instructions')).toBeInTheDocument();
		expect(screen.getByText('Retrieved context')).toBeInTheDocument();
		expect(screen.getByText(/Fraction context/)).toBeInTheDocument();
		// source row includes normalized similarity (0.910) and content
		expect(screen.getByText(/0\.910/)).toBeInTheDocument();
		expect(screen.getByText(/Fractions are parts of a whole/)).toBeInTheDocument();
		// No request_body → the final message list is used as the fallback.
		expect(screen.getByText('Messages sent to LLM')).toBeInTheDocument();
		expect(screen.getByText(/What is 1\/2 \+ 1\/4\?/)).toBeInTheDocument();
	});

	test('C2: renders tool timeline from toolEvents', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: null,
				toolEvents: [
					{ type: 'thinking' },
					{ type: 'tool', name: 'calculator', args: '1+1' },
					{ type: 'tool_done', name: 'calculator', success: true },
					{ type: 'tool_done', name: 'kb_query', success: false },
				],
			},
		});
		expect(screen.getByText('Tool calls')).toBeInTheDocument();
		expect(screen.getAllByText('calculator').length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText('kb_query')).toBeInTheDocument();
		expect(screen.getByText('failed')).toBeInTheDocument();
		expect(screen.getByText('1+1')).toBeInTheDocument();
	});

	test('C3: empty state placeholder when no data', () => {
		render(ObservabilityPanel, { props: { obsData: null, toolEvents: [] } });
		expect(screen.getByText(/Nothing to observe yet/)).toBeInTheDocument();
	});
	test('RAG section hidden when no rag context or sources', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: { system_instructions: 'hi', final_llm_messages: [], retrieved_sources: [] },
				toolEvents: [],
			},
		});
		expect(screen.queryByText('Retrieved context')).not.toBeInTheDocument();
	});

	test('C4: renders the full request body (model/tools/messages) sent to the LLM', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: {
					request_body: {
						model: 'gpt-4o-mini',
						tools: [
							{ type: 'function', function: { name: 'calculator', description: 'Evaluate a mathematical expression' } },
						],
						messages: [
							{ role: 'system', content: 'You are a helpful assistant.' },
							{
								role: 'assistant',
								content: null,
								tool_calls: [{ id: 'call_calc_1', type: 'function', function: { name: 'calculator', arguments: '{"expression":"123*456"}' } }],
							},
							{ role: 'tool', tool_call_id: 'call_calc_1', content: '56088' },
						],
					},
				},
				toolEvents: [],
			},
		});
		// Single request section, model shown in the header.
		expect(screen.getByText('Sent to the model')).toBeInTheDocument();
		expect(screen.getAllByText('gpt-4o-mini').length).toBeGreaterThanOrEqual(1);
		// It renders model + tools + messages as separate raw blocks.
		expect(screen.getAllByText('model').length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText('tools')).toBeInTheDocument();
		expect(screen.getByText(/messages \(3\)/)).toBeInTheDocument();
		// The raw JSON includes the calculator tool and the tool_calls structure.
		// "calculator" appears in both the tools block and the messages block.
		expect(screen.getAllByText(/"calculator"/).length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText(/"tool_calls"/)).toBeInTheDocument();
		expect(screen.getByText(/"call_calc_1"/)).toBeInTheDocument();
	});

	test('C5: full request body is shown by default with no toggle', () => {
		const { container } = render(ObservabilityPanel, {
			props: {
				obsData: {
					request_body: {
						model: 'gpt-4o-mini',
						tools: [
							{ type: 'function', function: { name: 'calculator', description: 'Evaluate a mathematical expression' } },
						],
						messages: [
							{
								role: 'assistant',
								content: null,
								tool_calls: [{ id: 'c1', function: { name: 'calculator', arguments: '{"expression":"1+1"}' } }],
							},
						],
					},
				},
				toolEvents: [],
			},
		});

		// No "View raw JSON" toggle button anymore.
		expect(screen.queryByRole('button', { name: /View raw JSON/ })).not.toBeInTheDocument();
		// The tools/messages are immediately rendered.
		// "calculator" appears in both the tools block and the messages block.
		expect(screen.getAllByText(/"calculator"/).length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText(/"tool_calls"/)).toBeInTheDocument();
		expect(screen.queryByText(/"call_calc_1"/)).not.toBeInTheDocument();
	});

	test('C6: shows "No tools defined" when the request has no tools', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: {
					request_body: {
						model: 'gpt-4o-mini',
						tools: [],
						messages: [{ role: 'user', content: 'hi' }],
					},
				},
				toolEvents: [],
			},
		});
		expect(screen.getByText('Sent to the model')).toBeInTheDocument();
		expect(screen.getByText('No tools defined.')).toBeInTheDocument();
	});

	test('C8: renders multiple retrieved sources that share an empty chunk_id', () => {
		// simple_rag emits document_id/chunk_id as "" for plain-text chunks, so
		// several sources can share the same key. Keying the each block on
		// chunk_id crashed the whole panel (each_key_duplicate) and aborted the
		// SSE stream before [DONE], leaving the chat stuck at "streaming…".
		render(ObservabilityPanel, {
			props: {
				obsData: {
					rag_context: 'ctx',
					retrieved_sources: [
						{ document_id: '', chunk_id: '', similarity: 0.7, content: 'First excerpt' },
						{ document_id: '', chunk_id: '', similarity: 0.6, content: 'Second excerpt' },
					],
					final_llm_messages: [],
				},
				toolEvents: [],
			},
		});
		expect(screen.getByText(/First excerpt/)).toBeInTheDocument();
		expect(screen.getByText(/Second excerpt/)).toBeInTheDocument();
	});

	test('C7: explains a missing system prompt when none is set', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: {
					system_instructions: '',
					request_body: {
						model: 'gpt-4o-mini',
						tools: [],
						messages: [{ role: 'user', content: 'Hello' }],
					},
				},
				toolEvents: [],
			},
		});
		// The empty system prompt is called out so a missing system prompt is explained,
		// rather than silently showing a request with no role:system message.
		expect(screen.getByText('Active instructions')).toBeInTheDocument();
		expect(screen.getByText(/None set on this assistant/)).toBeInTheDocument();
	});
});

// ── D1 / D2 / D3 additions ────────────────────────────────────────────────

const requestFrame = {
	phase: 'request',
	rag_mode: 'on',
	system_instructions: 'You are a helpful tutor.',
	rag_context: 'Fraction context…',
	retrieved_sources: [
		{ similarity: 0.9, content: 'Fractions are parts of a whole.' },
	],
	request_body: {
		model: 'gpt-4o-mini',
		tools: [{ type: 'function', function: { name: 'calculator' } }],
		messages: [{ role: 'user', content: 'What is a fraction?' }],
	},
};

const resultFrame = {
	phase: 'result',
	rag_mode: 'on',
	final_llm_messages: [{ role: 'assistant', content: 'A fraction is…' }],
	request_body: {
		model: 'gpt-4o-mini',
		tools: [],
		messages: [
			{ role: 'user', content: 'What is a fraction?' },
			{ role: 'assistant', content: 'A fraction is…' },
		],
	},
};

describe('ObservabilityPanel — D1 phase routing', () => {
	test('P1: a request frame renders the "about to be sent" view', () => {
		render(ObservabilityPanel, {
			props: { obsRequest: requestFrame, obsData: null, toolEvents: [] },
		});
		expect(screen.getByTestId('panel-request')).toBeInTheDocument();
		expect(screen.getByText('About to be sent')).toBeInTheDocument();
		expect(screen.queryByTestId('panel-result')).not.toBeInTheDocument();
	});

	test('P2: request and result frames render side by side', () => {
		render(ObservabilityPanel, {
			props: { obsRequest: requestFrame, obsData: resultFrame, toolEvents: [] },
		});
		expect(screen.getByTestId('panel-request')).toBeInTheDocument();
		expect(screen.getByTestId('panel-result')).toBeInTheDocument();
		expect(screen.getByText('About to be sent')).toBeInTheDocument();
		expect(screen.getByText('Sent to the model')).toBeInTheDocument();
	});

	test('P3: a phase-less frame is treated as the result (back-compat)', () => {
		render(ObservabilityPanel, {
			props: { obsData: sampleObs, toolEvents: [] },
		});
		expect(screen.queryByTestId('panel-request')).not.toBeInTheDocument();
		expect(screen.getByText('Messages sent to LLM')).toBeInTheDocument();
	});
});

describe('ObservabilityPanel — D2 per-step views', () => {
	test('S1: the document registry is explained in teaching terms', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: null,
				step: 2,
				documents: [
					{
						original_filename: 'fractions.md',
						document_count: 45,
						file_size: 2048,
						status: 'completed',
						plugin_params: { chunk_size: 1000, chunk_overlap: 200 },
					},
				],
			},
		});
		expect(screen.getByTestId('panel-document')).toBeInTheDocument();
		expect(screen.getByText('How your document was split')).toBeInTheDocument();
		expect(screen.getByText('fractions.md')).toBeInTheDocument();
		expect(screen.getByText(/45 chunks/)).toBeInTheDocument();
		expect(screen.getByText(/chunk size 1000/)).toBeInTheDocument();
		expect(screen.getByText(/overlap 200/)).toBeInTheDocument();
		expect(screen.getByText(/2\.0 KB/)).toBeInTheDocument();
	});

	test('S2: step 4 shows the tool definitions that will be sent', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: null,
				step: 4,
				toolDefinitions: [{ type: 'function', function: { name: 'kb_query' } }],
			},
		});
		expect(screen.getByTestId('panel-tools')).toBeInTheDocument();
		expect(screen.getByText(/"kb_query"/)).toBeInTheDocument();
	});

	test('S3: an empty tool selection is explained, not left blank', () => {
		render(ObservabilityPanel, {
			props: { obsData: null, step: 4, toolDefinitions: [] },
		});
		expect(screen.getByText(/No tools selected/)).toBeInTheDocument();
	});

	test('S4: the panel still renders with no chat data at all', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: null,
				step: 3,
				toolEvents: [],
			},
		});
		// Nothing step-specific yet → the honest empty state (never a crash).
		expect(screen.getByText(/Nothing to observe yet/)).toBeInTheDocument();
	});
});

describe('ObservabilityPanel — D3 rag mode badge', () => {
	test('M1: an "on" turn is badged as on', () => {
		render(ObservabilityPanel, {
			props: { obsData: resultFrame, step: 5, ragMode: 'on' },
		});
		expect(screen.getByTestId('panel-rag-mode')).toHaveTextContent(
			'Knowledge base on');
	});

	test('M2: an "off" turn is badged as off', () => {
		render(ObservabilityPanel, {
			props: {
				obsData: { ...resultFrame, rag_mode: 'off' },
				step: 5,
				ragMode: 'off'
			},
		});
		expect(screen.getByTestId('panel-rag-mode')).toHaveTextContent(
			'Knowledge base off');
	});

	test('M3: no badge outside the chat step', () => {
		render(ObservabilityPanel, {
			props: { obsData: resultFrame, step: 3, ragMode: 'on' },
		});
		expect(screen.queryByTestId('panel-rag-mode')).not.toBeInTheDocument();
	});
});
