<script>
	import { onMount, tick } from 'svelte';
	import { fade, scale } from 'svelte/transition';
	import { X } from 'lucide-svelte';
	import IconButton from './IconButton.svelte';

	/**
	 * Canonical Modal primitive.
	 *
	 * Sizes: sm (max-w-md) | md (max-w-lg) | lg (max-w-2xl) | xl (max-w-3xl) | xxl (max-w-5xl)
	 *
	 * Header / body / footer slots receive `{ close }` so they can wire their
	 * own dismiss buttons. The default header (used when no `header` snippet
	 * is passed) renders `title` and a top-right close button.
	 *
	 * Behaviors:
	 *  - backdrop click → close (when `closeOnBackdrop` is true)
	 *  - Escape → close (when `closeOnEscape` is true)
	 *  - body scroll-lock while open
	 *  - focus trap (Tab / Shift+Tab cycle inside the panel)
	 *  - on close, focus is restored to the opener
	 */

	/**
	 * @typedef {Object} ModalProps
	 * @property {boolean} open
	 * @property {() => void} onclose
	 * @property {'sm'|'md'|'lg'|'xl'|'xxl'} [size]
	 * @property {string} [title]
	 * @property {string} [labelledBy] optional id; defaults to internal id
	 * @property {boolean} [closeOnBackdrop]
	 * @property {boolean} [closeOnEscape]
	 * @property {boolean} [showClose] show the default top-right close button
	 * @property {string} [closeAriaLabel]
	 * @property {string} [class] extra class on the panel
	 * @property {string} [bodyClass] extra class on the body container
	 * @property {import('svelte').Snippet<[{ close: () => void }]>} [header]
	 * @property {import('svelte').Snippet<[{ close: () => void }]>} [children]
	 * @property {import('svelte').Snippet<[{ close: () => void }]>} [footer]
	 */

	/** @type {ModalProps} */
	let {
		open,
		onclose,
		size = 'md',
		title,
		labelledBy,
		closeOnBackdrop = true,
		closeOnEscape = true,
		showClose = true,
		closeAriaLabel = 'Close',
		class: klass = '',
		bodyClass = '',
		header,
		children,
		footer
	} = $props();

	const id = `modal-${Math.random().toString(36).slice(2, 9)}`;
	const titleId = $derived(labelledBy || `${id}-title`);

	const SIZES = {
		sm: 'max-w-md',
		md: 'max-w-lg',
		lg: 'max-w-2xl',
		xl: 'max-w-3xl',
		xxl: 'max-w-5xl',
		full: 'max-w-[min(96rem,95vw)]'
	};

	/** @type {HTMLDivElement | undefined} */
	let panelEl = $state();
	/** @type {Element | null} */
	let previouslyFocused = null;

	function close() {
		if (typeof onclose === 'function') onclose();
	}

	function getFocusable() {
		if (!panelEl) return [];
		const sel =
			'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';
		return Array.from(panelEl.querySelectorAll(sel)).filter(
			(el) => !el.hasAttribute('aria-hidden')
		);
	}

	/** @param {KeyboardEvent} e */
	function onKeydown(e) {
		if (!open) return;
		if (e.key === 'Escape' && closeOnEscape) {
			e.preventDefault();
			close();
			return;
		}
		if (e.key === 'Tab') {
			const focusables = getFocusable();
			if (focusables.length === 0) {
				e.preventDefault();
				panelEl?.focus();
				return;
			}
			const first = focusables[0];
			const last = focusables[focusables.length - 1];
			const active = document.activeElement;
			if (e.shiftKey && active === first) {
				e.preventDefault();
				/** @type {HTMLElement} */ (last).focus();
			} else if (!e.shiftKey && active === last) {
				e.preventDefault();
				/** @type {HTMLElement} */ (first).focus();
			}
		}
	}

	/** @param {MouseEvent} e */
	function onBackdrop(e) {
		// Only close when the click lands on the overlay itself (not bubbled
		// from the panel or its descendants).
		if (closeOnBackdrop && e.target === e.currentTarget) close();
	}

	$effect(() => {
		if (!open) return;
		if (typeof document === 'undefined') return;

		previouslyFocused = document.activeElement;
		const prevOverflow = document.body.style.overflow;
		document.body.style.overflow = 'hidden';

		tick().then(() => {
			const focusables = getFocusable();
			const first = /** @type {HTMLElement | undefined} */ (focusables[0]);
			(first || panelEl)?.focus();
		});

		return () => {
			document.body.style.overflow = prevOverflow;
			if (previouslyFocused instanceof HTMLElement) {
				previouslyFocused.focus();
			}
		};
	});

	onMount(() => {
		// Nothing global to set up — keydown is bound on svelte:window below.
	});
</script>

<svelte:window onkeydown={onKeydown} />

{#if open}
	<!-- Overlay: backdrop + click-outside zone. Single positioned layer so
	     clicks on the empty space around the panel reliably close the modal. -->
	<div
		class="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/40 p-4 backdrop-blur-[1px] sm:p-6"
		role="presentation"
		onclick={onBackdrop}
		transition:fade={{ duration: 200 }}
	>
		<div
			bind:this={panelEl}
			role="dialog"
			aria-modal="true"
			aria-labelledby={title || header ? titleId : undefined}
			tabindex="-1"
			class="border-border bg-surface shadow-modal flex max-h-[calc(100vh_-_2rem)] w-full flex-col rounded-xl border focus:outline-none sm:max-h-[calc(100vh_-_3rem)] {SIZES[
				size
			] || SIZES.md} {klass}"
			transition:scale={{ duration: 200, start: 0.96, opacity: 0 }}
		>
			<!-- Header (shrink-0) -->
			{#if header}
				<div class="shrink-0">{@render header({ close })}</div>
			{:else if title || showClose}
				<div
					class="border-border flex shrink-0 items-start justify-between gap-3 border-b px-6 py-4"
				>
					<h2 id={titleId} class="type-section-title min-w-0 flex-1 truncate">
						{title ?? ''}
					</h2>
					{#if showClose}
						<IconButton
							icon={X}
							ariaLabel={closeAriaLabel}
							tooltip={closeAriaLabel}
							variant="ghost"
							size="sm"
							onclick={close}
							inModal
						/>
					{/if}
				</div>
			{/if}

			<!-- Body (flex-1, scrolls) -->
			<div class="min-h-0 flex-1 overflow-y-auto px-6 py-5 {bodyClass}">
				{@render children?.({ close })}
			</div>

			<!-- Footer (shrink-0) -->
			{#if footer}
				<div
					class="border-border bg-surface-muted flex shrink-0 flex-row-reverse items-center gap-2 border-t px-6 py-4"
				>
					{@render footer({ close })}
				</div>
			{/if}
		</div>
	</div>
{/if}
