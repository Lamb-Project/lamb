<script>
	import { onMount } from 'svelte';
	import {
		getScenarios, createScenario, deleteScenario,
		runTests, getRuns, evaluateRun, getEvaluations
	} from '$lib/services/testService';
	import { _ } from 'svelte-i18n';

	/** @type {{ assistantId: number, onLaunchSkill?: (skill: string) => void }} */
	let { assistantId, onLaunchSkill = () => {} } = $props();

	/** @type {Array} */
	let scenarios = $state([]);
	/** @type {Array} */
	let runs = $state([]);
	/** @type {Array} */
	let evaluations = $state([]);

	let loading = $state(false);
	let running = $state(false);
	let error = $state('');

	// Add scenario form
	let showAddForm = $state(false);
	let newTitle = $state('');
	let newMessage = $state('');
	let newType = $state('single_turn');
	let newExpected = $state('');

	// Evaluation form
	let evaluatingRunId = $state(null);
	let evalVerdict = $state('');
	let evalNotes = $state('');

	// Expanded run detail
	let expandedRunId = $state(null);

	onMount(async () => {
		await loadData();
	});

	async function loadData() {
		loading = true;
		error = '';
		try {
			[scenarios, runs, evaluations] = await Promise.all([
				getScenarios(assistantId),
				getRuns(assistantId),
				getEvaluations(assistantId),
			]);
		} catch (e) {
			error = e.message;
		}
		loading = false;
	}

	async function handleAddScenario() {
		if (!newTitle.trim() || !newMessage.trim()) return;
		try {
			await createScenario(assistantId, {
				title: newTitle,
				message: newMessage,
				scenario_type: newType,
				expected_behavior: newExpected,
			});
			showAddForm = false;
			newTitle = ''; newMessage = ''; newExpected = '';
			await loadData();
		} catch (e) {
			error = e.message;
		}
	}

	async function handleDeleteScenario(scenarioId) {
		if (!confirm('Delete this test scenario?')) return;
		try {
			await deleteScenario(assistantId, scenarioId);
			await loadData();
		} catch (e) {
			error = e.message;
		}
	}

	async function handleRunAll(bypass = false) {
		running = true;
		error = '';
		try {
			await runTests(assistantId, { bypass });
			await loadData();
		} catch (e) {
			error = e.message;
		}
		running = false;
	}

	async function handleRunSingle(scenarioId, bypass = false) {
		running = true;
		error = '';
		try {
			await runTests(assistantId, { scenarioId, bypass });
			await loadData();
		} catch (e) {
			error = e.message;
		}
		running = false;
	}

	async function handleEvaluate() {
		if (!evaluatingRunId || !evalVerdict) return;
		try {
			await evaluateRun(assistantId, evaluatingRunId, {
				verdict: evalVerdict,
				notes: evalNotes,
			});
			evaluatingRunId = null;
			evalVerdict = ''; evalNotes = '';
			await loadData();
		} catch (e) {
			error = e.message;
		}
	}

	function getEvalForRun(runId) {
		return evaluations.find(e => e.test_run_id === runId);
	}

	function getScenarioTitle(scenarioId) {
		const s = scenarios.find(s => s.id === scenarioId);
		return s ? s.title : scenarioId?.slice(0, 8) || 'Ad-hoc';
	}

	function toggleRunDetail(runId) {
		expandedRunId = expandedRunId === runId ? null : runId;
	}

	const TYPE_BADGES = {
		single_turn: { label: 'Normal', color: 'bg-blue-100 text-blue-700' },
		multi_turn: { label: 'Multi', color: 'bg-purple-100 text-purple-700' },
		adversarial: { label: 'Adversarial', color: 'bg-red-100 text-red-700' },
	};

	const VERDICT_BADGES = {
		good: { label: '👍 Good', color: 'bg-green-100 text-green-700' },
		bad: { label: '👎 Bad', color: 'bg-red-100 text-red-700' },
		mixed: { label: '🤔 Mixed', color: 'bg-yellow-100 text-yellow-700' },
	};
</script>

<div class="px-6 py-4 space-y-6">
	{#if error}
		<div class="bg-red-50 border border-red-200 text-red-700 px-4 py-2 rounded text-sm">
			{error}
			<button class="ml-2 underline" onclick={() => error = ''}>dismiss</button>
		</div>
	{/if}

	{#if loading}
		<p class="text-gray-500">Loading tests...</p>
	{:else}
		<!-- Scenarios Section -->
		<div>
			<div class="flex items-center justify-between mb-3">
				<h3 class="text-lg font-semibold text-gray-800">
					Test Scenarios ({scenarios.length})
				</h3>
				<div class="flex gap-2">
					<button
						onclick={() => showAddForm = !showAddForm}
						class="px-3 py-1.5 text-sm font-medium rounded-md bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200"
					>
						+ Add Scenario
					</button>
				</div>
			</div>

			{#if showAddForm}
				<div class="bg-gray-50 border rounded-lg p-4 mb-4 space-y-3">
					<input bind:value={newTitle} placeholder="Title (e.g., 'Basic question about topic')"
						class="w-full px-3 py-2 border rounded text-sm" />
					<textarea bind:value={newMessage} placeholder="Student message / test prompt"
						rows="2" class="w-full px-3 py-2 border rounded text-sm"></textarea>
					<div class="flex gap-3">
						<select bind:value={newType} class="px-3 py-2 border rounded text-sm">
							<option value="single_turn">Normal</option>
							<option value="multi_turn">Multi-turn</option>
							<option value="adversarial">Adversarial</option>
						</select>
						<input bind:value={newExpected} placeholder="Expected behavior (optional)"
							class="flex-1 px-3 py-2 border rounded text-sm" />
					</div>
					<div class="flex gap-2">
						<button onclick={handleAddScenario}
							class="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700">
							Add
						</button>
						<button onclick={() => showAddForm = false}
							class="px-3 py-1.5 text-sm rounded bg-gray-200 hover:bg-gray-300">
							Cancel
						</button>
					</div>
				</div>
			{/if}

			{#if scenarios.length === 0}
				<p class="text-gray-400 text-sm italic">No test scenarios yet. Add some or let the agent generate them.</p>
			{:else}
				<div class="border rounded-lg overflow-hidden">
					<table class="w-full text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-2 text-left text-gray-600 font-medium">Title</th>
								<th class="px-4 py-2 text-left text-gray-600 font-medium">Type</th>
								<th class="px-4 py-2 text-left text-gray-600 font-medium">Message</th>
								<th class="px-4 py-2 text-right text-gray-600 font-medium">Actions</th>
							</tr>
						</thead>
						<tbody>
							{#each scenarios as s}
								<tr class="border-t hover:bg-gray-50">
									<td class="px-4 py-2 font-medium">{s.title}</td>
									<td class="px-4 py-2">
										<span class="px-2 py-0.5 rounded text-xs {(TYPE_BADGES[s.scenario_type] || TYPE_BADGES.single_turn).color}">{(TYPE_BADGES[s.scenario_type] || TYPE_BADGES.single_turn).label}</span>
									</td>
									<td class="px-4 py-2 text-gray-500 truncate max-w-[300px]">
										{s.messages?.[0]?.content || ''}
									</td>
									<td class="px-4 py-2 text-right">
										<button onclick={() => handleRunSingle(s.id, false)}
											disabled={running}
											class="text-xs text-blue-600 hover:underline disabled:opacity-50 mr-2"
											title="Run with real LLM">▶ Run</button>
										<button onclick={() => handleRunSingle(s.id, true)}
											disabled={running}
											class="text-xs text-purple-600 hover:underline disabled:opacity-50 mr-2"
											title="Debug bypass (zero tokens)">🔍 Debug</button>
										<button onclick={() => handleDeleteScenario(s.id)}
											class="text-xs text-red-500 hover:underline">✕</button>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="flex gap-2 mt-3">
					<button onclick={() => handleRunAll(false)}
						disabled={running || scenarios.length === 0}
						class="px-3 py-1.5 text-sm font-medium rounded-md bg-green-50 text-green-700 hover:bg-green-100 border border-green-200 disabled:opacity-50">
						{running ? '⏳ Running...' : '▶ Run All'}
					</button>
					<button onclick={() => handleRunAll(true)}
						disabled={running || scenarios.length === 0}
						class="px-3 py-1.5 text-sm font-medium rounded-md bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200 disabled:opacity-50">
						{running ? '⏳ Running...' : '🔍 Debug All (bypass)'}
					</button>
					<button onclick={() => onLaunchSkill('test-and-evaluate')}
						class="px-3 py-1.5 text-sm font-medium rounded-md bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200">
						🤖 Test & Evaluate with Agent
					</button>
				</div>
			{/if}
		</div>

		<!-- Test Runs Section -->
		{#if runs.length > 0}
			<div>
				<h3 class="text-lg font-semibold text-gray-800 mb-3">
					Test Runs ({runs.length})
				</h3>
				<div class="space-y-2">
					{#each runs as run}
						{@const evalResult = getEvalForRun(run.id)}
						<div class="border rounded-lg overflow-hidden">
							<div class="flex items-center justify-between px-4 py-2 bg-gray-50 cursor-pointer hover:bg-gray-100"
								role="button" tabindex="0"
								onclick={() => toggleRunDetail(run.id)}
								onkeydown={(e) => { if (e.key === 'Enter') toggleRunDetail(run.id); }}>
								<div class="flex items-center gap-3 text-sm">
									<span class="font-medium">{getScenarioTitle(run.scenario_id)}</span>
									<span class="text-gray-400">{run.model_used}</span>
									<span class="text-gray-400">{run.token_usage?.total_tokens || 0} tok</span>
									<span class="text-gray-400">{Math.round(run.elapsed_ms || 0)}ms</span>
									{#if evalResult}
										{@const vb = VERDICT_BADGES[evalResult.verdict] || {}}
										<span class="px-2 py-0.5 rounded text-xs {vb.color}">{vb.label}</span>
									{/if}
								</div>
								<div class="flex items-center gap-2">
									{#if !evalResult}
										<button onclick={(e) => { e.stopPropagation(); evaluatingRunId = run.id; }}
											class="text-xs text-blue-600 hover:underline">
											Evaluate
										</button>
									{/if}
									<span class="text-gray-400 text-xs">{expandedRunId === run.id ? '▼' : '▶'}</span>
								</div>
							</div>

							{#if expandedRunId === run.id}
								<div class="px-4 py-3 text-sm border-t bg-white space-y-2">
									<div>
										<span class="font-medium text-gray-600">Input:</span>
										<div class="mt-1 p-2 bg-blue-50 rounded text-gray-700 font-mono text-xs whitespace-pre-wrap">
											{run.input_messages?.map(m => `[${m.role}] ${m.content}`).join('\n') || ''}
										</div>
									</div>
									<div>
										<span class="font-medium text-gray-600">Response:</span>
										<div class="mt-1 p-2 bg-green-50 rounded text-gray-700 text-xs whitespace-pre-wrap max-h-[300px] overflow-y-auto">
											{run.response || '(no response)'}
										</div>
									</div>
									{#if evalResult?.notes}
										<div class="text-xs text-gray-500">
											Notes: {evalResult.notes}
										</div>
									{/if}
								</div>
							{/if}
						</div>
					{/each}
				</div>
			</div>
		{/if}

		<!-- Evaluation Modal -->
		{#if evaluatingRunId}
			<!-- svelte-ignore a11y_no_static_element_interactions -->
			<div class="fixed inset-0 bg-black/30 flex items-center justify-center z-50"
				role="dialog" tabindex="-1"
				onclick={() => evaluatingRunId = null}
				onkeydown={(e) => { if (e.key === 'Escape') evaluatingRunId = null; }}>
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="bg-white rounded-lg p-6 w-96 shadow-xl" role="document" onclick={(e) => e.stopPropagation()}>
					<h3 class="text-lg font-semibold mb-4">Evaluate Test Run</h3>
					<div class="space-y-3">
						<div class="flex gap-2">
							{#each ['good', 'bad', 'mixed'] as v}
								{@const vb = VERDICT_BADGES[v]}
								<button
									onclick={() => evalVerdict = v}
									class="flex-1 px-3 py-2 rounded border text-sm {evalVerdict === v ? 'ring-2 ring-blue-400' : ''} {vb.color}">
									{vb.label}
								</button>
							{/each}
						</div>
						<textarea bind:value={evalNotes} placeholder="Notes (optional)"
							rows="2" class="w-full px-3 py-2 border rounded text-sm"></textarea>
						<div class="flex gap-2 justify-end">
							<button onclick={() => { evaluatingRunId = null; evalVerdict = ''; evalNotes = ''; }}
								class="px-3 py-1.5 text-sm rounded bg-gray-200 hover:bg-gray-300">Cancel</button>
							<button onclick={handleEvaluate}
								disabled={!evalVerdict}
								class="px-3 py-1.5 text-sm rounded bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50">
								Submit
							</button>
						</div>
					</div>
				</div>
			</div>
		{/if}
	{/if}
</div>
