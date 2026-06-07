<script>
	import { onMount } from 'svelte';
	import {
		getScenarios,
		createScenario,
		deleteScenario,
		runTests,
		getRuns,
		evaluateRun,
		getEvaluations
	} from '$lib/services/testService';
	import { _ } from 'svelte-i18n';
	import ConfirmationModal from '$lib/components/modals/ConfirmationModal.svelte';

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

	// --- Delete Scenario Confirmation Modal ---
	let showDeleteScenarioModal = $state(false);
	/** @type {number | null} */
	let scenarioToDelete = $state(null);

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
				getEvaluations(assistantId)
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
				expected_behavior: newExpected
			});
			showAddForm = false;
			newTitle = '';
			newMessage = '';
			newExpected = '';
			await loadData();
		} catch (e) {
			error = e.message;
		}
	}

	async function handleDeleteScenario(scenarioId) {
		scenarioToDelete = scenarioId;
		showDeleteScenarioModal = true;
	}

	async function confirmDeleteScenario() {
		if (!scenarioToDelete) return;
		showDeleteScenarioModal = false;
		const id = scenarioToDelete;
		scenarioToDelete = null;
		try {
			await deleteScenario(assistantId, id);
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
				notes: evalNotes
			});
			evaluatingRunId = null;
			evalVerdict = '';
			evalNotes = '';
			await loadData();
		} catch (e) {
			error = e.message;
		}
	}

	function getEvalForRun(runId) {
		return evaluations.find((e) => e.test_run_id === runId);
	}

	function getScenarioTitle(scenarioId) {
		const s = scenarios.find((s) => s.id === scenarioId);
		return s ? s.title : scenarioId?.slice(0, 8) || 'Ad-hoc';
	}

	function toggleRunDetail(runId) {
		expandedRunId = expandedRunId === runId ? null : runId;
	}

	const TYPE_BADGES = {
		single_turn: { label: 'Normal', color: 'bg-blue-100 text-blue-700' },
		multi_turn: { label: 'Multi', color: 'bg-purple-100 text-purple-700' },
		adversarial: { label: 'Adversarial', color: 'bg-red-100 text-red-700' }
	};

	const VERDICT_BADGES = {
		good: { label: '👍 Good', color: 'bg-green-100 text-green-700' },
		bad: { label: '👎 Bad', color: 'bg-red-100 text-red-700' },
		mixed: { label: '🤔 Mixed', color: 'bg-yellow-100 text-yellow-700' }
	};
</script>

<div class="space-y-6 px-6 py-4">
	{#if error}
		<div class="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
			{error}
			<button class="ml-2 underline" onclick={() => (error = '')}>dismiss</button>
		</div>
	{/if}

	{#if loading}
		<p class="text-gray-500">Loading tests...</p>
	{:else}
		<!-- Scenarios Section -->
		<div>
			<div class="mb-3 flex items-center justify-between">
				<h3 class="text-lg font-semibold text-gray-800">
					Test Scenarios ({scenarios.length})
				</h3>
				<div class="flex gap-2">
					<button
						onclick={() => (showAddForm = !showAddForm)}
						class="rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-700 hover:bg-blue-100"
					>
						+ Add Scenario
					</button>
				</div>
			</div>

			{#if showAddForm}
				<div class="mb-4 space-y-3 rounded-lg border bg-gray-50 p-4">
					<input
						bind:value={newTitle}
						placeholder="Title (e.g., 'Basic question about topic')"
						class="w-full rounded border px-3 py-2 text-sm"
					/>
					<textarea
						bind:value={newMessage}
						placeholder="Student message / test prompt"
						rows="2"
						class="w-full rounded border px-3 py-2 text-sm"
					></textarea>
					<div class="flex gap-3">
						<select bind:value={newType} class="rounded border px-3 py-2 text-sm">
							<option value="single_turn">Normal</option>
							<option value="multi_turn">Multi-turn</option>
							<option value="adversarial">Adversarial</option>
						</select>
						<input
							bind:value={newExpected}
							placeholder="Expected behavior (optional)"
							class="flex-1 rounded border px-3 py-2 text-sm"
						/>
					</div>
					<div class="flex gap-2">
						<button
							onclick={handleAddScenario}
							class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700"
						>
							Add
						</button>
						<button
							onclick={() => (showAddForm = false)}
							class="rounded bg-gray-200 px-3 py-1.5 text-sm hover:bg-gray-300"
						>
							Cancel
						</button>
					</div>
				</div>
			{/if}

			{#if scenarios.length === 0}
				<p class="text-sm text-gray-400 italic">
					No test scenarios yet. Add some or let the agent generate them.
				</p>
			{:else}
				<div class="overflow-hidden rounded-lg border">
					<table class="w-full text-sm">
						<thead class="bg-gray-50">
							<tr>
								<th class="px-4 py-2 text-left font-medium text-gray-600">Title</th>
								<th class="px-4 py-2 text-left font-medium text-gray-600">Type</th>
								<th class="px-4 py-2 text-left font-medium text-gray-600">Message</th>
								<th class="px-4 py-2 text-right font-medium text-gray-600">Actions</th>
							</tr>
						</thead>
						<tbody>
							{#each scenarios as s}
								<tr class="border-t hover:bg-gray-50">
									<td class="px-4 py-2 font-medium">{s.title}</td>
									<td class="px-4 py-2">
										<span
											class="rounded px-2 py-0.5 text-xs {(
												TYPE_BADGES[s.scenario_type] || TYPE_BADGES.single_turn
											).color}"
											>{(TYPE_BADGES[s.scenario_type] || TYPE_BADGES.single_turn).label}</span
										>
									</td>
									<td class="max-w-[300px] truncate px-4 py-2 text-gray-500">
										{s.messages?.[0]?.content || ''}
									</td>
									<td class="px-4 py-2 text-right">
										<button
											onclick={() => handleRunSingle(s.id, false)}
											disabled={running}
											class="mr-2 text-xs text-blue-600 hover:underline disabled:opacity-50"
											title="Run with real LLM">▶ Run</button
										>
										<button
											onclick={() => handleRunSingle(s.id, true)}
											disabled={running}
											class="mr-2 text-xs text-purple-600 hover:underline disabled:opacity-50"
											title="Debug bypass (zero tokens)">🔍 Debug</button
										>
										<button
											onclick={() => handleDeleteScenario(s.id)}
											class="text-xs text-red-500 hover:underline">✕</button
										>
									</td>
								</tr>
							{/each}
						</tbody>
					</table>
				</div>

				<div class="mt-3 flex gap-2">
					<button
						onclick={() => handleRunAll(false)}
						disabled={running || scenarios.length === 0}
						class="rounded-md border border-green-200 bg-green-50 px-3 py-1.5 text-sm font-medium text-green-700 hover:bg-green-100 disabled:opacity-50"
					>
						{running ? '⏳ Running...' : '▶ Run All'}
					</button>
					<button
						onclick={() => handleRunAll(true)}
						disabled={running || scenarios.length === 0}
						class="rounded-md border border-purple-200 bg-purple-50 px-3 py-1.5 text-sm font-medium text-purple-700 hover:bg-purple-100 disabled:opacity-50"
					>
						{running ? '⏳ Running...' : '🔍 Debug All (bypass)'}
					</button>
					<button
						onclick={() => onLaunchSkill('test-and-evaluate')}
						class="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-sm font-medium text-emerald-700 hover:bg-emerald-100"
					>
						🤖 Test & Evaluate with Agent
					</button>
				</div>
			{/if}
		</div>

		<!-- Test Runs Section -->
		{#if runs.length > 0}
			<div>
				<h3 class="mb-3 text-lg font-semibold text-gray-800">
					Test Runs ({runs.length})
				</h3>
				<div class="space-y-2">
					{#each runs as run}
						{@const evalResult = getEvalForRun(run.id)}
						<div class="overflow-hidden rounded-lg border">
							<div
								class="flex cursor-pointer items-center justify-between bg-gray-50 px-4 py-2 hover:bg-gray-100"
								role="button"
								tabindex="0"
								onclick={() => toggleRunDetail(run.id)}
								onkeydown={(e) => {
									if (e.key === 'Enter') toggleRunDetail(run.id);
								}}
							>
								<div class="flex items-center gap-3 text-sm">
									<span class="font-medium">{getScenarioTitle(run.scenario_id)}</span>
									<span class="text-gray-400">{run.model_used}</span>
									<span class="text-gray-400">{run.token_usage?.total_tokens || 0} tok</span>
									<span class="text-gray-400">{Math.round(run.elapsed_ms || 0)}ms</span>
									{#if evalResult}
										{@const vb = VERDICT_BADGES[evalResult.verdict] || {}}
										<span class="rounded px-2 py-0.5 text-xs {vb.color}">{vb.label}</span>
									{/if}
								</div>
								<div class="flex items-center gap-2">
									{#if !evalResult}
										<button
											onclick={(e) => {
												e.stopPropagation();
												evaluatingRunId = run.id;
											}}
											class="text-xs text-blue-600 hover:underline"
										>
											Evaluate
										</button>
									{/if}
									<span class="text-xs text-gray-400">{expandedRunId === run.id ? '▼' : '▶'}</span>
								</div>
							</div>

							{#if expandedRunId === run.id}
								<div class="space-y-2 border-t bg-white px-4 py-3 text-sm">
									<div>
										<span class="font-medium text-gray-600">Input:</span>
										<div
											class="mt-1 rounded bg-blue-50 p-2 font-mono text-xs whitespace-pre-wrap text-gray-700"
										>
											{run.input_messages?.map((m) => `[${m.role}] ${m.content}`).join('\n') || ''}
										</div>
									</div>
									<div>
										<span class="font-medium text-gray-600">Response:</span>
										<div
											class="mt-1 max-h-[300px] overflow-y-auto rounded bg-green-50 p-2 text-xs whitespace-pre-wrap text-gray-700"
										>
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
			<dialog
				open
				class="fixed inset-0 z-50 m-0 h-full max-h-none w-full max-w-none bg-transparent p-0"
			>
				<div class="fixed inset-0 flex items-center justify-center bg-black/30">
					<form
						method="dialog"
						class="w-96 space-y-3 rounded-lg bg-white p-6 shadow-xl"
						onsubmit={(e) => {
							e.preventDefault();
							handleEvaluate();
						}}
					>
						<h3 class="text-lg font-semibold">Evaluate Test Run</h3>
						<div class="flex gap-2">
							{#each ['good', 'bad', 'mixed'] as v}
								{@const vb = VERDICT_BADGES[v]}
								<button
									type="button"
									onclick={() => (evalVerdict = v)}
									class="flex-1 rounded border px-3 py-2 text-sm {evalVerdict === v
										? 'ring-2 ring-blue-400'
										: ''} {vb.color}"
								>
									{vb.label}
								</button>
							{/each}
						</div>
						<textarea
							bind:value={evalNotes}
							placeholder="Notes (optional)"
							rows="2"
							class="w-full rounded border px-3 py-2 text-sm"
						></textarea>
						<div class="flex justify-end gap-2">
							<button
								type="button"
								onclick={() => {
									evaluatingRunId = null;
									evalVerdict = '';
									evalNotes = '';
								}}
								class="rounded bg-gray-200 px-3 py-1.5 text-sm hover:bg-gray-300">Cancel</button
							>
							<button
								type="submit"
								disabled={!evalVerdict}
								class="rounded bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
							>
								Submit
							</button>
						</div>
					</form>
				</div>
			</dialog>
		{/if}
	{/if}
</div>

<!-- Delete Scenario Confirmation Modal -->
<ConfirmationModal
    bind:isOpen={showDeleteScenarioModal}
    title="Delete Test Scenario"
    message="Are you sure you want to delete this test scenario? This action cannot be undone."
    confirmText="Delete"
    variant="danger"
    onconfirm={confirmDeleteScenario}
    oncancel={() => { showDeleteScenarioModal = false; scenarioToDelete = null; }}
/>
