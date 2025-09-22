<script>
	import { createEventDispatcher } from 'svelte';
	import { user } from '$lib/stores/userStore';
	import { login } from '$lib/services/authService';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { _, locale } from '$lib/i18n';
	import { onMount } from 'svelte';

	// Event dispatcher for component events
	const dispatch = createEventDispatcher();

	// Form state using $state
	let email = $state('');
	let password = $state('');
	let message = $state('');
	let success = $state(false);
	let loading = $state(false);

	let localeLoaded = $state(false);
	onMount(() => {
		const unsub = locale.subscribe((v) => (localeLoaded = !!v));
		return unsub;
	});

	// Handle form submission
	async function submitLogin() {
		loading = true;
		message = '';
		success = false;

		const result = await login(email, password);

		// Check the success flag and nested data object
		if (result.success && result.data) {
			// Pass the nested result.data object to userStore.login
			user.login(result.data);

			success = true;
			message = 'Login successful!'; // Use a generic message or i18n key

			setTimeout(() => {
				goto(base + '/', { replaceState: true });
			}, 1000);
		} else {
			// Handle login failure
			success = false;
			message = result.error || 'Login failed. Please check credentials.'; // Provide a clearer default error
		}

		loading = false;
	}

	// Show signup form
	function showSignup() {
		dispatch('show-signup');
	}
</script>

<div class="mx-auto max-w-md overflow-hidden rounded-lg bg-white shadow-md">
	<div class="p-6">
		<h2 class="mb-6 text-2xl font-bold">{localeLoaded ? $_('auth.loginTitle') : 'Login'}</h2>
		<form onsubmit={submitLogin} class="space-y-4">
			<div class="space-y-2">
				<label for="email" class="block text-sm font-medium"
					>{localeLoaded ? $_('auth.email') : 'Email'}</label
				>
				<input
					type="email"
					id="email"
					bind:value={email}
					required
					class="w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] focus:outline-none"
				/>
			</div>

			<div class="space-y-2">
				<label for="password" class="block text-sm font-medium"
					>{localeLoaded ? $_('auth.password') : 'Password'}</label
				>
				<input
					type="password"
					id="password"
					bind:value={password}
					required
					class="w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] focus:outline-none"
				/>
			</div>

			{#if message}
				<div
					class={`rounded-md p-3 ${success ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}
				>
					{message}
				</div>
			{/if}

			<button
				type="submit"
				disabled={loading}
				class="flex w-full justify-center rounded-md border border-transparent bg-[#2271b3] px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-[#195a91] focus:ring-2 focus:ring-[#2271b3] focus:ring-offset-2 focus:outline-none disabled:opacity-50"
			>
				{#if loading}
					<span>{localeLoaded ? $_('auth.loading') : 'Loading...'}</span>
				{:else}
					<span>{localeLoaded ? $_('auth.loginButton') : 'Login'}</span>
				{/if}
			</button>

			<div class="mt-4 text-center">
				<p class="text-sm text-gray-600">
					{localeLoaded ? $_('auth.noAccount') : "Don't have an account?"}
					<button
						type="button"
						onclick={showSignup}
						class="font-medium text-[#2271b3] hover:text-[#195a91]"
					>
						{localeLoaded ? $_('auth.signupLink') : 'Sign up'}
					</button>
				</p>
			</div>
		</form>
	</div>
</div>
