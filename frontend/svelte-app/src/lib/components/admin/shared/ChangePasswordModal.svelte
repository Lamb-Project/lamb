<script>
	import { _ } from '$lib/i18n';

	/**
	 * Shared Change Password Modal
	 * Works for both super-admin and org-admin contexts
	 */

	/**
	 * @typedef {Object} PasswordChangeData
	 * @property {string} [email]
	 * @property {string} [user_name]
	 * @property {string} [user_email]
	 * @property {number|null} [user_id]
	 * @property {string} new_password
	 */

	/** @type {{
	 *   isOpen?: boolean,
	 *   userName?: string,
	 *   userEmail?: string,
	 *   newPassword?: string,
	 *   isChanging?: boolean,
	 *   error?: string | null,
	 *   success?: boolean,
	 *   localeLoaded?: boolean,
	 *   onSubmit?: (e: Event) => void,
	 *   onClose?: () => void,
	 *   onPasswordChange?: (password: string) => void
	 * }} */
	let {
		isOpen = false,
		userName = '',
		userEmail = '',
		newPassword = '',
		isChanging = false,
		error = null,
		success = false,
		localeLoaded = true,
		onSubmit = () => {},
		onClose = () => {},
		onPasswordChange = () => {}
	} = $props();
</script>

{#if isOpen}
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex h-full w-full items-center justify-center overflow-y-auto bg-gray-600"
		role="dialog"
		aria-modal="true"
		onclick={onClose}
	>
		<div class="relative mx-auto w-full max-w-md rounded-md border bg-white p-5 shadow-lg" role="presentation" onclick={(e) => e.stopPropagation()}>
			<div class="mt-3 text-center">
				<h3 class="text-lg leading-6 font-medium text-gray-900">
					{localeLoaded
						? $_('admin.users.password.title', { default: 'Change Password' })
						: 'Change Password'}
				</h3>
				<p class="mt-1 text-sm text-gray-500">
					{localeLoaded
						? $_('admin.users.password.subtitle', { default: 'Set a new password for' })
						: 'Set a new password for'}
					{userName}
					{#if userEmail}
						<span class="block text-gray-400">({userEmail})</span>
					{/if}
				</p>

				{#if success}
					<div
						class="relative mt-4 rounded border border-green-400 bg-green-100 px-4 py-3 text-green-700"
						role="alert"
					>
						<span class="block sm:inline"
							>{localeLoaded
								? $_('admin.users.password.success', { default: 'Password changed successfully!' })
								: 'Password changed successfully!'}</span
						>
					</div>
				{:else}
					<form class="mt-4" onsubmit={onSubmit}>
						{#if error}
							<div
								class="relative mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
								role="alert"
							>
								<span class="block sm:inline">{error}</span>
							</div>
						{/if}

						<!-- Email field (readonly, for reference) -->
						{#if userEmail}
							<div class="mb-4 text-left">
								<label for="pwd-email" class="mb-2 block text-sm font-bold text-gray-700">
									{localeLoaded ? $_('admin.users.password.email', { default: 'Email' }) : 'Email'}
								</label>
								<input
									type="email"
									id="pwd-email"
									class="w-full appearance-none rounded border bg-gray-100 px-3 py-2 leading-tight text-gray-500 shadow"
									value={userEmail}
									disabled
									readonly
								/>
							</div>
						{/if}

						<div class="mb-6 text-left">
							<label for="pwd-new-password" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded
									? $_('admin.users.password.newPassword', { default: 'New Password' })
									: 'New Password'} *
							</label>
							<input
								type="password"
								id="pwd-new-password"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								value={newPassword}
								oninput={(e) => onPasswordChange(/** @type {HTMLInputElement} */ (e.target).value)}
								required
								autocomplete="new-password"
								minlength="8"
							/>
							<p class="mt-1 text-xs text-gray-500 italic">
								{localeLoaded
									? $_('admin.users.password.hint', {
											default: 'At least 8 characters recommended'
										})
									: 'At least 8 characters recommended'}
							</p>
						</div>

						<div class="flex items-center justify-between">
							<button
								type="button"
								onclick={onClose}
								class="focus:shadow-outline rounded bg-gray-300 px-4 py-2 text-gray-800 hover:bg-gray-400 focus:outline-none"
							>
								{localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'}
							</button>
							<button
								type="submit"
								class="bg-brand focus:shadow-outline rounded px-4 py-2 font-bold text-white focus:outline-none disabled:opacity-50"
								disabled={isChanging}
							>
								{isChanging
									? localeLoaded
										? $_('admin.users.password.changing', { default: 'Changing...' })
										: 'Changing...'
									: localeLoaded
										? $_('admin.users.password.change', { default: 'Change Password' })
										: 'Change Password'}
							</button>
						</div>
					</form>
				{/if}
			</div>
		</div>
	</div>
{/if}
