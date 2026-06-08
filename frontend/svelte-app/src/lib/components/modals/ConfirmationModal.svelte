<script>
	import { _, locale } from '$lib/i18n';
	import { AlertCircle, AlertTriangle, Info } from 'lucide-svelte';
	import Modal from '$lib/components/ui/Modal.svelte';
	import Button from '$lib/components/ui/Button.svelte';
	import Banner from '$lib/components/ui/Banner.svelte';
	import Card from '$lib/components/ui/Card.svelte';
	import IconButton from '$lib/components/ui/IconButton.svelte';
	import { X } from 'lucide-svelte';

	/**
	 * ConfirmationModal — design-system implementation.
	 *
	 * External prop API is preserved verbatim so the ~14 existing call sites
	 * keep working. Internals are rebuilt on top of the new `<Modal>` primitive
	 * with the canonical white header, tinted intent icon, and Banner-based
	 * error display.
	 *
	 * For `variant='danger'`, the body always appends a `common.cannotBeUndone`
	 * caption — this enforces the Consistency Contract's copy rule.
	 */

	/**
	 * @typedef {Object} ModalBlocker
	 * @property {string} id
	 * @property {string} name
	 * @property {number|null} [contentCount]
	 * @property {boolean} [removing]
	 */

	let {
		isOpen = $bindable(false),
		isLoading = $bindable(false),
		error = $bindable(''),
		blockers = $bindable(/** @type {ModalBlocker[]} */ ([])),
		blockersTitle = '',
		blockerRemoveLabel = '',
		/** @type {(id: string) => void} */
		onRemoveBlocker = () => {},
		title = '',
		message = '',
		confirmText = '',
		cancelText = '',
		variant = 'danger', // 'danger' | 'warning' | 'info'
		hideConfirm = false,
		onconfirm = () => {},
		oncancel = () => {}
	} = $props();

	let localeLoaded = $derived(!!$locale);

	/** @type {Record<string, any>} */
	const HEADER_ICON = {
		danger: AlertCircle,
		warning: AlertTriangle,
		info: Info
	};

	/** @type {Record<string, string>} */
	const HEADER_ICON_COLOR = {
		danger: 'text-danger',
		warning: 'text-warning',
		info: 'text-info'
	};

	/** @type {Record<string, 'danger'|'primary'>} */
	const CONFIRM_VARIANT = {
		danger: 'danger',
		warning: 'primary',
		info: 'primary'
	};

	let displayTitle = $derived(
		title || (localeLoaded ? $_('common.confirm', { default: 'Confirm' }) : 'Confirm')
	);
	let displayConfirmText = $derived(
		confirmText || (localeLoaded ? $_('common.confirm', { default: 'Confirm' }) : 'Confirm')
	);
	let displayCancelText = $derived(
		cancelText || (localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel')
	);
	let cannotBeUndoneText = $derived(
		localeLoaded
			? $_('common.cannotBeUndone', { default: 'This action cannot be undone.' })
			: 'This action cannot be undone.'
	);
	let blockersHeading = $derived(
		blockersTitle ||
			(localeLoaded ? $_('common.referencingItems', { default: 'Referenced by' }) : 'Referenced by')
	);
	let removeLabel = $derived(
		blockerRemoveLabel || (localeLoaded ? $_('common.remove', { default: 'Remove' }) : 'Remove')
	);
	let itemsLabel = $derived(
		localeLoaded ? $_('common.itemsLowercase', { default: 'items' }) : 'items'
	);

	const HeaderIcon = $derived(HEADER_ICON[variant] || HEADER_ICON.danger);
	const iconColor = $derived(HEADER_ICON_COLOR[variant] || HEADER_ICON_COLOR.danger);
	const confirmVariant = $derived(CONFIRM_VARIANT[variant] || 'danger');

	function handleConfirm() {
		if (isLoading) return;
		onconfirm();
	}

	function handleCancel() {
		if (isLoading) return;
		oncancel();
		isOpen = false;
	}
</script>

<Modal
	open={isOpen}
	onclose={handleCancel}
	size="sm"
	title=""
	showClose={false}
	closeOnEscape={!isLoading}
	closeOnBackdrop={!isLoading}
>
	{#snippet header({ close })}
		<div class="border-border bg-surface flex items-start justify-between gap-3 border-b px-6 py-4">
			<div class="flex min-w-0 flex-1 items-center gap-2">
				<HeaderIcon size={20} class="shrink-0 {iconColor}" aria-hidden="true" />
				<h2 class="type-section-title truncate">{displayTitle}</h2>
			</div>
			<IconButton
				icon={X}
				ariaLabel={displayCancelText}
				tooltip={displayCancelText}
				variant="ghost"
				size="sm"
				inModal
				disabled={isLoading}
				onclick={close}
			/>
		</div>
	{/snippet}

	{#if message}
		<p class="type-body break-words whitespace-pre-line">{message}</p>
	{/if}
	{#if variant === 'danger'}
		<p class="type-caption mt-3">{cannotBeUndoneText}</p>
	{/if}
	{#if error}
		<div class="mt-4">
			<Banner variant="danger" description={error} />
		</div>
	{/if}
	{#if blockers && blockers.length > 0}
		<div class="mt-4">
			<Card padded={false} divided={true} headerClass="px-3 py-2 bg-surface-muted">
				{#snippet header()}
					<p class="type-label">{blockersHeading}</p>
				{/snippet}
				<ul class="divide-border divide-y">
					{#each blockers as b (b.id)}
						<li class="flex items-center justify-between gap-3 px-3 py-2">
							<div class="min-w-0 flex-1">
								<p class="text-text truncate text-sm font-medium" title={b.name}>
									{b.name}
								</p>
								{#if typeof b.contentCount === 'number'}
									<p class="text-text-muted text-xs">{b.contentCount} {itemsLabel}</p>
								{/if}
							</div>
							<Button
								variant="danger-ghost"
								size="sm"
								disabled={!!b.removing || isLoading}
								loading={!!b.removing}
								onclick={() => onRemoveBlocker(b.id)}
							>
								{removeLabel}
							</Button>
						</li>
					{/each}
				</ul>
			</Card>
		</div>
	{/if}

	{#snippet footer({ close })}
		{#if !hideConfirm}
			<Button variant={confirmVariant} loading={isLoading} onclick={handleConfirm}>
				{displayConfirmText}
			</Button>
		{/if}
		<Button variant="secondary" disabled={isLoading} onclick={close}>
			{displayCancelText}
		</Button>
	{/snippet}
</Modal>
