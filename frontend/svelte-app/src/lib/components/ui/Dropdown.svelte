<script>
	import { tick } from 'svelte';

	/**
	 * Generic floating Dropdown panel.
	 *
	 * Usage:
	 * ```svelte
	 * <Dropdown bind:open placement="bottom-end" anchor={triggerEl}>
	 *   {#snippet children({ close })}
	 *     <button onclick={() => close()}>...</button>
	 *   {/snippet}
	 * </Dropdown>
	 * ```
	 *
	 * Two anchoring modes:
	 *  - `anchor={element}`: positioned next to a DOM element (handles
	 *    `placement` directions including auto-flip near the viewport edge).
	 *  - `anchorPoint={ { x, y } }`: positioned at an absolute coordinate
	 *    (use this for right-click context menus). The position is clamped
	 *    so the panel never escapes the viewport.
	 *
	 * Closes on:
	 *  - outside click
	 *  - Escape keydown
	 *  - window scroll / resize
	 *  - `close()` invoked from the `children` snippet
	 */

	/**
	 * @typedef {Object} DropdownProps
	 * @property {boolean} open
	 * @property {() => void} [onclose]
	 * @property {HTMLElement | null} [anchor]
	 * @property {{ x: number, y: number } | null} [anchorPoint]
	 * @property {'bottom-start'|'bottom-end'|'top-start'|'top-end'} [placement]
	 * @property {number} [offset]
	 * @property {boolean} [closeOnEscape]
	 * @property {boolean} [closeOnOutside]
	 * @property {boolean} [closeOnScroll]
	 * @property {boolean} [viewportClamp]
	 * @property {string} [class]
	 * @property {string} [panelClass]
	 * @property {number} [minWidth]
	 * @property {import('svelte').Snippet<[{ close: () => void }]>} children
	 */

	/** @type {DropdownProps} */
	let {
		open,
		onclose,
		anchor = null,
		anchorPoint = null,
		placement = 'bottom-start',
		offset = 4,
		closeOnEscape = true,
		closeOnOutside = true,
		closeOnScroll = true,
		viewportClamp = true,
		class: klass = '',
		panelClass = '',
		minWidth,
		children
	} = $props();

	/** @type {HTMLDivElement | undefined} */
	let panelEl = $state();
	let top = $state(0);
	let left = $state(0);
	let mounted = $state(false);

	function close() {
		if (typeof onclose === 'function') onclose();
	}

	function compute() {
		if (!panelEl) return;
		const vw = window.innerWidth;
		const vh = window.innerHeight;
		const pw = panelEl.offsetWidth;
		const ph = panelEl.offsetHeight;

		let x = 0;
		let y = 0;

		if (anchorPoint) {
			x = anchorPoint.x;
			y = anchorPoint.y;
		} else if (anchor) {
			const r = anchor.getBoundingClientRect();
			const wantTop = placement.startsWith('top');
			const wantEnd = placement.endsWith('end');
			// Position
			y = wantTop ? r.top - ph - offset : r.bottom + offset;
			x = wantEnd ? r.right - pw : r.left;
			// Auto-flip vertically when not enough room
			if (wantTop && y < 0 && r.bottom + offset + ph <= vh) {
				y = r.bottom + offset;
			} else if (!wantTop && y + ph > vh && r.top - offset - ph >= 0) {
				y = r.top - ph - offset;
			}
		}

		if (viewportClamp) {
			const margin = 8;
			if (x + pw > vw - margin) x = Math.max(margin, vw - pw - margin);
			if (x < margin) x = margin;
			if (y + ph > vh - margin) y = Math.max(margin, vh - ph - margin);
			if (y < margin) y = margin;
		}

		top = y;
		left = x;
	}

	$effect(() => {
		if (!open) {
			mounted = false;
			return;
		}
		mounted = true;
		tick().then(() => {
			compute();
		});

		function onWinScroll() {
			if (closeOnScroll) close();
		}
		function onWinResize() {
			compute();
		}
		/** @param {KeyboardEvent} e */
		function onKey(e) {
			if (e.key === 'Escape' && closeOnEscape) {
				e.preventDefault();
				close();
			}
		}
		/** @param {MouseEvent} e */
		function onDocClick(e) {
			if (!closeOnOutside) return;
			const target = e.target;
			if (!(target instanceof Node)) return;
			if (panelEl && panelEl.contains(target)) return;
			if (anchor && anchor.contains(target)) return;
			close();
		}

		window.addEventListener('scroll', onWinScroll, true);
		window.addEventListener('resize', onWinResize);
		document.addEventListener('keydown', onKey);
		// Defer outside-click bind so the click that opened the dropdown
		// doesn't immediately close it.
		const handle = setTimeout(() => {
			document.addEventListener('mousedown', onDocClick);
		}, 0);

		return () => {
			window.removeEventListener('scroll', onWinScroll, true);
			window.removeEventListener('resize', onWinResize);
			document.removeEventListener('keydown', onKey);
			document.removeEventListener('mousedown', onDocClick);
			clearTimeout(handle);
		};
	});
</script>

{#if open && mounted}
	<div
		bind:this={panelEl}
		role="menu"
		class="border-border bg-surface shadow-popover fixed z-[70] rounded-lg border {panelClass} {klass}"
		style:top="{top}px"
		style:left="{left}px"
		style:min-width={minWidth ? `${minWidth}px` : undefined}
	>
		{@render children({ close })}
	</div>
{/if}
