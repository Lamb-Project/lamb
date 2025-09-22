<script>
	import { onMount, onDestroy } from 'svelte';
	import { browser } from '$app/environment';
	import { page } from '$app/stores'; // Import page store to read URL params
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { _ } from '$lib/i18n'; // Assuming i18n setup
	import axios from 'axios';
	import { getApiUrl } from '$lib/config';
	import { user } from '$lib/stores/userStore'; // Import user store for auth token

	// --- State Management ---
	/** @type {'dashboard' | 'users' | 'organizations'} */
	let currentView = $state('users'); // Changed default view to users
	let localeLoaded = $state(true); // Assume loaded for now

	// Current user data for self-disable prevention
	/** @type {any} */
	let currentUserData = $state(null);

	// --- Users Management State ---
	/** @type {Array<any>} */
	let users = $state([]);
	let isLoadingUsers = $state(false);
	/** @type {string | null} */
	let usersError = $state(null);

	// --- Create User Modal State ---
	let isCreateUserModalOpen = $state(false);
	let newUser = $state({
		email: '',
		name: '',
		password: '',
		role: 'user', // Default role
		organization_id: null // Default to no organization selected
	});
	let isCreatingUser = $state(false);
	/** @type {string | null} */
	let createUserError = $state(null);
	let createUserSuccess = $state(false);

	// --- Organizations for User Creation ---
	/** @type {Array<{id: number, name: string, slug: string, is_system: boolean}>} */
	let organizationsForUsers = $state([]);
	let isLoadingOrganizationsForUsers = $state(false);
	/** @type {string | null} */
	let organizationsForUsersError = $state(null);

	// --- Change Password Modal State ---
	let isChangePasswordModalOpen = $state(false);
	let passwordChangeData = $state({
		email: '',
		new_password: ''
	});
	let isChangingPassword = $state(false);
	/** @type {string | null} */
	let changePasswordError = $state(null);
	let changePasswordSuccess = $state(false);
	let selectedUserName = $state('');

	// --- Organizations Management State ---
	/** @type {Array<any>} */
	let organizations = $state([]);
	let isLoadingOrganizations = $state(false);
	/** @type {string | null} */
	let organizationsError = $state(null);

	// --- Create Organization Modal State ---
	let isCreateOrgModalOpen = $state(false);
	let newOrg = $state({
		slug: '',
		name: '',
		admin_user_id: null,
		signup_enabled: false,
		signup_key: '',
		use_system_baseline: true,
		config: {
			version: '1.0',
			setups: {
				default: {
					name: 'Default Setup',
					providers: {},
					knowledge_base: {}
				}
			},
			features: {
				rag_enabled: true,
				mcp_enabled: true,
				lti_publishing: true,
				signup_enabled: false
			},
			limits: {
				usage: {
					tokens_per_month: 1000000,
					max_assistants: 100,
					max_assistants_per_user: 10,
					storage_gb: 10
				}
			}
		}
	});
	let isCreatingOrg = $state(false);
	/** @type {string | null} */
	let createOrgError = $state(null);
	let createOrgSuccess = $state(false);

	// --- System Org Users for Admin Selection ---
	/** @type {Array<{id: number, email: string, name: string, role: string, joined_at: number}>} */
	let systemOrgUsers = $state([]);
	let isLoadingSystemUsers = $state(false);
	/** @type {string | null} */
	let systemUsersError = $state(null);

	// --- View Organization Config Modal State ---
	let isViewConfigModalOpen = $state(false);
	/** @type {any | null} */
	let selectedOrg = $state(null);
	/** @type {any | null} */
	let selectedOrgConfig = $state(null);
	let isLoadingOrgConfig = $state(false);
	/** @type {string | null} */
	let configError = $state(null);

	// --- URL Handling ---
	/** @type {Function|null} */
	let unsubscribePage = null;
	/** @type {Function|null} */
	let unsubscribeUser = null;

	// --- Navigation Functions ---
	function showDashboard() {
		currentView = 'dashboard';
		goto(`${base}/admin`, { replaceState: true });
	}

	function showUsers() {
		currentView = 'users';
		goto(`${base}/admin?view=users`, { replaceState: true });
		// Always fetch users when this view is explicitly selected
		fetchUsers();
	}

	function showOrganizations() {
		currentView = 'organizations';
		goto(`${base}/admin?view=organizations`, { replaceState: true });
		// Always fetch organizations when this view is explicitly selected
		fetchOrganizations();
	}

	// --- Modal Functions ---
	function openCreateUserModal() {
		// Reset form state
		newUser = {
			email: '',
			name: '',
			password: '',
			role: 'user',
			organization_id: null
		};
		createUserError = null;
		createUserSuccess = false;
		isCreateUserModalOpen = true;

		// Fetch organizations for the dropdown
		fetchOrganizationsForUsers();
	}

	function closeCreateUserModal() {
		isCreateUserModalOpen = false;
		// Clear any previous state
		createUserError = null;
	}

	/**
	 * Open the change password modal for a specific user
	 * @param {string} email - User's email
	 * @param {string} name - User's name for display
	 */
	function openChangePasswordModal(email, name) {
		// Reset form state
		passwordChangeData = {
			email: email,
			new_password: ''
		};
		selectedUserName = name;
		changePasswordError = null;
		changePasswordSuccess = false;
		isChangePasswordModalOpen = true;
	}

	function closeChangePasswordModal() {
		isChangePasswordModalOpen = false;
		// Clear any previous state
		changePasswordError = null;
		selectedUserName = '';
	}

	// User enable/disable functions for system admin
	async function toggleUserStatusAdmin(user) {
		const newStatus = !user.enabled;
		const action = newStatus ? 'enable' : 'disable';

		// Prevent users from disabling themselves
		if (currentUserData && currentUserData.email === user.email && !newStatus) {
			alert(
				'You cannot disable your own account. Please ask another administrator to disable your account if needed.'
			);
			return;
		}

		if (!confirm(`Are you sure you want to ${action} ${user.name} (${user.email})?`)) {
			return;
		}

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			const apiUrl = getApiUrl(`/admin/users/${user.id}/status`);
			console.log(
				`${action === 'enable' ? 'Enabling' : 'Disabling'} user ${user.email} at: ${apiUrl}`
			);

			const response = await axios.put(
				apiUrl,
				{
					enabled: newStatus
				},
				{
					headers: {
						Authorization: `Bearer ${token}`,
						'Content-Type': 'application/json'
					}
				}
			);

			console.log(`User ${action} response:`, response.data);

			// Update the user in the local list
			const userIndex = users.findIndex((u) => u.id === user.id);
			if (userIndex !== -1) {
				users[userIndex].enabled = newStatus;
				users = [...users]; // Trigger reactivity
			}

			// Show success message (you could use a toast library here)
			alert(`User ${user.name} has been ${newStatus ? 'enabled' : 'disabled'} successfully.`);
		} catch (err) {
			console.error(`Error ${action}ing user:`, err);

			let errorMessage = `Failed to ${action} user.`;
			if (axios.isAxiosError(err) && err.response?.data?.detail) {
				errorMessage = err.response.data.detail;
			} else if (err instanceof Error) {
				errorMessage = err.message;
			}

			alert(`Error: ${errorMessage}`);
		}
	}

	function openCreateOrgModal() {
		// Reset form state
		newOrg = {
			slug: '',
			name: '',
			admin_user_id: null,
			signup_enabled: false,
			signup_key: '',
			use_system_baseline: true,
			config: {
				version: '1.0',
				setups: {
					default: {
						name: 'Default Setup',
						providers: {},
						knowledge_base: {}
					}
				},
				features: {
					rag_enabled: true,
					mcp_enabled: true,
					lti_publishing: true,
					signup_enabled: false
				},
				limits: {
					usage: {
						tokens_per_month: 1000000,
						max_assistants: 100,
						max_assistants_per_user: 10,
						storage_gb: 10
					}
				}
			}
		};
		createOrgError = null;
		createOrgSuccess = false;
		isCreateOrgModalOpen = true;

		// Fetch system org users for admin selection
		fetchSystemOrgUsers();
	}

	function closeCreateOrgModal() {
		isCreateOrgModalOpen = false;
		// Clear any previous state
		createOrgError = null;
	}

	/**
	 * Open the view configuration modal for a specific organization
	 * @param {any} org - Organization object
	 */
	function openViewConfigModal(org) {
		selectedOrg = org;
		selectedOrgConfig = null;
		configError = null;
		isViewConfigModalOpen = true;
		fetchOrganizationConfig(org.slug);
	}

	function closeViewConfigModal() {
		isViewConfigModalOpen = false;
		selectedOrg = null;
		selectedOrgConfig = null;
		configError = null;
	}

	/**
	 * Navigate to organization admin interface for a specific organization
	 * @param {any} org - Organization object
	 */
	function administerOrganization(org) {
		// Navigate to org-admin with organization parameter
		goto(`${base}/org-admin?org=${org.slug}`);
	}

	// --- Form Handling ---
	/**
	 * @param {Event} e - The form submission event
	 */
	async function handleCreateUser(e) {
		e.preventDefault();

		// Basic form validation
		if (!newUser.email || !newUser.name || !newUser.password) {
			createUserError = 'Please fill in all required fields.';
			return;
		}

		if (!newUser.email.includes('@')) {
			createUserError = 'Please enter a valid email address.';
			return;
		}

		createUserError = null;
		isCreatingUser = true;

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			// Construct form data in URL-encoded format
			const formData = new URLSearchParams();
			formData.append('email', newUser.email);
			formData.append('name', newUser.name);
			formData.append('password', newUser.password);
			formData.append('role', newUser.role);

			// Add organization_id if selected
			if (newUser.organization_id) {
				formData.append('organization_id', String(newUser.organization_id));
			}

			const apiUrl = getApiUrl('/admin/users/create');
			console.log(`Creating user at: ${apiUrl}`);

			const response = await axios.post(apiUrl, formData, {
				headers: {
					Authorization: `Bearer ${token}`,
					'Content-Type': 'application/x-www-form-urlencoded'
				}
			});

			console.log('Create user response:', response.data);

			if (response.data && response.data.success) {
				createUserSuccess = true;
				// Wait 1.5 seconds to show success message, then close modal and refresh list
				setTimeout(() => {
					closeCreateUserModal();
					fetchUsers(); // Refresh the users list
				}, 1500);
			} else {
				throw new Error(response.data.error || 'Failed to create user.');
			}
		} catch (err) {
			console.error('Error creating user:', err);
			if (axios.isAxiosError(err) && err.response?.data?.error) {
				createUserError = err.response.data.error;
			} else if (axios.isAxiosError(err) && err.response?.data?.detail) {
				// Handle validation errors from FastAPI
				if (Array.isArray(err.response.data.detail)) {
					/** @type {Array<{msg: string}>} */
					const details = err.response.data.detail;
					createUserError = details.map((d) => d.msg).join(', ');
				} else {
					createUserError = err.response.data.detail;
				}
			} else if (err instanceof Error) {
				createUserError = err.message;
			} else {
				createUserError = 'An unknown error occurred while creating the user.';
			}
		} finally {
			isCreatingUser = false;
		}
	}

	/**
	 * Handle password change form submission
	 * @param {Event} e - The form submission event
	 */
	async function handleChangePassword(e) {
		e.preventDefault();

		// Basic form validation
		if (!passwordChangeData.new_password) {
			changePasswordError = 'Please enter a new password.';
			return;
		}

		if (passwordChangeData.new_password.length < 8) {
			changePasswordError = 'Password should be at least 8 characters.';
			return;
		}

		changePasswordError = null;
		isChangingPassword = true;

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			// Construct form data in URL-encoded format
			const formData = new URLSearchParams();
			formData.append('email', passwordChangeData.email);
			formData.append('new_password', passwordChangeData.new_password);

			const apiUrl = getApiUrl('/admin/users/update-password');
			console.log(`Changing password at: ${apiUrl}`);

			const response = await axios.post(apiUrl, formData, {
				headers: {
					Authorization: `Bearer ${token}`,
					'Content-Type': 'application/x-www-form-urlencoded'
				}
			});

			console.log('Change password response:', response.data);

			if (response.data && response.data.success) {
				changePasswordSuccess = true;
				// Wait 1.5 seconds to show success message, then close modal
				setTimeout(() => {
					closeChangePasswordModal();
				}, 1500);
			} else {
				throw new Error(
					response.data.error || response.data.message || 'Failed to change password.'
				);
			}
		} catch (err) {
			console.error('Error changing password:', err);
			if (axios.isAxiosError(err) && err.response?.data?.error) {
				changePasswordError = err.response.data.error;
			} else if (axios.isAxiosError(err) && err.response?.data?.detail) {
				// Handle validation errors from FastAPI
				if (Array.isArray(err.response.data.detail)) {
					/** @type {Array<{msg: string}>} */
					const details = err.response.data.detail;
					changePasswordError = details.map((d) => d.msg).join(', ');
				} else {
					changePasswordError = err.response.data.detail;
				}
			} else if (err instanceof Error) {
				changePasswordError = err.message;
			} else {
				changePasswordError = 'An unknown error occurred while changing the password.';
			}
		} finally {
			isChangingPassword = false;
		}
	}

	/**
	 * Handle organization creation form submission
	 * @param {Event} e - The form submission event
	 */
	async function handleCreateOrganization(e) {
		e.preventDefault();

		// Basic form validation
		if (!newOrg.slug || !newOrg.name) {
			createOrgError = 'Please fill in all required fields.';
			return;
		}

		// Validate admin user selection
		if (!newOrg.admin_user_id) {
			createOrgError = 'Please select an admin user for the organization.';
			return;
		}

		// Validate slug format (URL-friendly)
		if (!/^[a-z0-9-]+$/.test(newOrg.slug)) {
			createOrgError = 'Slug must contain only lowercase letters, numbers, and hyphens.';
			return;
		}

		// Validate signup key if signup is enabled
		if (newOrg.signup_enabled && (!newOrg.signup_key || newOrg.signup_key.trim().length < 8)) {
			createOrgError = 'Signup key must be at least 8 characters long when signup is enabled.';
			return;
		}

		// Validate signup key format if provided
		if (newOrg.signup_key && !/^[a-zA-Z0-9_-]+$/.test(newOrg.signup_key)) {
			createOrgError = 'Signup key can only contain letters, numbers, hyphens, and underscores.';
			return;
		}

		createOrgError = null;
		isCreatingOrg = true;

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			// Use the enhanced endpoint with admin assignment
			const apiUrl = getApiUrl('/admin/organizations/enhanced');
			console.log(`Creating organization with admin assignment at: ${apiUrl}`);

			// Prepare the payload
			const payload = {
				slug: newOrg.slug,
				name: newOrg.name,
				admin_user_id: parseInt(newOrg.admin_user_id),
				signup_enabled: newOrg.signup_enabled,
				signup_key: newOrg.signup_enabled ? newOrg.signup_key.trim() : null,
				use_system_baseline: newOrg.use_system_baseline
			};

			console.log('Organization creation payload:', payload);

			const response = await axios.post(apiUrl, payload, {
				headers: {
					Authorization: `Bearer ${token}`,
					'Content-Type': 'application/json'
				}
			});

			console.log('Create organization response:', response.data);

			if (response.data) {
				createOrgSuccess = true;
				// Wait 1.5 seconds to show success message, then close modal and refresh list
				setTimeout(() => {
					closeCreateOrgModal();
					fetchOrganizations(); // Refresh the organizations list
				}, 1500);
			} else {
				throw new Error('Failed to create organization.');
			}
		} catch (err) {
			console.error('Error creating organization:', err);
			if (axios.isAxiosError(err) && err.response?.data?.detail) {
				createOrgError = err.response.data.detail;
			} else if (err instanceof Error) {
				createOrgError = err.message;
			} else {
				createOrgError = 'An unknown error occurred while creating the organization.';
			}
		} finally {
			isCreatingOrg = false;
		}
	}

	// --- Keyboard Event Handlers ---
	function handleKeydown(event) {
		// Handle ESC key to close modals
		if (event.key === 'Escape') {
			if (isCreateOrgModalOpen) {
				closeCreateOrgModal();
			} else if (isViewConfigModalOpen) {
				closeViewConfigModal();
			} else if (isChangePasswordModalOpen) {
				closeChangePasswordModal();
			}
		}
	}

	// --- Lifecycle ---
	onMount(() => {
		console.log('Admin page mounted');

		// Add global keydown listener for ESC key
		document.addEventListener('keydown', handleKeydown);

		// Check if user is logged in and is admin
		unsubscribeUser = user.subscribe((userData) => {
			currentUserData = userData; // Store current user data for self-disable prevention

			if (userData.isLoggedIn) {
				console.log('User is logged in:', userData.email);
				// Check if user is admin (based on role in userData)
				const userRole = userData.data?.role;
				if (userRole === 'admin') {
					console.log('User has admin role, can access admin features');
				} else {
					console.warn("User doesn't have admin role:", userRole);
					// Optionally redirect non-admin users
					// goto(`${base}/`);
				}
			} else {
				console.warn('User not logged in, redirecting...');
				// Redirect to login page
				// goto(`${base}/login`);
			}
		});

		unsubscribePage = page.subscribe((currentPage) => {
			console.log('Admin page store updated:', currentPage.url.searchParams.toString());
			const viewParam = currentPage.url.searchParams.get('view');

			if (viewParam === 'users') {
				console.log("URL indicates 'users' view.");
				currentView = 'users';
				fetchUsers(); // Always fetch when the view is users
			} else if (viewParam === 'organizations') {
				console.log("URL indicates 'organizations' view.");
				currentView = 'organizations';
				fetchOrganizations(); // Always fetch when the view is organizations
			} else {
				console.log("URL indicates 'dashboard' view.");
				currentView = 'dashboard';
			}
		});

		// Initial fetch if needed based on the current view
		if (currentView === 'users') {
			fetchUsers();
		} else if (currentView === 'organizations') {
			fetchOrganizations();
		}
	});

	onDestroy(() => {
		console.log('Admin page unmounting');

		// Remove global keydown listener (only on client)
		if (browser) {
			document.removeEventListener('keydown', handleKeydown);
		}

		if (unsubscribePage) {
			unsubscribePage();
		}
		if (unsubscribeUser) {
			unsubscribeUser();
		}
	});

	// --- Data Fetching ---
	// Get auth token from user store
	function getAuthToken() {
		const userData = $user;
		if (!userData.isLoggedIn || !userData.token) {
			console.error('No authentication token available. User must be logged in.');
			return null;
		}
		return userData.token;
	}

	async function fetchUsers() {
		if (isLoadingUsers) {
			console.log('Already loading users, skipping duplicate request');
			return;
		}

		console.log('Fetching users...');
		isLoadingUsers = true;
		usersError = null;

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			const apiUrl = getApiUrl('/users');
			console.log(`Fetching users from: ${apiUrl}`);

			const response = await axios.get(apiUrl, {
				headers: {
					Authorization: `Bearer ${token}`
				}
			});

			console.log('API Response:', response.data);

			if (response.data && response.data.success) {
				users = response.data.data || [];
				console.log(`Fetched ${users.length} users`);
			} else {
				throw new Error(response.data.error || 'Failed to fetch users.');
			}
		} catch (err) {
			console.error('Error fetching users:', err);
			if (axios.isAxiosError(err) && err.response?.status === 401) {
				usersError = 'Access denied. Admin privileges required.';
			} else if (axios.isAxiosError(err) && err.response?.data?.error) {
				usersError = err.response.data.error;
			} else if (err instanceof Error) {
				usersError = err.message;
			} else {
				usersError = 'An unknown error occurred while fetching users.';
			}
			users = [];
		} finally {
			isLoadingUsers = false;
		}
	}

	async function fetchOrganizations() {
		if (isLoadingOrganizations) {
			console.log('Already loading organizations, skipping duplicate request');
			return;
		}

		console.log('Fetching organizations...');
		isLoadingOrganizations = true;
		organizationsError = null;

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			const apiUrl = getApiUrl('/admin/organizations');
			console.log(`Fetching organizations from: ${apiUrl}`);

			const response = await axios.get(apiUrl, {
				headers: {
					Authorization: `Bearer ${token}`
				}
			});

			console.log('Organizations API Response:', response.data);

			if (response.data && Array.isArray(response.data)) {
				organizations = response.data;
				console.log(`Fetched ${organizations.length} organizations`);
			} else {
				throw new Error('Invalid response format.');
			}
		} catch (err) {
			console.error('Error fetching organizations:', err);
			if (axios.isAxiosError(err) && err.response?.status === 401) {
				organizationsError = 'Access denied. Admin privileges required.';
			} else if (axios.isAxiosError(err) && err.response?.data?.detail) {
				organizationsError = err.response.data.detail;
			} else if (err instanceof Error) {
				organizationsError = err.message;
			} else {
				organizationsError = 'An unknown error occurred while fetching organizations.';
			}
			organizations = [];
		} finally {
			isLoadingOrganizations = false;
		}
	}

	async function fetchSystemOrgUsers() {
		if (isLoadingSystemUsers) {
			console.log('Already loading system users, skipping duplicate request');
			return;
		}

		console.log('Fetching system organization users...');
		isLoadingSystemUsers = true;
		systemUsersError = null;

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			const apiUrl = getApiUrl('/admin/organizations/system/users');
			console.log(`Fetching system users from: ${apiUrl}`);

			const response = await axios.get(apiUrl, {
				headers: {
					Authorization: `Bearer ${token}`
				}
			});

			console.log('System Users API Response:', response.data);

			if (response.data && Array.isArray(response.data)) {
				systemOrgUsers = response.data;
				console.log(`Fetched ${systemOrgUsers.length} system org users`);
			} else {
				throw new Error('Invalid response format.');
			}
		} catch (err) {
			console.error('Error fetching system org users:', err);
			if (axios.isAxiosError(err) && err.response?.status === 401) {
				systemUsersError = 'Access denied. Admin privileges required.';
			} else if (axios.isAxiosError(err) && err.response?.data?.detail) {
				systemUsersError = err.response.data.detail;
			} else if (err instanceof Error) {
				systemUsersError = err.message;
			} else {
				systemUsersError = 'An unknown error occurred while fetching system users.';
			}
			systemOrgUsers = [];
		} finally {
			isLoadingSystemUsers = false;
		}
	}

	async function fetchOrganizationsForUsers() {
		if (isLoadingOrganizationsForUsers) {
			console.log('Already loading organizations for users, skipping duplicate request');
			return;
		}

		console.log('Fetching organizations for user creation...');
		isLoadingOrganizationsForUsers = true;
		organizationsForUsersError = null;

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			const apiUrl = getApiUrl('/admin/organizations/list');
			console.log(`Fetching organizations for users from: ${apiUrl}`);

			const response = await axios.get(apiUrl, {
				headers: {
					Authorization: `Bearer ${token}`
				}
			});

			console.log('Organizations for Users API Response:', response.data);

			if (response.data && response.data.success && Array.isArray(response.data.data)) {
				organizationsForUsers = response.data.data;
				console.log(`Fetched ${organizationsForUsers.length} organizations for user assignment`);
			} else {
				throw new Error('Invalid response format.');
			}
		} catch (err) {
			console.error('Error fetching organizations for users:', err);
			if (axios.isAxiosError(err) && err.response?.status === 401) {
				organizationsForUsersError = 'Access denied. Admin privileges required.';
			} else if (axios.isAxiosError(err) && err.response?.data?.detail) {
				organizationsForUsersError = err.response.data.detail;
			} else if (err instanceof Error) {
				organizationsForUsersError = err.message;
			} else {
				organizationsForUsersError = 'An unknown error occurred while fetching organizations.';
			}
			organizationsForUsers = [];
		} finally {
			isLoadingOrganizationsForUsers = false;
		}
	}

	/**
	 * @param {string} slug - Organization slug
	 */
	async function fetchOrganizationConfig(slug) {
		if (!slug) return;

		isLoadingOrgConfig = true;
		configError = null;

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			const apiUrl = getApiUrl(`/admin/organizations/${slug}/config`);
			console.log(`Fetching organization config from: ${apiUrl}`);

			const response = await axios.get(apiUrl, {
				headers: {
					Authorization: `Bearer ${token}`
				}
			});

			console.log('Organization config response:', response.data);
			selectedOrgConfig = response.data;
		} catch (err) {
			console.error('Error fetching organization config:', err);
			if (axios.isAxiosError(err) && err.response?.data?.detail) {
				configError = err.response.data.detail;
			} else if (err instanceof Error) {
				configError = err.message;
			} else {
				configError = 'An unknown error occurred while fetching configuration.';
			}
		} finally {
			isLoadingOrgConfig = false;
		}
	}

	async function syncSystemOrganization() {
		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			const apiUrl = getApiUrl('/admin/organizations/system/sync');
			console.log(`Syncing system organization at: ${apiUrl}`);

			const response = await axios.post(
				apiUrl,
				{},
				{
					headers: {
						Authorization: `Bearer ${token}`
					}
				}
			);

			console.log('Sync system organization response:', response.data);

			// Refresh organizations list
			fetchOrganizations();

			// Show success message (you might want to add a toast notification here)
			alert('System organization synced successfully!');
		} catch (err) {
			console.error('Error syncing system organization:', err);
			let errorMessage = 'Failed to sync system organization.';

			if (axios.isAxiosError(err) && err.response?.data?.detail) {
				errorMessage = err.response.data.detail;
			} else if (err instanceof Error) {
				errorMessage = err.message;
			}

			alert(`Error: ${errorMessage}`);
		}
	}

	/**
	 * @param {string} slug - Organization slug
	 */
	async function deleteOrganization(slug) {
		if (
			!confirm(
				`Are you sure you want to delete organization '${slug}'? This action cannot be undone.`
			)
		) {
			return;
		}

		try {
			const token = getAuthToken();
			if (!token) {
				throw new Error('Authentication token not found. Please log in again.');
			}

			const apiUrl = getApiUrl(`/admin/organizations/${slug}`);
			console.log(`Deleting organization at: ${apiUrl}`);

			const response = await axios.delete(apiUrl, {
				headers: {
					Authorization: `Bearer ${token}`
				}
			});

			console.log('Delete organization response:', response.data);

			// Refresh organizations list
			fetchOrganizations();

			// Show success message
			alert(`Organization '${slug}' deleted successfully!`);
		} catch (err) {
			console.error('Error deleting organization:', err);
			let errorMessage = 'Failed to delete organization.';

			if (axios.isAxiosError(err) && err.response?.data?.detail) {
				errorMessage = err.response.data.detail;
			} else if (err instanceof Error) {
				errorMessage = err.message;
			}

			alert(`Error: ${errorMessage}`);
		}
	}
</script>

<div class="container mx-auto px-4 py-8">
	<!-- Admin Navigation Tabs -->
	<div class="mb-6 border-b border-gray-200">
		<ul class="-mb-px flex flex-wrap">
			<li class="mr-2">
				<button
					class={`inline-block px-4 py-2 text-sm font-medium ${currentView === 'dashboard' ? 'bg-brand border-brand text-white' : 'hover:text-brand border-transparent text-gray-500'} rounded-t-lg border-b-2`}
					style={currentView === 'dashboard'
						? 'background-color: #2271b3; color: white; border-color: #2271b3;'
						: ''}
					onclick={showDashboard}
					aria-label={localeLoaded
						? $_('admin.tabs.dashboard', { default: 'Dashboard' })
						: 'Dashboard'}
				>
					{localeLoaded ? $_('admin.tabs.dashboard', { default: 'Dashboard' }) : 'Dashboard'}
				</button>
			</li>
			<li class="mr-2">
				<button
					class={`inline-block px-4 py-2 text-sm font-medium ${currentView === 'users' ? 'bg-brand border-brand text-white' : 'hover:text-brand border-transparent text-gray-500'} rounded-t-lg border-b-2`}
					style={currentView === 'users'
						? 'background-color: #2271b3; color: white; border-color: #2271b3;'
						: ''}
					onclick={showUsers}
					aria-label={localeLoaded
						? $_('admin.tabs.users', { default: 'User Management' })
						: 'User Management'}
				>
					{localeLoaded
						? $_('admin.tabs.users', { default: 'User Management' })
						: 'User Management'}
				</button>
			</li>
			<li class="mr-2">
				<button
					class={`inline-block px-4 py-2 text-sm font-medium ${currentView === 'organizations' ? 'bg-brand border-brand text-white' : 'hover:text-brand border-transparent text-gray-500'} rounded-t-lg border-b-2`}
					style={currentView === 'organizations'
						? 'background-color: #2271b3; color: white; border-color: #2271b3;'
						: ''}
					onclick={showOrganizations}
					aria-label={localeLoaded
						? $_('admin.tabs.organizations', { default: 'Organizations' })
						: 'Organizations'}
				>
					{localeLoaded
						? $_('admin.tabs.organizations', { default: 'Organizations' })
						: 'Organizations'}
				</button>
			</li>
		</ul>
	</div>

	<!-- View Content -->
	{#if currentView === 'dashboard'}
		<div>
			<h1 class="mb-6 text-2xl font-semibold text-gray-800">
				{localeLoaded
					? $_('admin.dashboard.title', { default: 'Admin Dashboard' })
					: 'Admin Dashboard'}
			</h1>
			<p class="text-gray-600">
				{localeLoaded
					? $_('admin.dashboard.welcome', {
							default: 'Welcome to the administration area. Use the tabs above to navigate.'
						})
					: 'Welcome to the administration area. Use the tabs above to navigate.'}
			</p>
		</div>
	{:else if currentView === 'users'}
		<!-- Users Management View -->
		<div class="mb-6 flex items-center justify-between">
			<h1 class="text-2xl font-semibold text-gray-800">
				{localeLoaded ? $_('admin.users.title', { default: 'User Management' }) : 'User Management'}
			</h1>
			<button
				onclick={openCreateUserModal}
				class="bg-brand hover:bg-brand-hover focus:ring-brand focus:ring-opacity-50 rounded px-4 py-2 text-white focus:ring-2 focus:outline-none"
				style="background-color: #2271b3; color: white;"
				aria-label={localeLoaded
					? $_('admin.users.actions.create', { default: 'Create User' })
					: 'Create User'}
			>
				{localeLoaded
					? $_('admin.users.actions.create', { default: 'Create User' })
					: 'Create User'}
			</button>
		</div>

		{#if isLoadingUsers}
			<p class="py-4 text-center text-gray-500">
				{localeLoaded
					? $_('admin.users.loading', { default: 'Loading users...' })
					: 'Loading users...'}
			</p>
		{:else if usersError}
			<div
				class="relative mb-6 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
				role="alert"
			>
				<strong class="font-bold"
					>{localeLoaded ? $_('admin.users.errorTitle', { default: 'Error:' }) : 'Error:'}</strong
				>
				<span class="block sm:inline"> {usersError}</span>
			</div>
			<!-- Button to retry fetching -->
			<div class="text-center">
				<button
					onclick={fetchUsers}
					class="bg-brand hover:bg-brand-hover focus:ring-brand focus:ring-opacity-50 rounded px-4 py-2 text-white focus:ring-2 focus:outline-none"
					style="background-color: #2271b3; color: white;"
				>
					{localeLoaded ? $_('admin.users.retry', { default: 'Retry' }) : 'Retry'}
				</button>
			</div>
		{:else if users.length === 0}
			<p class="py-4 text-center text-gray-500">
				{localeLoaded
					? $_('admin.users.noUsers', { default: 'No users found.' })
					: 'No users found.'}
			</p>
		{:else}
			<!-- Responsive Table Wrapper -->
			<div class="mb-6 overflow-x-auto border border-gray-200 shadow-md sm:rounded-lg">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th
								scope="col"
								class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
								style="color: #2271b3;"
							>
								{localeLoaded ? $_('admin.users.table.name', { default: 'Name' }) : 'Name'}
							</th>
							<th
								scope="col"
								class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
								style="color: #2271b3;"
							>
								{localeLoaded ? $_('admin.users.table.email', { default: 'Email' }) : 'Email'}
							</th>
							<th
								scope="col"
								class="text-brand hidden px-6 py-3 text-left text-xs font-medium tracking-wider uppercase md:table-cell"
								style="color: #2271b3;"
							>
								{localeLoaded ? $_('admin.users.table.role', { default: 'Role' }) : 'Role'}
							</th>
							<th
								scope="col"
								class="text-brand hidden px-6 py-3 text-left text-xs font-medium tracking-wider uppercase lg:table-cell"
								style="color: #2271b3;"
							>
								Organization
							</th>
							<th
								scope="col"
								class="text-brand hidden px-6 py-3 text-left text-xs font-medium tracking-wider uppercase md:table-cell"
								style="color: #2271b3;"
							>
								Status
							</th>
							<th
								scope="col"
								class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
							>
								{localeLoaded ? $_('admin.users.table.actions', { default: 'Actions' }) : 'Actions'}
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200 bg-white">
						{#each users as user (user.id)}
							<tr class="hover:bg-gray-50">
								<td class="px-6 py-4 align-top whitespace-nowrap">
									<div class="text-sm font-medium text-gray-900">{user.name || '-'}</div>
								</td>
								<td class="px-6 py-4 align-top whitespace-nowrap">
									<div class="text-sm text-gray-800">{user.email}</div>
								</td>
								<td class="hidden px-6 py-4 text-sm whitespace-nowrap text-gray-800 md:table-cell">
									<span
										class="inline-flex rounded-full px-2 text-xs leading-5 font-semibold {user.role ===
										'admin'
											? 'bg-red-100 text-red-800'
											: 'bg-blue-100 text-blue-800'}"
									>
										{user.role}
									</span>
								</td>
								<td class="hidden px-6 py-4 text-sm whitespace-nowrap text-gray-800 lg:table-cell">
									{#if user.organization}
										<div class="flex items-center">
											<span class="text-sm font-medium text-gray-900"
												>{user.organization.name || '-'}</span
											>
											{#if user.organization.is_system}
												<span
													class="ml-2 inline-flex rounded-full bg-yellow-100 px-2 text-xs leading-5 font-semibold text-yellow-800"
												>
													System
												</span>
											{/if}
										</div>
										{#if user.organization_role && user.organization_role !== 'member'}
											<div class="text-xs text-gray-500">
												{user.organization_role}
											</div>
										{/if}
									{:else}
										<span class="text-gray-400">No Organization</span>
									{/if}
								</td>
								<td class="hidden px-6 py-4 text-sm whitespace-nowrap md:table-cell">
									<span
										class="inline-flex rounded-full px-2 text-xs leading-5 font-semibold {user.enabled
											? 'bg-green-100 text-green-800'
											: 'bg-red-100 text-red-800'}"
									>
										{user.enabled ? 'Active' : 'Disabled'}
									</span>
								</td>
								<td class="px-6 py-4 text-sm font-medium whitespace-nowrap">
									<!-- Action buttons - Edit and Delete buttons removed -->
									<button
										class="mr-3 text-amber-600 hover:text-amber-800"
										title={localeLoaded
											? $_('admin.users.actions.changePassword', { default: 'Change Password' })
											: 'Change Password'}
										aria-label={localeLoaded
											? $_('admin.users.actions.changePassword', { default: 'Change Password' })
											: 'Change Password'}
										onclick={() => openChangePasswordModal(user.email, user.name)}
									>
										<svg
											xmlns="http://www.w3.org/2000/svg"
											fill="none"
											viewBox="0 0 24 24"
											stroke-width="1.5"
											stroke="currentColor"
											class="h-5 w-5"
										>
											<path
												stroke-linecap="round"
												stroke-linejoin="round"
												d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25-2.25v6.75a2.25 2.25 0 002.25 2.25z"
											/>
										</svg>
									</button>
									<button
										class={currentUserData && currentUserData.email === user.email && user.enabled
											? 'cursor-not-allowed text-gray-400'
											: 'text-blue-600 hover:text-blue-800'}
										title={currentUserData && currentUserData.email === user.email && user.enabled
											? 'You cannot disable your own account'
											: user.enabled
												? 'Disable User'
												: 'Enable User'}
										aria-label={currentUserData &&
										currentUserData.email === user.email &&
										user.enabled
											? 'You cannot disable your own account'
											: user.enabled
												? 'Disable User'
												: 'Enable User'}
										onclick={() => toggleUserStatusAdmin(user)}
										disabled={currentUserData &&
											currentUserData.email === user.email &&
											user.enabled}
									>
										{#if user.enabled}
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="h-5 w-5"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728L5.636 5.636m12.728 12.728L18.364 5.636M5.636 18.364l12.728-12.728"
												/>
											</svg>
										{:else}
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="h-5 w-5"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
												/>
											</svg>
										{/if}
									</button>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{:else if currentView === 'organizations'}
		<!-- Organizations Management View -->
		<div class="mb-6 flex items-center justify-between">
			<h1 class="text-2xl font-semibold text-gray-800">
				{localeLoaded
					? $_('admin.organizations.title', { default: 'Organization Management' })
					: 'Organization Management'}
			</h1>
			<div class="flex space-x-2">
				<button
					onclick={syncSystemOrganization}
					class="focus:ring-opacity-50 rounded bg-green-600 px-4 py-2 text-white hover:bg-green-700 focus:ring-2 focus:ring-green-600 focus:outline-none"
					aria-label="Sync System Organization"
				>
					Sync System
				</button>
				<button
					onclick={openCreateOrgModal}
					class="bg-brand hover:bg-brand-hover focus:ring-brand focus:ring-opacity-50 rounded px-4 py-2 text-white focus:ring-2 focus:outline-none"
					style="background-color: #2271b3; color: white;"
					aria-label={localeLoaded
						? $_('admin.organizations.actions.create', { default: 'Create Organization' })
						: 'Create Organization'}
				>
					{localeLoaded
						? $_('admin.organizations.actions.create', { default: 'Create Organization' })
						: 'Create Organization'}
				</button>
			</div>
		</div>

		{#if isLoadingOrganizations}
			<p class="py-4 text-center text-gray-500">
				{localeLoaded
					? $_('admin.organizations.loading', { default: 'Loading organizations...' })
					: 'Loading organizations...'}
			</p>
		{:else if organizationsError}
			<div
				class="relative mb-6 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
				role="alert"
			>
				<strong class="font-bold"
					>{localeLoaded
						? $_('admin.organizations.errorTitle', { default: 'Error:' })
						: 'Error:'}</strong
				>
				<span class="block sm:inline"> {organizationsError}</span>
			</div>
			<!-- Button to retry fetching -->
			<div class="text-center">
				<button
					onclick={fetchOrganizations}
					class="bg-brand hover:bg-brand-hover focus:ring-brand focus:ring-opacity-50 rounded px-4 py-2 text-white focus:ring-2 focus:outline-none"
					style="background-color: #2271b3; color: white;"
				>
					{localeLoaded ? $_('admin.organizations.retry', { default: 'Retry' }) : 'Retry'}
				</button>
			</div>
		{:else if organizations.length === 0}
			<p class="py-4 text-center text-gray-500">
				{localeLoaded
					? $_('admin.organizations.noOrganizations', { default: 'No organizations found.' })
					: 'No organizations found.'}
			</p>
		{:else}
			<!-- Responsive Table Wrapper -->
			<div class="mb-6 overflow-x-auto border border-gray-200 shadow-md sm:rounded-lg">
				<table class="min-w-full divide-y divide-gray-200">
					<thead class="bg-gray-50">
						<tr>
							<th
								scope="col"
								class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
								style="color: #2271b3;"
							>
								{localeLoaded ? $_('admin.organizations.table.name', { default: 'Name' }) : 'Name'}
							</th>
							<th
								scope="col"
								class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
								style="color: #2271b3;"
							>
								{localeLoaded ? $_('admin.organizations.table.slug', { default: 'Slug' }) : 'Slug'}
							</th>
							<th
								scope="col"
								class="text-brand hidden px-6 py-3 text-left text-xs font-medium tracking-wider uppercase md:table-cell"
								style="color: #2271b3;"
							>
								{localeLoaded
									? $_('admin.organizations.table.status', { default: 'Status' })
									: 'Status'}
							</th>
							<th
								scope="col"
								class="text-brand hidden px-6 py-3 text-left text-xs font-medium tracking-wider uppercase lg:table-cell"
								style="color: #2271b3;"
							>
								{localeLoaded ? $_('admin.organizations.table.type', { default: 'Type' }) : 'Type'}
							</th>
							<th
								scope="col"
								class="text-brand px-6 py-3 text-left text-xs font-medium tracking-wider uppercase"
							>
								{localeLoaded
									? $_('admin.organizations.table.actions', { default: 'Actions' })
									: 'Actions'}
							</th>
						</tr>
					</thead>
					<tbody class="divide-y divide-gray-200 bg-white">
						{#each organizations as org (org.id)}
							<tr class="hover:bg-gray-50">
								<td class="px-6 py-4 align-top whitespace-nowrap">
									<div class="text-sm font-medium text-gray-900">{org.name || '-'}</div>
								</td>
								<td class="px-6 py-4 align-top whitespace-nowrap">
									<div class="font-mono text-sm text-gray-800">{org.slug}</div>
								</td>
								<td class="hidden px-6 py-4 text-sm whitespace-nowrap text-gray-800 md:table-cell">
									<span
										class="inline-flex rounded-full px-2 text-xs leading-5 font-semibold {org.status ===
										'active'
											? 'bg-green-100 text-green-800'
											: 'bg-yellow-100 text-yellow-800'}"
									>
										{org.status}
									</span>
								</td>
								<td class="hidden px-6 py-4 text-sm whitespace-nowrap text-gray-800 lg:table-cell">
									<span
										class="inline-flex rounded-full px-2 text-xs leading-5 font-semibold {org.is_system
											? 'bg-blue-100 text-blue-800'
											: 'bg-gray-100 text-gray-800'}"
									>
										{org.is_system ? 'System' : 'Regular'}
									</span>
								</td>
								<td class="px-6 py-4 text-sm font-medium whitespace-nowrap">
									<div class="flex space-x-2">
										<button
											class="text-green-600 hover:text-green-800"
											title="Administer Organization"
											aria-label="Administer Organization"
											onclick={() => administerOrganization(org)}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="h-5 w-5"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M10.343 3.94c.09-.542.56-.94 1.11-.94h1.093c.55 0 1.02.398 1.11.94l.149.894c.07.424.384.764.78.93.398.164.855.142 1.205-.108l.737-.527a1.125 1.125 0 011.45.12l.773.774c.39.389.44 1.002.12 1.45l-.527.737c-.25.35-.272.806-.107 1.204.165.397.505.71.93.78l.893.15c.543.09.94.56.94 1.109v1.094c0 .55-.397 1.02-.94 1.11l-.893.149c-.425.07-.765.383-.93.78-.165.398-.143.854.107 1.204l.527.738c.32.447.269 1.06-.12 1.45l-.774.773a1.125 1.125 0 01-1.449.12l-.738-.527c-.35-.25-.806-.272-1.203-.107-.397.165-.71.505-.781.929l-.149.894c-.09.542-.56.94-1.11.94h-1.094c-.55 0-1.019-.398-1.11-.94l-.148-.894c-.071-.424-.384-.764-.781-.93-.398-.164-.854-.142-1.204.108l-.738.527c-.447.32-1.06.269-1.45-.12l-.773-.774a1.125 1.125 0 01-.12-1.45l.527-.737c.25-.35.273-.806.108-1.204-.165-.397-.505-.71-.93-.78l-.894-.15c-.542-.09-.94-.56-.94-1.109v-1.094c0-.55.398-1.02.94-1.11l.894-.149c.424-.07.765-.383.93-.78.165-.398.143-.854-.107-1.204l-.527-.738a1.125 1.125 0 01.12-1.45l.773-.773a1.125 1.125 0 011.45-.12l.737.527c.35.25.807.272 1.204.107.397-.165.71-.505.78-.929l.15-.894z"
												/>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
												/>
											</svg>
										</button>
										<button
											class="text-blue-600 hover:text-blue-800"
											title={localeLoaded
												? $_('admin.organizations.actions.viewConfig', {
														default: 'View Configuration'
													})
												: 'View Configuration'}
											aria-label={localeLoaded
												? $_('admin.organizations.actions.viewConfig', {
														default: 'View Configuration'
													})
												: 'View Configuration'}
											onclick={() => openViewConfigModal(org)}
										>
											<svg
												xmlns="http://www.w3.org/2000/svg"
												fill="none"
												viewBox="0 0 24 24"
												stroke-width="1.5"
												stroke="currentColor"
												class="h-5 w-5"
											>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"
												/>
												<path
													stroke-linecap="round"
													stroke-linejoin="round"
													d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
												/>
											</svg>
										</button>
										{#if !org.is_system}
											<button
												class="text-red-600 hover:text-red-800"
												title={localeLoaded
													? $_('admin.organizations.actions.delete', {
															default: 'Delete Organization'
														})
													: 'Delete Organization'}
												aria-label={localeLoaded
													? $_('admin.organizations.actions.delete', {
															default: 'Delete Organization'
														})
													: 'Delete Organization'}
												onclick={() => deleteOrganization(org.slug)}
											>
												<svg
													xmlns="http://www.w3.org/2000/svg"
													fill="none"
													viewBox="0 0 24 24"
													stroke-width="1.5"
													stroke="currentColor"
													class="h-5 w-5"
												>
													<path
														stroke-linecap="round"
														stroke-linejoin="round"
														d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
													/>
												</svg>
											</button>
										{/if}
									</div>
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/if}
	{/if}
</div>

<!-- Change Password Modal -->
{#if isChangePasswordModalOpen}
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex h-full w-full items-center justify-center overflow-y-auto bg-gray-600"
	>
		<div class="relative mx-auto w-full max-w-md rounded-md border bg-white p-5 shadow-lg">
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
					{selectedUserName}
				</p>

				{#if changePasswordSuccess}
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
					<form class="mt-4" onsubmit={handleChangePassword}>
						{#if changePasswordError}
							<div
								class="relative mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
								role="alert"
							>
								<span class="block sm:inline">{changePasswordError}</span>
							</div>
						{/if}

						<div class="mb-4 text-left">
							<label for="email" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded ? $_('admin.users.password.email', { default: 'Email' }) : 'Email'}
							</label>
							<input
								type="email"
								id="email"
								class="w-full appearance-none rounded border bg-gray-100 px-3 py-2 leading-tight text-gray-500 shadow"
								value={passwordChangeData.email}
								disabled
								readonly
							/>
						</div>

						<div class="mb-6 text-left">
							<label for="new_password" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded
									? $_('admin.users.password.newPassword', { default: 'New Password' })
									: 'New Password'} *
							</label>
							<input
								type="password"
								id="new_password"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								bind:value={passwordChangeData.new_password}
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
								onclick={closeChangePasswordModal}
								class="focus:shadow-outline rounded bg-gray-300 px-4 py-2 text-gray-800 hover:bg-gray-400 focus:outline-none"
							>
								{localeLoaded ? $_('admin.users.password.cancel', { default: 'Cancel' }) : 'Cancel'}
							</button>
							<button
								type="submit"
								class="bg-brand focus:shadow-outline rounded px-4 py-2 font-bold text-white focus:outline-none disabled:opacity-50"
								style="background-color: #2271b3; color: white;"
								disabled={isChangingPassword}
							>
								{isChangingPassword
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

<!-- Create User Modal -->
{#if isCreateUserModalOpen}
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex h-full w-full items-center justify-center overflow-y-auto bg-gray-600"
	>
		<div class="relative mx-auto w-full max-w-md rounded-md border bg-white p-5 shadow-lg">
			<div class="mt-3 text-center">
				<h3 class="text-lg leading-6 font-medium text-gray-900">
					{localeLoaded
						? $_('admin.users.create.title', { default: 'Create New User' })
						: 'Create New User'}
				</h3>

				{#if createUserSuccess}
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
					<form class="mt-4" onsubmit={handleCreateUser}>
						{#if createUserError}
							<div
								class="relative mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
								role="alert"
							>
								<span class="block sm:inline">{createUserError}</span>
							</div>
						{/if}

						<div class="mb-4 text-left">
							<label for="email" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded ? $_('admin.users.create.email', { default: 'Email' }) : 'Email'} *
							</label>
							<input
								type="email"
								id="email"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								bind:value={newUser.email}
								required
							/>
						</div>

						<div class="mb-4 text-left">
							<label for="name" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded ? $_('admin.users.create.name', { default: 'Name' }) : 'Name'} *
							</label>
							<input
								type="text"
								id="name"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								bind:value={newUser.name}
								required
							/>
						</div>

						<div class="mb-4 text-left">
							<label for="password" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded
									? $_('admin.users.create.password', { default: 'Password' })
									: 'Password'} *
							</label>
							<input
								type="password"
								id="password"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								bind:value={newUser.password}
								required
							/>
						</div>

						<div class="mb-4 text-left">
							<label for="role" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded ? $_('admin.users.create.role', { default: 'Role' }) : 'Role'}
							</label>
							<select
								id="role"
								class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
								bind:value={newUser.role}
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

						<div class="mb-6 text-left">
							<label for="organization" class="mb-2 block text-sm font-bold text-gray-700">
								Organization
							</label>
							{#if isLoadingOrganizationsForUsers}
								<div class="text-sm text-gray-500">Loading organizations...</div>
							{:else if organizationsForUsersError}
								<div class="text-sm text-red-500">{organizationsForUsersError}</div>
							{:else}
								<select
									id="organization"
									class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
									bind:value={newUser.organization_id}
								>
									<option value={null}>Select an organization (optional)</option>
									{#each organizationsForUsers as org}
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
								If no organization is selected, the user will be assigned to the system organization
								by default.
							</p>
						</div>

						<div class="flex items-center justify-between">
							<button
								type="button"
								onclick={closeCreateUserModal}
								class="focus:shadow-outline rounded bg-gray-300 px-4 py-2 text-gray-800 hover:bg-gray-400 focus:outline-none"
							>
								{localeLoaded ? $_('admin.users.create.cancel', { default: 'Cancel' }) : 'Cancel'}
							</button>
							<button
								type="submit"
								class="bg-brand focus:shadow-outline rounded px-4 py-2 font-bold text-white focus:outline-none disabled:opacity-50"
								style="background-color: #2271b3; color: white;"
								disabled={isCreatingUser}
							>
								{isCreatingUser
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

<!-- Create Organization Modal -->
{#if isCreateOrgModalOpen}
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex h-full w-full items-center justify-center overflow-y-auto bg-gray-600"
	>
		<div class="relative mx-auto w-full max-w-2xl rounded-md border bg-white p-5 shadow-lg">
			<div class="mt-3">
				<h3 class="text-center text-lg leading-6 font-medium text-gray-900">
					{localeLoaded
						? $_('admin.organizations.create.title', { default: 'Create New Organization' })
						: 'Create New Organization'}
				</h3>

				{#if createOrgSuccess}
					<div
						class="relative mt-4 rounded border border-green-400 bg-green-100 px-4 py-3 text-green-700"
						role="alert"
					>
						<span class="block sm:inline"
							>{localeLoaded
								? $_('admin.organizations.create.success', {
										default: 'Organization created successfully!'
									})
								: 'Organization created successfully!'}</span
						>
					</div>
				{:else}
					<form class="mt-4" onsubmit={handleCreateOrganization}>
						{#if createOrgError}
							<div
								class="relative mb-4 rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
								role="alert"
							>
								<span class="block sm:inline">{createOrgError}</span>
							</div>
						{/if}

						<div class="mb-4 grid grid-cols-1 gap-4 md:grid-cols-2">
							<div class="text-left">
								<label for="org_slug" class="mb-2 block text-sm font-bold text-gray-700">
									{localeLoaded
										? $_('admin.organizations.create.slug', { default: 'Slug' })
										: 'Slug'} *
								</label>
								<input
									type="text"
									id="org_slug"
									class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
									bind:value={newOrg.slug}
									required
									pattern="[a-z0-9-]+"
									title="Only lowercase letters, numbers, and hyphens allowed"
								/>
								<p class="mt-1 text-xs text-gray-500 italic">
									URL-friendly identifier (lowercase, numbers, hyphens only)
								</p>
							</div>

							<div class="text-left">
								<label for="org_name" class="mb-2 block text-sm font-bold text-gray-700">
									{localeLoaded
										? $_('admin.organizations.create.name', { default: 'Name' })
										: 'Name'} *
								</label>
								<input
									type="text"
									id="org_name"
									class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
									bind:value={newOrg.name}
									required
								/>
							</div>
						</div>

						<!-- Admin User Selection -->
						<div class="mb-4 text-left">
							<label for="admin_user" class="mb-2 block text-sm font-bold text-gray-700">
								Organization Admin *
							</label>
							{#if isLoadingSystemUsers}
								<div class="text-sm text-gray-500">Loading system users...</div>
							{:else if systemUsersError}
								<div class="text-sm text-red-500">{systemUsersError}</div>
							{:else}
								<select
									id="admin_user"
									class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
									bind:value={newOrg.admin_user_id}
									required
								>
									<option value={null}>Select a user from system organization...</option>
									{#each systemOrgUsers.filter((user) => user.role !== 'admin') as user}
										<option value={user.id}>{user.name} ({user.email}) - {user.role}</option>
									{/each}
								</select>
							{/if}
							<p class="mt-1 text-xs text-gray-500 italic">
								Select a user from the system organization to become admin of this organization.
								<strong>Note:</strong> System admins are not eligible as they must remain in the system
								organization.
							</p>
						</div>

						<!-- Signup Configuration -->
						<div class="mb-4 text-left">
							<label for="signup_config_section" class="mb-2 block text-sm font-bold text-gray-700">
								Signup Configuration
							</label>
							<div id="signup_config_section" class="mb-3">
								<label class="flex items-center">
									<input type="checkbox" bind:checked={newOrg.signup_enabled} class="mr-2" />
									<span class="text-sm">Enable organization-specific signup</span>
								</label>
							</div>

							{#if newOrg.signup_enabled}
								<div>
									<label for="signup_key" class="mb-1 block text-sm text-gray-600"
										>Signup Key *</label
									>
									<input
										type="text"
										id="signup_key"
										class="focus:shadow-outline w-full appearance-none rounded border px-3 py-2 leading-tight text-gray-700 shadow focus:outline-none"
										bind:value={newOrg.signup_key}
										required={newOrg.signup_enabled}
										pattern="[a-zA-Z0-9_-]+"
										title="Only letters, numbers, hyphens, and underscores allowed"
										minlength="8"
										maxlength="64"
									/>
									<p class="mt-1 text-xs text-gray-500 italic">
										Unique key for users to signup to this organization (8-64 characters)
									</p>
								</div>
							{/if}
						</div>

						<!-- System Baseline Option -->
						<div class="mb-4 text-left">
							<label class="flex items-center">
								<input type="checkbox" bind:checked={newOrg.use_system_baseline} class="mr-2" />
								<span class="text-sm">Copy system organization configuration as baseline</span>
							</label>
							<p class="mt-1 text-xs text-gray-500 italic">
								Inherit providers and settings from the system organization
							</p>
						</div>

						<div class="mb-4 text-left">
							<label for="org_features" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded
									? $_('admin.organizations.create.features', { default: 'Features' })
									: 'Features'}
							</label>
							<div class="grid grid-cols-2 gap-2">
								<label class="flex items-center">
									<input
										type="checkbox"
										bind:checked={newOrg.config.features.rag_enabled}
										class="mr-2"
									/>
									<span class="text-sm">RAG Enabled</span>
								</label>
								<label class="flex items-center">
									<input
										type="checkbox"
										bind:checked={newOrg.config.features.mcp_enabled}
										class="mr-2"
									/>
									<span class="text-sm">MCP Enabled</span>
								</label>
								<label class="flex items-center">
									<input
										type="checkbox"
										bind:checked={newOrg.config.features.lti_publishing}
										class="mr-2"
									/>
									<span class="text-sm">LTI Publishing</span>
								</label>
								<label class="flex items-center">
									<input
										type="checkbox"
										bind:checked={newOrg.config.features.signup_enabled}
										class="mr-2"
									/>
									<span class="text-sm">Signup Enabled</span>
								</label>
							</div>
						</div>

						<div class="mb-4 text-left">
							<label for="org_limits" class="mb-2 block text-sm font-bold text-gray-700">
								{localeLoaded
									? $_('admin.organizations.create.limits', { default: 'Usage Limits' })
									: 'Usage Limits'}
							</label>
							<div class="grid grid-cols-1 gap-4 md:grid-cols-3">
								<div>
									<label for="tokens_per_month" class="mb-1 block text-xs text-gray-600"
										>Tokens/Month</label
									>
									<input
										type="number"
										id="tokens_per_month"
										class="focus:shadow-outline w-full appearance-none rounded border px-2 py-1 text-sm leading-tight text-gray-700 shadow focus:outline-none"
										bind:value={newOrg.config.limits.usage.tokens_per_month}
										min="0"
									/>
								</div>
								<div>
									<label for="max_assistants" class="mb-1 block text-xs text-gray-600"
										>Max Assistants</label
									>
									<input
										type="number"
										id="max_assistants"
										class="focus:shadow-outline w-full appearance-none rounded border px-2 py-1 text-sm leading-tight text-gray-700 shadow focus:outline-none"
										bind:value={newOrg.config.limits.usage.max_assistants}
										min="1"
									/>
								</div>
								<div>
									<label for="storage_gb" class="mb-1 block text-xs text-gray-600"
										>Storage (GB)</label
									>
									<input
										type="number"
										id="storage_gb"
										class="focus:shadow-outline w-full appearance-none rounded border px-2 py-1 text-sm leading-tight text-gray-700 shadow focus:outline-none"
										bind:value={newOrg.config.limits.usage.storage_gb}
										min="0"
										step="0.1"
									/>
								</div>
							</div>
						</div>

						<div class="flex items-center justify-between">
							<button
								type="button"
								onclick={closeCreateOrgModal}
								class="focus:shadow-outline rounded bg-gray-300 px-4 py-2 text-gray-800 hover:bg-gray-400 focus:outline-none"
							>
								{localeLoaded
									? $_('admin.organizations.create.cancel', { default: 'Cancel' })
									: 'Cancel'}
							</button>
							<button
								type="submit"
								class="bg-brand focus:shadow-outline rounded px-4 py-2 font-bold text-white focus:outline-none disabled:opacity-50"
								style="background-color: #2271b3; color: white;"
								disabled={isCreatingOrg}
							>
								{isCreatingOrg
									? localeLoaded
										? $_('admin.organizations.create.creating', { default: 'Creating...' })
										: 'Creating...'
									: localeLoaded
										? $_('admin.organizations.create.create', { default: 'Create Organization' })
										: 'Create Organization'}
							</button>
						</div>
					</form>
				{/if}
			</div>
		</div>
	</div>
{/if}

<!-- View Configuration Modal -->
{#if isViewConfigModalOpen && selectedOrg}
	<div
		class="bg-opacity-50 fixed inset-0 z-50 flex h-full w-full items-center justify-center overflow-y-auto bg-gray-600"
	>
		<div
			class="relative mx-auto max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-md border bg-white p-5 shadow-lg"
		>
			<div class="mt-3">
				<div class="mb-4 flex items-center justify-between">
					<h3 class="text-lg leading-6 font-medium text-gray-900">
						Configuration: {selectedOrg.name} ({selectedOrg.slug})
					</h3>
					<button
						onclick={closeViewConfigModal}
						class="text-gray-400 hover:text-gray-600"
						aria-label="Close"
					>
						<svg class="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
							<path
								stroke-linecap="round"
								stroke-linejoin="round"
								stroke-width="2"
								d="M6 18L18 6M6 6l12 12"
							></path>
						</svg>
					</button>
				</div>

				{#if isLoadingOrgConfig}
					<div class="py-8 text-center">
						<p class="text-gray-500">Loading configuration...</p>
					</div>
				{:else if configError}
					<div
						class="relative rounded border border-red-400 bg-red-100 px-4 py-3 text-red-700"
						role="alert"
					>
						<strong class="font-bold">Error:</strong>
						<span class="block sm:inline"> {configError}</span>
					</div>
				{:else if selectedOrgConfig}
					<div class="rounded-lg bg-gray-50 p-4">
						<h4 class="mb-2 text-sm font-medium text-gray-700">Configuration JSON:</h4>
						<pre class="overflow-x-auto rounded border bg-white p-4 text-xs"><code
								>{JSON.stringify(selectedOrgConfig, null, 2)}</code
							></pre>

						{#if selectedOrgConfig.setups}
							<div class="mt-6">
								<h4 class="mb-2 text-sm font-medium text-gray-700">Setups Summary:</h4>
								<div class="grid grid-cols-1 gap-4 md:grid-cols-2">
									{#each Object.entries(selectedOrgConfig.setups) as [setupName, setup]}
										<div class="rounded border bg-white p-3">
											<h5 class="text-sm font-medium text-gray-800">{setup.name || setupName}</h5>
											<p class="mb-1 text-xs text-gray-600">
												{setup.is_default ? '(Default)' : ''}
											</p>
											{#if setup.providers}
												<div class="text-xs">
													<strong>Providers:</strong>
													{Object.keys(setup.providers).join(', ') || 'None'}
												</div>
											{/if}
										</div>
									{/each}
								</div>
							</div>
						{/if}

						{#if selectedOrgConfig.features}
							<div class="mt-4">
								<h4 class="mb-2 text-sm font-medium text-gray-700">Features:</h4>
								<div class="grid grid-cols-2 gap-2 md:grid-cols-4">
									{#each Object.entries(selectedOrgConfig.features) as [feature, enabled]}
										<div class="flex items-center text-xs">
											<span
												class="mr-2 h-2 w-2 rounded-full {enabled ? 'bg-green-500' : 'bg-gray-300'}"
											></span>
											<span class="capitalize">{feature.replace('_', ' ')}</span>
										</div>
									{/each}
								</div>
							</div>
						{/if}

						{#if selectedOrgConfig.limits && selectedOrgConfig.limits.usage}
							<div class="mt-4">
								<h4 class="mb-2 text-sm font-medium text-gray-700">Usage Limits:</h4>
								<div class="grid grid-cols-1 gap-4 text-xs md:grid-cols-3">
									<div>
										<strong>Tokens/Month:</strong>
										{selectedOrgConfig.limits.usage.tokens_per_month?.toLocaleString() ||
											'Unlimited'}
									</div>
									<div>
										<strong>Max Assistants:</strong>
										{selectedOrgConfig.limits.usage.max_assistants || 'Unlimited'}
									</div>
									<div>
										<strong>Storage:</strong>
										{selectedOrgConfig.limits.usage.storage_gb || 'Unlimited'} GB
									</div>
								</div>
							</div>
						{/if}
					</div>
				{/if}

				<div class="mt-6 text-center">
					<button
						onclick={closeViewConfigModal}
						class="focus:shadow-outline rounded bg-gray-300 px-4 py-2 text-gray-800 hover:bg-gray-400 focus:outline-none"
					>
						Close
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

<style>
	/* Add specific styles if needed, though Tailwind should cover most */
</style>
