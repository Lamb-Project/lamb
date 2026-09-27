<script>
	/** Tells a creator that an administrator acted on their account (#523). */
	import { onMount } from 'svelte';
	import { locale } from 'svelte-i18n';
	import { takeoverNotices, dismissTakeoverNotices } from '$lib/services/takeoverService';
	import { takeoverText, fill, when } from '$lib/utils/takeoverText';

	const text = $derived(takeoverText($locale));
	/** @type {any[]} */
	let notices = $state([]);

	onMount(async () => {
		try { notices = (await takeoverNotices()).notices || []; } catch { notices = []; }
	});

	async function dismiss() {
		const ended = notices.filter(n => !n.active).map(n => n.id);
		try { await dismissTakeoverNotices(ended); } catch { /* shown again next time */ }
		notices = notices.filter(n => n.active);
	}
</script>

{#if notices.length}
	<div class="takeover-notice" role="status">
		<strong>{text.noticeTitle}</strong>
		<ul>
			{#each notices as n (n.id)}
				<li>{n.active
					? fill(text.noticeActive, { actor: n.actor_name, email: n.actor_email, start: when(n.started_at, $locale) })
					: fill(text.noticeEnded, { actor: n.actor_name, email: n.actor_email, start: when(n.started_at, $locale), end: when(n.ended_at, $locale) })}</li>
			{/each}
		</ul>
		<p>{text.noticeWhy}</p>
		{#if notices.some(n => !n.active)}<button type="button" onclick={dismiss}>{text.dismiss}</button>{/if}
	</div>
{/if}

<style>
	.takeover-notice { margin: 0.75rem auto; max-width: 64rem; padding: 0.75rem 1rem; border: 1px solid #fcd34d;
		background: #fffbeb; color: #78350f; border-radius: 0.5rem; font-size: 0.875rem; }
	.takeover-notice ul { margin: 0.25rem 0 0.5rem 1.25rem; list-style: disc; }
	.takeover-notice button { background: #92400e; color: #fff; border-radius: 0.375rem; padding: 0.25rem 0.75rem; }
</style>
