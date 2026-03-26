<script>
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { _ } from 'svelte-i18n';
	import { getLambApiUrl } from '$lib/config';

	// Props
	let { 
		assistant = null,
		token = '',
		onClose = () => {},
		onSaved = () => {}
	} = $props();

	// State - ALL must use $state()
	let sharedUsers = $state([]);
	let availableUsers = $state([]);
	let selectedShared = $state([]);
	let selectedAvailable = $state([]);
	let loading = $state(false);
	let saving = $state(false);
	let errorMessage = $state('');
	let successMessage = $state('');
	let searchShared = $state('');
	let searchAvailable = $state('');

	// Computed - filtered lists
	let filteredShared = $derived(
		sharedUsers.filter(user => 
			user.name.toLowerCase().includes(searchShared.toLowerCase()) ||
			user.email.toLowerCase().includes(searchShared.toLowerCase())
		)
	);

	let filteredAvailable = $derived(
		availableUsers.filter(user => 
			user.name.toLowerCase().includes(searchAvailable.toLowerCase()) ||
			user.email.toLowerCase().includes(searchAvailable.toLowerCase())
		)
	);

	// Computed - button disabled states (ensure reactivity)
	let canMoveLeft = $derived(selectedShared.length > 0);
	let canMoveRight = $derived(selectedAvailable.length > 0);
	let canMoveAllLeft = $derived(sharedUsers.length > 0);
	let canMoveAllRight = $derived(availableUsers.length > 0);

	// Load data on mount
	onMount(() => {
		if (browser && assistant) {
			loadData();
		}
	});

	async function loadData() {
		loading = true;
		errorMessage = '';
		
		try {
			// Load both lists in parallel
			const [currentShares, orgUsers] = await Promise.all([
				fetchCurrentShares(),
				fetchOrganizationUsers()
			]);

			// Split org users into shared and available (using email as identifier)
			const sharedUserEmails = new Set(currentShares.map(s => s.user_email));
			
			sharedUsers = orgUsers
				.filter(u => sharedUserEmails.has(u.email))
				.sort((a, b) => a.name.localeCompare(b.name));
			
			availableUsers = orgUsers
				.filter(u => !sharedUserEmails.has(u.email))
				.sort((a, b) => a.name.localeCompare(b.name));

		} catch (error) {
			errorMessage = error.message || 'Failed to load users';
		} finally {
			loading = false;
		}
	}

	async function fetchCurrentShares() {
		const response = await fetch(
			getLambApiUrl(`/creator/lamb/assistant-sharing/shares/${assistant.id}`),
			{
				headers: {
					'Authorization': `Bearer ${token}`
				}
			}
		);

		if (!response.ok) {
			throw new Error('Failed to load current shares');
		}

		return response.json();
	}

	async function fetchOrganizationUsers() {
		const response = await fetch(
			getLambApiUrl('/creator/lamb/assistant-sharing/organization-users'),
			{
				headers: {
					'Authorization': `Bearer ${token}`
				}
			}
		);

		if (response.status === 403) {
			throw new Error('Sharing is not enabled for your organization');
		}

		if (!response.ok) {
			throw new Error('Failed to load organization users');
		}

		return response.json();
	}

	// Move selected available users to shared (using email as identifier)
	function moveToShared() {
		if (selectedAvailable.length === 0) return;
		
		const toMove = availableUsers.filter(u => selectedAvailable.includes(u.email));
		availableUsers = availableUsers.filter(u => !selectedAvailable.includes(u.email));
		sharedUsers = [...sharedUsers, ...toMove].sort((a, b) => a.name.localeCompare(b.name));
		selectedAvailable = [];
	}

	// Move selected shared users to available (using email as identifier)
	function moveToAvailable() {
		if (selectedShared.length === 0) return;
		
		const toMove = sharedUsers.filter(u => selectedShared.includes(u.email));
		sharedUsers = sharedUsers.filter(u => !selectedShared.includes(u.email));
		availableUsers = [...availableUsers, ...toMove].sort((a, b) => a.name.localeCompare(b.name));
		selectedShared = [];
	}

	// Move ALL available to shared
	function moveAllToShared() {
		sharedUsers = [...sharedUsers, ...availableUsers].sort((a, b) => a.name.localeCompare(b.name));
		availableUsers = [];
		selectedAvailable = [];
	}

	// Move ALL shared to available
	function moveAllToAvailable() {
		availableUsers = [...availableUsers, ...sharedUsers].sort((a, b) => a.name.localeCompare(b.name));
		sharedUsers = [];
		selectedShared = [];
	}

	// Save changes
	async function saveChanges() {
		saving = true;
		errorMessage = '';
		successMessage = '';

		try {
			const userEmails = sharedUsers.map(u => u.email);
			
			const response = await fetch(
				getLambApiUrl(`/creator/lamb/assistant-sharing/shares/${assistant.id}`),
				{
					method: 'PUT',
					headers: {
						'Authorization': `Bearer ${token}`,
						'Content-Type': 'application/json'
					},
					body: JSON.stringify({ user_emails: userEmails })
				}
			);

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || 'Failed to save changes');
			}

			successMessage = 'Sharing changes saved successfully!';
			
			// Notify parent and close after short delay
			setTimeout(() => {
				onSaved();
				onClose();
			}, 1000);

		} catch (error) {
			errorMessage = error.message || 'Failed to save changes';
		} finally {
			saving = false;
		}
	}

	// Toggle checkbox selection (using email as identifier)
	function toggleShared(userEmail) {
		if (selectedShared.includes(userEmail)) {
			selectedShared = selectedShared.filter(email => email !== userEmail);
		} else {
			selectedShared = [...selectedShared, userEmail];
		}
		console.log('Selected shared users:', selectedShared);
	}

	function toggleAvailable(userEmail) {
		if (selectedAvailable.includes(userEmail)) {
			selectedAvailable = selectedAvailable.filter(email => email !== userEmail);
		} else {
			selectedAvailable = [...selectedAvailable, userEmail];
		}
		console.log('Selected available users:', selectedAvailable);
	}
</script>

<!-- Modal Overlay -->
<div 
	class="modal-overlay" 
	role="button" 
	tabindex="0"
	onclick={onClose}
	onkeydown={(e) => e.key === 'Escape' && onClose()}
>
	<div 
		class="modal-container" 
		role="dialog"
		aria-modal="true"
		tabindex="-1"
		onclick={(e) => e.stopPropagation()}
		onkeydown={(e) => e.stopPropagation()}
	>
		<div class="modal-header">
			<h2>Manage Shared Users</h2>
			<button class="close-btn" onclick={onClose}>×</button>
		</div>

		{#if loading}
			<div class="loading">Loading users...</div>
		{:else if errorMessage}
			<div class="error-message">{errorMessage}</div>
		{:else}
			<div class="modal-body">
				<!-- Left Panel: Shared Users -->
				<div class="user-panel">
					<h3>Shared Users ({sharedUsers.length})</h3>
					<input
						type="text"
						placeholder="Search shared users..."
						bind:value={searchShared}
						class="search-input"
					/>
					<div class="user-list">
						{#each filteredShared as user (user.email)}
							<label class="user-item">
								<input
									type="checkbox"
									checked={selectedShared.includes(user.email)}
									onchange={() => toggleShared(user.email)}
								/>
								<div class="user-info">
									<div class="user-name">{user.name}</div>
									<div class="user-email">{user.email}</div>
								</div>
							</label>
						{/each}
					</div>
				</div>

				<!-- Middle: Move Buttons (Top to Bottom: <<, <, >, >>) -->
			<div class="move-buttons">
				<button
					class="move-btn move-all-left"
					onclick={moveAllToShared}
					disabled={!canMoveAllRight}
					title="Share with ALL users"
				>
					≪
				</button>
				<button
					class="move-btn move-left"
					onclick={moveToShared}
					disabled={!canMoveRight}
					title="Add selected to shared"
				>
					‹
				</button>
				<button
					class="move-btn move-right"
					onclick={moveToAvailable}
					disabled={!canMoveLeft}
					title="Unshare selected"
				>
					›
				</button>
				<button
					class="move-btn move-all-right"
					onclick={moveAllToAvailable}
					disabled={!canMoveAllLeft}
					title="Unshare ALL"
				>
					≫
				</button>
			</div>

				<!-- Right Panel: Available Users -->
				<div class="user-panel">
					<h3>Available Users ({availableUsers.length})</h3>
					<input
						type="text"
						placeholder="Search available users..."
						bind:value={searchAvailable}
						class="search-input"
					/>
					<div class="user-list">
						{#each filteredAvailable as user (user.email)}
							<label class="user-item">
								<input
									type="checkbox"
									checked={selectedAvailable.includes(user.email)}
									onchange={() => toggleAvailable(user.email)}
								/>
								<div class="user-info">
									<div class="user-name">{user.name}</div>
									<div class="user-email">{user.email}</div>
								</div>
							</label>
						{/each}
					</div>
				</div>
			</div>

			<!-- Footer: Action Buttons -->
			<div class="modal-footer">
				{#if successMessage}
					<div class="success-message">{successMessage}</div>
				{/if}
				
				<div class="action-buttons">
					<button class="btn-cancel" onclick={onClose} disabled={saving}>
						Cancel
					</button>
					<button 
						class="btn-save" 
						onclick={saveChanges}
						disabled={saving}
					>
						{saving ? 'Saving...' : 'Save Changes'}
					</button>
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	.modal-overlay {
		position: fixed;
		top: 0;
		left: 0;
		right: 0;
		bottom: 0;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		z-index: 1000;
	}

	.modal-container {
		background: white;
		border-radius: 8px;
		width: 90%;
		max-width: 1000px;
		max-height: 80vh;
		display: flex;
		flex-direction: column;
		box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
	}

	.modal-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 1.5rem;
		border-bottom: 1px solid #e5e7eb;
	}

	.modal-header h2 {
		margin: 0;
		font-size: 1.5rem;
		font-weight: 600;
	}

	.close-btn {
		background: none;
		border: none;
		font-size: 2rem;
		cursor: pointer;
		color: #6b7280;
		line-height: 1;
		padding: 0;
		width: 2rem;
		height: 2rem;
	}

	.close-btn:hover {
		color: #374151;
	}

	.modal-body {
		display: grid;
		grid-template-columns: 1fr auto 1fr;
		gap: 1.5rem;
		padding: 1.5rem;
		overflow: auto;
		flex: 1;
	}

	.user-panel {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.user-panel h3 {
		margin: 0;
		font-size: 1.125rem;
		font-weight: 600;
		color: #374151;
	}

	.search-input {
		padding: 0.5rem;
		border: 1px solid #d1d5db;
		border-radius: 4px;
		font-size: 0.875rem;
	}

	.user-list {
		border: 1px solid #d1d5db;
		border-radius: 4px;
		overflow-y: auto;
		flex: 1;
		min-height: 300px;
		max-height: 400px;
	}

	.user-item {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding: 0.75rem;
		border-bottom: 1px solid #f3f4f6;
		cursor: pointer;
		transition: background 0.15s;
	}

	.user-item:hover {
		background: #f9fafb;
	}

	.user-item:last-child {
		border-bottom: none;
	}

	.user-item input[type="checkbox"] {
		margin-top: 0.25rem;
		cursor: pointer;
	}

	.user-info {
		flex: 1;
		min-width: 0;
	}

	.user-name {
		font-weight: 500;
		color: #111827;
		margin-bottom: 0.25rem;
	}

	.user-email {
		font-size: 0.875rem;
		color: #6b7280;
		word-break: break-all;
	}

	.move-buttons {
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 0.5rem;
		padding-top: 2.5rem;
	}

	.move-btn {
		width: 2.5rem;
		height: 2.5rem;
		border: 1px solid #d1d5db;
		background: white;
		border-radius: 4px;
		cursor: pointer;
		font-size: 1.25rem;
		font-weight: bold;
		transition: all 0.15s;
		color: #374151;
	}

	.move-btn:hover:not(:disabled) {
		background: #f3f4f6;
		border-color: #9ca3af;
	}

	.move-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	/* Color coding like Ollama modal */
	.move-all-right {
		background: #dc2626;
		color: white;
		border-color: #dc2626;
	}

	.move-all-right:hover:not(:disabled) {
		background: #b91c1c;
	}

	.move-right {
		background: #ef4444;
		color: white;
		border-color: #ef4444;
	}

	.move-right:hover:not(:disabled) {
		background: #dc2626;
	}

	.move-left {
		background: #93c5fd;
		color: white;
		border-color: #93c5fd;
	}

	.move-left:hover:not(:disabled) {
		background: #60a5fa;
	}

	.move-all-left {
		background: #3b82f6;
		color: white;
		border-color: #3b82f6;
	}

	.move-all-left:hover:not(:disabled) {
		background: #2563eb;
	}

	.modal-footer {
		padding: 1.5rem;
		border-top: 1px solid #e5e7eb;
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.action-buttons {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}

	.btn-cancel, .btn-save {
		padding: 0.5rem 1.5rem;
		border-radius: 4px;
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s;
	}

	.btn-cancel {
		background: white;
		border: 1px solid #d1d5db;
		color: #374151;
	}

	.btn-cancel:hover:not(:disabled) {
		background: #f9fafb;
	}

	.btn-save {
		background: #3b82f6;
		border: 1px solid #3b82f6;
		color: white;
	}

	.btn-save:hover:not(:disabled) {
		background: #2563eb;
	}

	.btn-cancel:disabled, .btn-save:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.loading {
		padding: 2rem;
		text-align: center;
		color: #6b7280;
	}

	.error-message {
		padding: 1rem;
		background: #fef2f2;
		border: 1px solid #fecaca;
		border-radius: 4px;
		color: #dc2626;
	}

	.success-message {
		padding: 0.75rem;
		background: #f0fdf4;
		border: 1px solid #bbf7d0;
		border-radius: 4px;
		color: #16a34a;
		text-align: center;
	}
</style>

