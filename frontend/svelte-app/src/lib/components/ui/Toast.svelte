<script>
	import { fly } from 'svelte/transition';
	import { CheckCircle2, AlertCircle, Info, Loader2, X } from 'lucide-svelte';
	import IconButton from './IconButton.svelte';
	import { toasts, dismiss } from '$lib/stores/toast.js';

	/**
	 * Toast host. Mount once at the root layout. Renders the current toast
	 * stack in the top-right corner with countdown progress bars at the
	 * bottom of each toast.
	 */

	const ICONS = {
		success: CheckCircle2,
		error: AlertCircle,
		info: Info,
		loading: Loader2
	};

	const VARIANT_CLASS = {
		success: 'border-success-border bg-surface text-text',
		error: 'border-danger-border bg-surface text-text',
		info: 'border-info-border bg-surface text-text',
		loading: 'border-border bg-surface text-text'
	};

	const ICON_COLOR = {
		success: 'text-success',
		error: 'text-danger',
		info: 'text-info',
		loading: 'text-text-muted'
	};

	const BAR_COLOR = {
		success: 'bg-success',
		error: 'bg-danger',
		info: 'bg-info',
		loading: 'bg-text-muted'
	};

	/** @param {string} variant */
	function roleFor(variant) {
		return variant === 'error' ? 'alert' : 'status';
	}
</script>

<div
	class="pointer-events-none fixed top-4 right-4 z-[80] flex w-full max-w-sm flex-col gap-2"
	aria-live="polite"
	aria-atomic="false"
>
	{#each $toasts as t (t.id)}
		{@const Icon = ICONS[t.variant] || Info}
		<div
			class="shadow-popover pointer-events-auto overflow-hidden rounded-lg border {VARIANT_CLASS[
				t.variant
			] || VARIANT_CLASS.info}"
			role={roleFor(t.variant)}
			transition:fly={{ x: 24, duration: 200 }}
		>
			<div class="flex items-start gap-3 px-4 py-3">
				<Icon
					size={18}
					class="mt-0.5 shrink-0 {ICON_COLOR[t.variant] || ICON_COLOR.info} {t.variant === 'loading'
						? 'animate-spin'
						: ''}"
					aria-hidden="true"
				/>
				<div class="min-w-0 flex-1">
					<p class="type-body font-medium">{t.title}</p>
					{#if t.description}
						<p class="type-caption mt-0.5">{t.description}</p>
					{/if}
					{#if t.action}
						{@const action = t.action}
						<button
							type="button"
							class="text-brand hover:text-brand-hover mt-2 text-xs font-medium focus:outline-none focus-visible:underline"
							onclick={() => {
								try {
									action.onClick();
								} finally {
									dismiss(t.id);
								}
							}}
						>
							{action.label}
						</button>
					{/if}
				</div>
				<IconButton
					icon={X}
					ariaLabel="Dismiss"
					tooltip="Dismiss"
					variant="ghost"
					size="xs"
					onclick={() => dismiss(t.id)}
				/>
			</div>
			{#if t.duration && Number.isFinite(t.duration) && t.duration > 0}
				<div class="bg-surface-sunken relative h-1 w-full">
					<div
						class="absolute top-0 left-0 h-full {BAR_COLOR[t.variant] || BAR_COLOR.info}"
						style="animation: toast-countdown {t.duration}ms linear forwards;"
					></div>
				</div>
			{/if}
		</div>
	{/each}
</div>
