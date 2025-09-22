<script>
	import { createEventDispatcher } from 'svelte';
	import { signup } from '$lib/services/authService';
	import { _, locale } from '$lib/i18n';
	import { onMount } from 'svelte';

	// Event dispatcher for component events
	const dispatch = createEventDispatcher();

	// Form state using $state
	let name = $state('');
	let email = $state('');
	let password = $state('');
	let secretKey = $state('');
	let message = $state('');
	let success = $state(false);
	let loading = $state(false);

	let localeLoaded = $state(false);
	onMount(() => {
		const unsub = locale.subscribe((v) => (localeLoaded = !!v));
		return unsub;
	});

	// Handle form submission
	async function submitSignup() {
		loading = true;
		message = '';
		success = false;

		const result = await signup(name, email, password, secretKey);

		if (result.success) {
			success = true;
			message = result.message || 'Signup successful!';
			setTimeout(() => {
				dispatch('show-login');
			}, 1500);
		} else {
			success = false;
			message = result.error || 'Error signing up';
		}

		loading = false;
	}

	// Show login form
	function showLogin() {
		dispatch('show-login');
	}
</script>

<div class="mx-auto max-w-md overflow-hidden rounded-lg bg-white shadow-md">
	<div class="p-6">
		<h2 class="mb-6 text-2xl font-bold">{localeLoaded ? $_('auth.signupTitle') : 'Sign Up'}</h2>
		<form onsubmit={submitSignup} class="space-y-4">
			<div class="space-y-2">
				<label for="name" class="block text-sm font-medium"
					>{localeLoaded ? $_('auth.name') : 'Name'}</label
				>
				<input
					type="text"
					id="name"
					bind:value={name}
					required
					class="w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] focus:outline-none"
				/>
			</div>

			<div class="space-y-2">
				<label for="signup-email" class="block text-sm font-medium"
					>{localeLoaded ? $_('auth.email') : 'Email'}</label
				>
				<input
					type="email"
					id="signup-email"
					bind:value={email}
					required
					class="w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] focus:outline-none"
				/>
			</div>

			<div class="space-y-2">
				<label for="signup-password" class="block text-sm font-medium"
					>{localeLoaded ? $_('auth.password') : 'Password'}</label
				>
				<input
					type="password"
					id="signup-password"
					bind:value={password}
					required
					class="w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] focus:outline-none"
				/>
			</div>

			<div class="space-y-2">
				<label for="secret" class="block text-sm font-medium"
					>{localeLoaded ? $_('auth.secretKey') : 'Secret Key'}</label
				>
				<input
					type="text"
					id="secret"
					bind:value={secretKey}
					required
					class="w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-[#2271b3] focus:ring-[#2271b3] focus:outline-none"
				/>
				<p class="mt-1 text-xs text-gray-500">
					{localeLoaded ? $_('auth.secretKeyHint') : 'You need a secret key to register'}
				</p>
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
					<span>{localeLoaded ? $_('auth.signupButton') : 'Sign Up'}</span>
				{/if}
			</button>

			<div class="mt-4 text-center">
				<p class="text-sm text-gray-600">
					{localeLoaded ? $_('auth.haveAccount') : 'Already have an account?'}
					<button
						type="button"
						onclick={showLogin}
						class="font-medium text-[#2271b3] hover:text-[#195a91]"
					>
						{localeLoaded ? $_('auth.loginLink') : 'Log in'}
					</button>
				</p>
			</div>
		</form>
	</div>
</div>
