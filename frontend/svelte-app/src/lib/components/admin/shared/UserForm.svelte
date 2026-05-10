<script>
	import { _ } from '$lib/i18n';

	/**
	 * Shared User Creation/Edit Form
	 * Works for both super-admin and org-admin contexts
	 *
	 * Key differences by role:
	 * - Super-admin: Can select organization, can set role (user/admin)
	 * - Org-admin: Organization is pre-set, cannot set role, has enabled toggle
	 */

	/**
	 * @typedef {Object} NewUserData
	 * @property {string} email
	 * @property {string} name
	 * @property {string} password
	 * @property {string} [role] - Only for super-admin
	 * @property {string} user_type - 'creator' or 'end_user'
	 * @property {number|null} [organization_id] - Only for super-admin
	 * @property {boolean} [enabled] - Only for org-admin
	 */

	/**
	 * @typedef {Object} Organization
	 * @property {number} id
	 * @property {string} name
	 * @property {string} [slug]
	 * @property {boolean} [is_system]
	 */

	/** @type {{
	 *   isOpen?: boolean,
	 *   isSuperAdmin?: boolean,
	 *   newUser: NewUserData,
	 *   organizations?: Organization[],
	 *   isLoadingOrganizations?: boolean,
	 *   organizationsError?: string | null,
	 *   isCreating?: boolean,
	 *   error?: string | null,
	 *   success?: boolean,
	 *   localeLoaded?: boolean,
	 *   onSubmit?: (e: Event) => void,
	 *   onClose?: () => void,
	 *   onUserChange?: (user: NewUserData) => void
	 * }} */
	let {
		isOpen = false,
		isSuperAdmin = false,
		newUser,
		organizations = [],
		isLoadingOrganizations = false,
		organizationsError = null,
		isCreating = false,
		error = null,
		success = false,
		localeLoaded = true,
		onSubmit = () => {},
		onClose = () => {},
		onUserChange = () => {}
	} = $props();

	/**
	 * Handle role change - auto-set user_type for admins (super-admin only)
	 * @param {Event} e
	 */
	function handleRoleChange(e) {
		const target = /** @type {HTMLSelectElement} */ (e.target);
		if (target.value === 'admin') {
			onUserChange({ ...newUser, role: target.value, user_type: 'creator' });
		} else {
			onUserChange({ ...newUser, role: target.value });
		}
	}

	/**
	 * Update a single field
	 * @param {string} field
	 * @param {any} value
	 */
	function updateField(field, value) {
		onUserChange({ ...newUser, [field]: value });
	}
</script>

{#if isOpen}
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex h-full w-full items-center justify-center overflow-y-auto bg-gray-600"
		role="dialog"
		aria-modal="true"
	>
		<div class="relative mx-auto w-full max-w-md rounded-md border bg-white p-5 shadow-lg">
			<div class="mt-3 text-center">
				<h3 class="text-lg leading-6 font-medium text-gray-900">
					{localeLoaded
						? $_('admin.users.create.title', { default: 'Create New User' })
						: 'Create New User'}
				</h3>

				{#if success}
					<div
						class="relative mt-4 rounded border border-green-400 bg-green-100 px-4 py-3 text-green-700"
						role="alert"
					>
						<span class="block sm:inline"
							>{localeLoaded
								? $_('admin.users.create.success', { default: 'User created successfully!' })
								: 'User created successfully!'}</span
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

						<!-- Email Field -->
						<div class="mb-4 text-left">
							<label for="email" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded ? $_('admin.users.create.email', { default: 'Email' }) : 'Email'} *
							</label>
							<input
								type="email"
								id="email"
								name="email"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								value={newUser.email}
								oninput={(e) =>
									updateField('email', /** @type {HTMLInputElement} */ (e.target).value)}
								required
							/>
						</div>

						<!-- Name Field -->
						<div class="mb-4 text-left">
							<label for="name" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded ? $_('admin.users.create.name', { default: 'Name' }) : 'Name'} *
							</label>
							<input
								type="text"
								id="name"
								name="name"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								value={newUser.name}
								oninput={(e) =>
									updateField('name', /** @type {HTMLInputElement} */ (e.target).value)}
								required
							/>
						</div>

						<!-- Password Field -->
						<div class="mb-4 text-left">
							<label for="password" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded
									? $_('admin.users.create.password', { default: 'Password' })
									: 'Password'} *
							</label>
							<input
								type="password"
								id="password"
								name="password"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								value={newUser.password}
								oninput={(e) =>
									updateField('password', /** @type {HTMLInputElement} */ (e.target).value)}
								required
							/>
						</div>

						<!-- Role Field - Super Admin Only -->
						{#if isSuperAdmin}
							<div class="mb-4 text-left">
								<label for="role" class="mb-2 block text-sm font-bold text-gray-700">
									{localeLoaded ? $_('admin.users.create.role', { default: 'Role' }) : 'Role'}
								</label>
								<select
									id="role"
									name="role"
									class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
									value={newUser.role || 'user'}
									onchange={handleRoleChange}
								>
									<option value="user"
										>{localeLoaded
											? $_('admin.users.create.roleUser', { default: 'User' })
											: 'User'}</option
									>
									<option value="admin"
										>{localeLoaded
											? $_('admin.users.create.roleAdmin', { default: 'Admin' })
											: 'Admin'}</option
									>
								</select>
							</div>
						{/if}

						<!-- User Type Field -->
						<div class="mb-4 text-left">
							<label for="user_type" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded
									? $_('admin.users.create.userType', { default: 'User Type' })
									: 'User Type'}
							</label>
							<select
								id="user_type"
								name="user_type"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								value={newUser.user_type || 'creator'}
								onchange={(e) =>
									updateField('user_type', /** @type {HTMLSelectElement} */ (e.target).value)}
								disabled={isSuperAdmin && newUser.role === 'admin'}
							>
								<option value="creator"
									>{localeLoaded
										? $_('admin.users.create.typeCreator', {
												default: 'Creator (Can create assistants)'
											})
										: 'Creator (Can create assistants)'}</option
								>
								<option value="end_user"
									>{localeLoaded
										? $_('admin.users.create.typeEndUser', {
												default: 'End User (Redirects to Open WebUI)'
											})
										: 'End User (Redirects to Open WebUI)'}</option
								>
							</select>
							{#if isSuperAdmin && newUser.role === 'admin'}
								<p class="mt-1 text-xs text-gray-500">
									{localeLoaded
										? $_('admin.users.create.adminAutoCreator', {
												default: 'Admin users are automatically creators'
											})
										: 'Admin users are automatically creators'}
								</p>
							{/if}
						</div>

						<!-- Organization Field - Super Admin Only -->
						{#if isSuperAdmin}
							<div class="mb-4 text-left">
								<label for="organization" class="mb-2 block text-sm font-bold text-gray-700">
									{localeLoaded
										? $_('admin.users.create.organization', { default: 'Organization' })
										: 'Organization'}
								</label>
								{#if isLoadingOrganizations}
									<div class="text-sm text-gray-500">
										{localeLoaded ? $_('common.loading', { default: 'Loading...' }) : 'Loading...'}
									</div>
								{:else if organizationsError}
									<div class="text-sm text-red-500">{organizationsError}</div>
								{:else}
									<select
										id="organization"
										name="organization_id"
										class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
										value={newUser.organization_id ?? ''}
										onchange={(e) => {
											const val = /** @type {HTMLSelectElement} */ (e.target).value;
											updateField('organization_id', val ? parseInt(val, 10) : null);
										}}
									>
										<option value=""
											>{localeLoaded
												? $_('admin.users.create.selectOrg', {
														default: 'Select an organization (optional)'
													})
												: 'Select an organization (optional)'}</option
										>
										{#each organizations as org}
											<option value={org.id}>
												{org.name}
												{#if org.is_system}
													(System)
												{/if}
											</option>
										{/each}
									</select>
								{/if}
								<p class="mt-1 text-xs text-gray-500 italic">
									{localeLoaded
										? $_('admin.users.create.orgHelp', {
												default:
													'If no organization is selected, the user will be assigned to the system organization by default.'
											})
										: 'If no organization is selected, the user will be assigned to the system organization by default.'}
								</p>
							</div>
						{/if}

						<!-- Enabled Checkbox - Org Admin Only -->
						{#if !isSuperAdmin}
							<div class="mb-6 text-left">
								<div class="flex items-center">
									<input
										type="checkbox"
										id="enabled"
										name="enabled"
										checked={newUser.enabled !== false}
										onchange={(e) =>
											updateField('enabled', /** @type {HTMLInputElement} */ (e.target).checked)}
										class="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
									/>
									<label for="enabled" class="ml-2 block text-sm text-gray-900">
										{localeLoaded
											? $_('admin.users.create.enabled', { default: 'User enabled' })
											: 'User enabled'}
									</label>
								</div>
							</div>
						{/if}

						<!-- Action Buttons -->
						<div class="mt-6 flex items-center justify-between">
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
								disabled={isCreating}
							>
								{isCreating
									? localeLoaded
										? $_('admin.users.create.creating', { default: 'Creating...' })
										: 'Creating...'
									: localeLoaded
										? $_('admin.users.create.create', { default: 'Create User' })
										: 'Create User'}
							</button>
						</div>
					</form>
				{/if}
			</div>
		</div>
	</div>
{/if}
