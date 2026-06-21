<script>
	import { _, locale } from '$lib/i18n';

	// --- Props ---
	let {
		isOpen = $bindable(false),
		title = '',
		message = '',
		variant = 'success', // 'success' | 'error' | 'info'
		okText = '',
		onclose = () => {}
	} = $props();

	// --- Locale Ready State ---
	let localeLoaded = $derived(!!$locale);

	// --- Computed values for variant styling ---
	/** @type {Record<string, {headerBg: string, headerBorder: string, iconColor: string, titleColor: string, buttonBg: string, buttonRing: string}>} */
	const variantStyles = {
		success: {
			headerBg: 'bg-green-50',
			headerBorder: 'border-green-200',
			iconColor: 'text-green-600',
			titleColor: 'text-green-900',
			buttonBg: 'bg-green-600 hover:bg-green-700',
			buttonRing: 'focus:ring-green-500'
		},
		error: {
			headerBg: 'bg-red-50',
			headerBorder: 'border-red-200',
			iconColor: 'text-red-600',
			titleColor: 'text-red-900',
			buttonBg: 'bg-red-600 hover:bg-red-700',
			buttonRing: 'focus:ring-red-500'
		},
		info: {
			headerBg: 'bg-blue-50',
			headerBorder: 'border-blue-200',
			iconColor: 'text-blue-600',
			titleColor: 'text-blue-900',
			buttonBg: 'bg-blue-600 hover:bg-blue-700',
			buttonRing: 'focus:ring-blue-500'
		}
	};

	let styles = $derived(variantStyles[variant] || variantStyles.info);

	// --- Default text values ---
	let displayTitle = $derived(
		title ||
			(variant === 'success'
				? localeLoaded
					? $_('common.success', { default: 'Success' })
					: 'Success'
				: variant === 'error'
					? localeLoaded
						? $_('common.error', { default: 'Error' })
						: 'Error'
					: localeLoaded
						? $_('common.info', { default: 'Info' })
						: 'Info')
	);
	let displayOkText = $derived(
		okText || (localeLoaded ? $_('common.ok', { default: 'OK' }) : 'OK')
	);

	// --- Functions ---
	function handleClose() {
		onclose();
		isOpen = false;
	}

	function handleOverlayClick() {
		handleClose();
	}

	/** @param {KeyboardEvent} event */
	function handleKeydown(event) {
		if (!isOpen) return;
		if (event.key === 'Escape') {
			handleClose();
		}
	}
</script>

<svelte:window onkeydown={handleKeydown} />

{#if isOpen}
	<!-- Modal Overlay -->
	<div
		class="bg-opacity-75 fixed inset-0 z-40 bg-gray-500 transition-opacity"
		onclick={handleOverlayClick}
		aria-hidden="true"
	></div>

	<!-- Modal Panel -->
	<div class="fixed inset-0 z-50 flex items-center justify-center p-4">
		<div
			class="relative mx-2 w-full max-w-md overflow-hidden rounded-lg border border-gray-300 bg-white shadow-xl"
			role="alert"
			aria-labelledby="modal-title-notification"
		>
			<!-- Modal Header -->
			<div
				class="flex items-center border-b px-4 py-3 sm:px-6 {styles.headerBg} {styles.headerBorder}"
			>
				{#if variant === 'success'}
					<svg
						class="mr-2 h-6 w-6 {styles.iconColor}"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						aria-hidden="true"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
						/>
					</svg>
				{:else if variant === 'error'}
					<svg
						class="mr-2 h-6 w-6 {styles.iconColor}"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						aria-hidden="true"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
						/>
					</svg>
				{:else}
					<svg
						class="mr-2 h-6 w-6 {styles.iconColor}"
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						aria-hidden="true"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
						/>
					</svg>
				{/if}
				<h3 class="text-lg leading-6 font-medium {styles.titleColor}" id="modal-title-notification">
					{displayTitle}
				</h3>
			</div>

			<!-- Modal Body -->
			<div class="px-4 py-5 sm:p-6">
				<p class="text-sm break-words whitespace-pre-line text-gray-700">
					{message}
				</p>
			</div>

			<!-- Modal Footer -->
			<div class="flex justify-end border-t border-gray-200 bg-gray-50 px-4 py-3 sm:px-6">
				<button
					type="button"
					class="inline-flex w-full justify-center rounded-md border border-transparent px-4 py-2 text-base font-medium text-white shadow-sm focus:ring-2 focus:ring-offset-2 focus:outline-none sm:w-auto sm:text-sm {styles.buttonBg} {styles.buttonRing}"
					onclick={handleClose}
				>
					{displayOkText}
				</button>
			</div>
		</div>
	</div>
{/if}
