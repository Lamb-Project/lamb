<script>
	/** Shown while an administrator acts as a creator (#523). */
	import { onMount } from 'svelte';
	import { locale } from 'svelte-i18n';
	import { get } from 'svelte/store';
	import { user } from '$lib/stores/userStore';
	import { currentTakeover } from '$lib/services/takeoverService';
	import { returnFromTakeover } from '$lib/session/takeover';
	import { takeoverText, fill, when } from '$lib/utils/takeoverText';

	const text = $derived(takeoverText($locale));
	/** @type {any} */
	let info = $state(null);
	let leaving = $state(false);

	onMount(async () => {
		try {
			info = await currentTakeover(get(user).token || '');
			// Ended in another tab or expired: go back to the administrator's own account.
			if (!info?.active) await returnFromTakeover(false);
		} catch {
			await returnFromTakeover(false);
		}
	});

	async function back() {
		leaving = true;
		await returnFromTakeover(true);
	}
</script>

{#if info?.active}
	<div class="takeover-bar" role="status">
		<span>
			<strong>{fill(text.acting, { name: info.user?.name || '', email: info.user?.email || '' })}</strong>
			· {fill(text.until, { time: when(info.expires_at, $locale, true) })}
		</span>
		<button type="button" onclick={back} disabled={leaving}>{text.back}</button>
	</div>
{/if}

<style>
	.takeover-bar { position: sticky; top: 0; z-index: 60; display: flex; flex-wrap: wrap; gap: 0.5rem 1rem;
		align-items: center; justify-content: center; padding: 0.5rem 1rem; background: #7c2d12; color: #fff; font-size: 0.875rem; }
	.takeover-bar button { background: #fff; color: #7c2d12; border-radius: 0.375rem; padding: 0.25rem 0.75rem; font-weight: 600; }
	.takeover-bar button:disabled { opacity: 0.6; }
</style>
