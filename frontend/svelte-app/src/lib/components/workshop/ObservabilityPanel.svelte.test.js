// src/lib/components/workshop/ObservabilityPanel.svelte.test.js
import { describe, test, expect } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import '@testing-library/jest-dom/vitest';
import ObservabilityPanel from './ObservabilityPanel.svelte';

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
		// The stored system prompt is surfaced in the new "System instructions" block.
		expect(screen.getByText('System instructions (configured)')).toBeInTheDocument();
		expect(screen.getByText('Retrieved context')).toBeInTheDocument();
		expect(screen.getByText(/Fraction context/)).toBeInTheDocument();
		// source row includes normalized similarity (0.910) and content
		expect(screen.getByText(/0\.910/)).toBeInTheDocument();
		expect(screen.getByText(/Fractions are parts of a whole/)).toBeInTheDocument();
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
		expect(screen.getByText(/Send a test message/)).toBeInTheDocument();
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
							{ type: 'function', function: { name: 'calculator', description: '计算数学表达式' } },
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
		// Single "Request sent to LLM" section, model shown in the header.
		expect(screen.getByText('Request sent to LLM')).toBeInTheDocument();
		expect(screen.getAllByText('gpt-4o-mini').length).toBeGreaterThanOrEqual(1);
		// It renders model + tools + messages as separate raw blocks.
		expect(screen.getAllByText('model').length).toBeGreaterThanOrEqual(1);
		expect(screen.getByText('tools')).toBeInTheDocument();
		expect(screen.getByText(/messages \(3\)/)).toBeInTheDocument();
		// The raw JSON includes the calculator tool and the tool_calls structure.
		expect(screen.getByText(/"calculator"/)).toBeInTheDocument();
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
							{ type: 'function', function: { name: 'calculator', description: '计算数学表达式' } },
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
		expect(screen.getByText(/"calculator"/)).toBeInTheDocument();
		expect(screen.getByText(/"tool_calls"/)).toBeInTheDocument();
		expect(screen.getByText(/"call_calc_1"/)).not.toBeInTheDocument();
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
		expect(screen.getByText('Request sent to LLM')).toBeInTheDocument();
		expect(screen.getByText('No tools defined.')).toBeInTheDocument();
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
		// The empty system prompt is called out so "system prompt 不见了" is explained,
		// rather than silently showing a request with no role:system message.
		expect(screen.getByText('System instructions (configured)')).toBeInTheDocument();
		expect(screen.getByText(/None set on this assistant/)).toBeInTheDocument();
	});
});