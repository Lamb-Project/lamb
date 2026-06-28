<script>
	import { CheckCircle2 } from 'lucide-svelte';

	/**
	 * Horizontal Stepper — numbered circles connected by lines.
	 *
	 * Current step: brand-colored solid circle with white number.
	 * Completed step: brand-colored ring with CheckCircle2 icon, clickable
	 *   when `onJump` is supplied.
	 * Future step: neutral circle, disabled.
	 *
	 * On `mobileCollapsed`, renders a single-line summary "Step n of total: label"
	 * at viewport widths below `sm`.
	 */

	/**
	 * @typedef {Object} StepperStep
	 * @property {string} key
	 * @property {string} label
	 */

	/**
	 * @typedef {Object} StepperProps
	 * @property {StepperStep[]} steps
	 * @property {number} current        1-based current step
	 * @property {Set<string>|string[]} [completed]   keys of completed steps
	 * @property {(key: string, index: number) => void} [onJump]
	 * @property {boolean} [mobileCollapsed]
	 * @property {string} [class]
	 * @property {string} [ariaLabel]
	 */

	/** @type {StepperProps} */
	let {
		steps = [],
		current = 1,
		completed = new Set(),
		onJump,
		mobileCollapsed = true,
		class: klass = '',
		ariaLabel
	} = $props();

	const completedSet = $derived(
		completed instanceof Set ? completed : new Set(Array.isArray(completed) ? completed : [])
	);

	/** @param {StepperStep} step @param {number} idx */
	function isCompleted(step, idx) {
		return completedSet.has(step.key) || idx + 1 < current;
	}

	/** @param {StepperStep} _step @param {number} idx */
	function isCurrent(_step, idx) {
		return idx + 1 === current;
	}

	/** @param {StepperStep} step @param {number} idx */
	function jumpableLabel(step, idx) {
		if (typeof onJump !== 'function') return undefined;
		if (!isCompleted(step, idx)) return undefined;
		return `Go to step: ${step.label}`;
	}

	/** @param {StepperStep} step @param {number} idx */
	function handleJump(step, idx) {
		if (typeof onJump !== 'function') return;
		if (!isCompleted(step, idx)) return;
		onJump(step.key, idx);
	}

	const currentStep = $derived(steps[current - 1]);
</script>

<nav aria-label={ariaLabel ?? 'Progress'} class={klass}>
	{#if mobileCollapsed && currentStep}
		<div class="sm:hidden">
			<p class="type-label">Step {current} of {steps.length}</p>
			<p class="text-text mt-0.5 text-sm font-medium">{currentStep.label}</p>
			<div class="rounded-pill bg-surface-sunken mt-2 h-1.5 w-full">
				<div
					class="rounded-pill bg-brand h-full transition-all"
					style="width: {Math.round((current / Math.max(steps.length, 1)) * 100)}%"
				></div>
			</div>
		</div>
	{/if}

	<ol class="{mobileCollapsed ? 'hidden sm:flex' : 'flex'} items-center gap-2">
		{#each steps as step, i (step.key)}
			{@const done = isCompleted(step, i)}
			{@const here = isCurrent(step, i)}
			{@const clickable = done && typeof onJump === 'function'}
			<li class="flex flex-1 items-center gap-2">
				<button
					type="button"
					disabled={!clickable}
					onclick={() => handleJump(step, i)}
					aria-label={jumpableLabel(step, i)}
					aria-current={here ? 'step' : undefined}
					class="group inline-flex items-center gap-2 rounded-md focus:outline-none focus-visible:shadow-[var(--shadow-focus)] {clickable
						? 'cursor-pointer'
						: 'cursor-default'}"
				>
					<span
						class="inline-flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold transition-colors {here
							? 'border-brand bg-brand text-brand-fg'
							: done
								? 'border-brand bg-brand-subtle text-brand'
								: 'border-border-strong bg-surface text-text-muted'}"
					>
						{#if done && !here}
							<CheckCircle2 size={14} aria-hidden="true" />
						{:else}
							{i + 1}
						{/if}
					</span>
					<span
						class="hidden text-sm font-medium md:inline {here
							? 'text-text'
							: done
								? 'text-text group-hover:text-brand'
								: 'text-text-muted'}"
					>
						{step.label}
					</span>
				</button>
				{#if i < steps.length - 1}
					<span class="h-px flex-1 {i + 1 < current ? 'bg-brand' : 'bg-border'}" aria-hidden="true"
					></span>
				{/if}
			</li>
		{/each}
	</ol>
</nav>
