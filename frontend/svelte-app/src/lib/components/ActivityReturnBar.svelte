<script>
	/** Shown under the top bar to a teacher who came from an LMS activity: the way back to it (#562). */
	import { onMount } from 'svelte';
	import { _ } from '$lib/i18n';
	import { readActivity, activityReturnUrl } from '$lib/session/activityReturn';

	/** @type {import('$lib/session/activityReturn').ActivityReturn | null} */
	let activity = $state(null);
	let leaving = $state(false);

	onMount(() => {
		activity = readActivity();
		if (!activity) return;
		// The page may stay open past the expiry: the bar goes away then.
		const wait = Math.min(Math.max(0, activity.exp * 1000 - Date.now()) + 1000, 2 ** 31 - 1);
		const timer = setTimeout(() => { activity = readActivity(); }, wait);
		return () => clearTimeout(timer);
	});

	function back() {
		const current = readActivity();
		if (!current) {
			activity = null;
			return;
		}
		leaving = true;
		// Same window, as the activity opened LAMB Creator in it.
		window.location.assign(activityReturnUrl(current.token));
	}
</script>

{#if activity}
	<div class="activity-return-bar" role="status">
		<span>
			{activity.title
				? $_('ltiSession.cameFromCourse', { values: { course: activity.title }, default: 'You came from the activity in {course}' })
				: $_('ltiSession.cameFromActivity', { default: 'You came from an activity in your LMS' })}
		</span>
		<button type="button" onclick={back} disabled={leaving}>
			{$_('ltiSession.backToActivity', { default: 'Back to the activity' })}
		</button>
	</div>
{/if}

<style>
	.activity-return-bar { display: flex; flex-wrap: wrap; gap: 0.375rem 1rem; align-items: center; justify-content: center;
		padding: 0.375rem 1rem; background: #eaf2fa; border-bottom: 1px solid #c7dcef; color: #173f64; font-size: 0.875rem; }
	.activity-return-bar span { min-width: 0; overflow-wrap: anywhere; text-align: center; }
	.activity-return-bar button { background: #173f64; color: #fff; border-radius: 0.375rem; padding: 0.25rem 0.75rem;
		font-weight: 600; white-space: nowrap; }
	.activity-return-bar button:hover { background: #2271b3; }
	.activity-return-bar button:disabled { opacity: 0.6; }
</style>
