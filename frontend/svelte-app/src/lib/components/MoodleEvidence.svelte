<script>
    import { moodleResult } from '$lib/services/moodleService';
    import { locale } from 'svelte-i18n';
    let { resultId } = $props();
    let data = $state(null);
    let error = $state('');
    function dateLabel(value) {
        return new Intl.DateTimeFormat($locale || 'en', {dateStyle:'medium',timeStyle:'short',
            timeZone:data?.snapshot.window.timezone || 'UTC'}).format(new Date(value));
    }
    $effect(() => {
        const id = resultId;
        let active = true;
        data = null; error = '';
        moodleResult(id).then(value => { if (active) data = value; })
            .catch(e => { if (active) error = e.message; });
        return () => { active = false; };
    });
    function link(discussionId, postId) {
        const url = new URL(data.base_url);
        if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password
            || !Number.isInteger(discussionId) || !Number.isInteger(postId)) return '';
        url.pathname = url.pathname.replace(/\/$/, '') + '/mod/forum/discuss.php';
        url.search = `d=${discussionId}`; url.hash = `p${postId}`;
        return url.href;
    }
</script>

{#if error}<p role="alert">{error}</p>
{:else if !data}<p role="status">Loading verified Moodle evidence…</p>
{:else}
    <section data-aac-resource="moodle-result" data-aac-id={data.result_id} data-aac-tab="view">
        <h1>Forum activity</h1>
        <aside class:partial={!data.snapshot.coverage.complete} aria-label="Coverage">
            <strong>{data.snapshot.coverage.complete ? 'Complete coverage' : 'Partial coverage'}</strong>
            <p>{data.snapshot.coverage.posts_found} posts found. {data.snapshot.coverage.courses.ok || 0} of {data.snapshot.coverage.requested_courses} requested courses fully checked.</p>
            <p>New posts from {dateLabel(data.snapshot.window.since)} to {dateLabel(data.snapshot.window.until)} (end excluded). {data.snapshot.window.timezone || 'UTC'}.</p>
            <p>Checked at {dateLabel(data.snapshot.completed_at)}. {data.snapshot.coverage.meaning}.</p>
        </aside>
        <ul><li>New posts only; edits to older posts are not included.</li>
            <li>Messages visible to your instructor account when checked. Moodle may have changed since.</li></ul>
        <h2>Course coverage</h2>
        {#each data.snapshot.courses as course}
            <details><summary>{course.name || course.id}: {course.status}</summary>
                {#if course.reason}<p>{course.reason}</p>{/if}
                <ul>{#each course.forums as forum}<li>{forum.name}: {forum.status}. {forum.posts_found} posts. {forum.reason || ''}</li>{/each}</ul>
            </details>
        {/each}
        <h2>Posts</h2>
        <p>Plain-text display. Open Moodle for original formatting, attachments and the complete thread.</p>
        {#each data.snapshot.posts as post}
            <article>
                <h3>{post.subject_text}</h3>
                <p>Course {post.course_id} · {dateLabel(post.timecreated * 1000)}</p>
                <div class="message">{post.message_text}</div>
                <a href={link(post.discussion_id, post.id)} target="_blank" rel="noopener noreferrer">Open post in Moodle</a>
            </article>
        {:else}<p>No matching posts were retained. Check the coverage above before drawing conclusions.</p>{/each}
        <small>Evidence {data.result_id}. Stored for up to 24 hours; older results may be evicted after 16 runs.</small>
    </section>
{/if}

<style>
    section{color:#1f2937}h1{font-size:1.8rem;font-weight:700}h2{font-size:1.25rem;font-weight:600;margin:1.5rem 0 .5rem}h3{font-weight:600}
    aside{padding:1rem;background:#ecfdf5;border-left:4px solid #059669;margin:1rem 0}aside.partial{background:#fffbeb;border-color:#d97706}
    p{margin:.6rem 0}ul{list-style:disc;padding-left:1.5rem}details{padding:.6rem;border-bottom:1px solid #cbd5e1}summary{cursor:pointer}
    article{border:1px solid #cbd5e1;border-radius:.5rem;padding:1rem;margin:1rem 0}.message{white-space:pre-wrap;overflow-wrap:anywhere}a{color:#1d4ed8;text-decoration:underline}small{overflow-wrap:anywhere}
</style>
