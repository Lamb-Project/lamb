<script>
	import { _ } from '$lib/i18n';

	/**
	 * Shared User Action Modal
	 * Handles enable/disable confirmations for both single users and bulk actions
	 * Works for both super-admin and org-admin contexts
	 */

	/**
	 * @typedef {Object} TargetUser
	 * @property {number} id
	 * @property {string} name
	 * @property {string} email
	 */

	/** @type {{
	 *   isOpen?: boolean,
	 *   action?: 'enable' | 'disable',
	 *   isBulk?: boolean,
	 *   targetUser?: TargetUser | null,
	 *   selectedCount?: number,
	 *   isProcessing?: boolean,
	 *   error?: string | null,
	 *   localeLoaded?: boolean,
	 *   onConfirm?: () => void,
	 *   onClose?: () => void
	 * }} */
	let {
		isOpen = false,
		action = 'disable',
		isBulk = false,
		targetUser = null,
		selectedCount = 0,
		isProcessing = false,
		error = null,
		localeLoaded = true,
		onConfirm = () => {},
		onClose = () => {}
	} = $props();

	const isDisable = $derived(action === 'disable');
	const iconColor = $derived(isDisable ? 'text-amber-600' : 'text-green-600');
	const iconBgColor = $derived(isDisable ? 'bg-amber-100' : 'bg-green-100');
	const buttonColor = $derived(
		isDisable ? 'bg-amber-600 hover:bg-amber-700' : 'bg-green-600 hover:bg-green-700'
	);
</script>

{#if isOpen}
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex h-full w-full items-center justify-center overflow-y-auto bg-gray-600"
		role="dialog"
		aria-modal="true"
		onclick={onClose}
	>
		<div
			class="relative mx-auto w-full max-w-md rounded-md border bg-white p-5 shadow-lg"
			role="presentation"
			onclick={(e) => e.stopPropagation()}
		>
			<div class="mt-3">
				<!-- Icon -->
				<div class="mx-auto flex h-12 w-12 items-center justify-center rounded-full {iconBgColor}">
					{#if isDisable}
						<svg class="h-6 w-6 {iconColor}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
							/>
						</svg>
					{:else}
						<svg class="h-6 w-6 {iconColor}" fill="none" viewBox="0 0 24 24" stroke="currentColor">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
							/>
						</svg>
					{/if}
				</div>

				<!-- Title -->
				<h3 class="mt-4 text-center text-lg leading-6 font-medium text-gray-900">
					{#if isBulk}
						{isDisable
							? localeLoaded
								? $_('admin.users.modal.bulkDisableTitle', { default: 'Disable Multiple Users' })
								: 'Disable Multiple Users'
							: localeLoaded
								? $_('admin.users.modal.bulkEnableTitle', { default: 'Enable Multiple Users' })
								: 'Enable Multiple Users'}
					{:else}
						{isDisable
							? localeLoaded
								? $_('admin.users.modal.disableTitle', { default: 'Disable User Account' })
								: 'Disable User Account'
							: localeLoaded
								? $_('admin.users.modal.enableTitle', { default: 'Enable User Account' })
								: 'Enable User Account'}
					{/if}
				</h3>

				<!-- Content -->
				<div class="mt-4 text-center">
					{#if isBulk}
						<p class="text-sm text-gray-600">
							{isDisable
								? localeLoaded
									? $_('admin.users.modal.bulkDisableConfirm', {
											default: 'Are you sure you want to disable {count} user(s)?',
											values: { count: selectedCount }
										})
									: `Are you sure you want to disable ${selectedCount} user(s)?`
								: localeLoaded
									? $_('admin.users.modal.bulkEnableConfirm', {
											default: 'Are you sure you want to enable {count} user(s)?',
											values: { count: selectedCount }
										})
									: `Are you sure you want to enable ${selectedCount} user(s)?`}
						</p>
					{:else if targetUser}
						<p class="text-sm text-gray-600">
							{isDisable
								? localeLoaded
									? $_('admin.users.modal.disableConfirm', {
											default: 'Are you sure you want to disable the account for'
										})
									: 'Are you sure you want to disable the account for'
								: localeLoaded
									? $_('admin.users.modal.enableConfirm', {
											default: 'Are you sure you want to enable the account for'
										})
									: 'Are you sure you want to enable the account for'}
						</p>
						<p class="mt-2 text-base font-semibold text-gray-900">{targetUser.name}</p>
						<p class="mt-1 text-sm text-gray-600">({targetUser.email})</p>
					{/if}

					<div
						class="mt-4 rounded border-l-4 p-3 {isDisable
							? 'border-yellow-400 bg-yellow-50'
							: 'border-green-400 bg-green-50'}"
					>
						<p class="text-sm text-gray-700">
							{#if isDisable}
								<strong>{localeLoaded ? $_('common.note', { default: 'Note' }) : 'Note'}:</strong>
								{localeLoaded
									? $_('admin.users.modal.disableNote', {
											default:
												'Disabled users will not be able to log in, but their resources (assistants, templates, rubrics) will remain accessible to other users.'
										})
									: 'Disabled users will not be able to log in, but their resources (assistants, templates, rubrics) will remain accessible to other users.'}
							{:else}
								{localeLoaded
									? $_('admin.users.modal.enableNote', {
											default: 'Enabled users will be able to log in and access the system.'
										})
									: 'Enabled users will be able to log in and access the system.'}
							{/if}
						</p>
					</div>
				</div>

				{#if error}
					<div
						class="relative mt-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
						role="alert"
					>
						<span class="block sm:inline">{error}</span>
					</div>
				{/if}

				<!-- Actions -->
				<div class="mt-6 flex items-center justify-between gap-3">
					<button
						type="button"
						onclick={onClose}
						class="focus:shadow-outline flex-1 rounded bg-gray-300 px-4 py-2 font-semibold text-gray-800 hover:bg-gray-400 focus:outline-none disabled:opacity-50"
						disabled={isProcessing}
					>
						{localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
					</button>
					<button
						type="button"
						onclick={onConfirm}
						class="flex-1 {buttonColor} focus:shadow-outline rounded px-4 py-2 font-semibold text-white focus:outline-none disabled:opacity-50"
						disabled={isProcessing}
					>
						{#if isProcessing}
							{isDisable
								? localeLoaded
									? $_('admin.users.modal.disabling', { default: 'Disabling...' })
									: 'Disabling...'
								: localeLoaded
									? $_('admin.users.modal.enabling', { default: 'Enabling...' })
									: 'Enabling...'}
						{:else}
							{isDisable
								? localeLoaded
									? $_('admin.users.modal.disableAction', { default: 'Disable' })
									: 'Disable'
								: localeLoaded
									? $_('admin.users.modal.enableAction', { default: 'Enable' })
									: 'Enable'}
							{#if isBulk}
								({selectedCount})
							{/if}
						{/if}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}
