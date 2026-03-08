<script>
    import { onMount } from 'svelte';
    import { page } from '$app/stores';

    let token = $state('');
    let loading = $state(true);
    let error = $state(null);
    let submitting = $state(false);

    let consentData = $state(null);

    onMount(async () => {
        token = $page.url.searchParams.get('token');
        if (!token) {
            error = "Missing LTI authorization token.";
            loading = false;
            return;
        }

        try {
            // We will build this endpoint in the backend shortly
            const res = await fetch(`/lamb/v1/lti/consent/info?token=${token}`);
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || "Failed to load consent info");
            }
            consentData = await res.json();
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    });

    async function handleConsent(e) {
        e.preventDefault();
        submitting = true;
        error = null;

        try {
            const res = await fetch('/lamb/v1/lti/consent', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token })
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to submit consent");
            }

            // Redirect handles the successful consent launch flow directly from backend.
            // Wait, actually, the old backend /consent replied with a POST or redirect to the OWI URL.
            // Depending on how backend is updated, it might return a redirect URL in JSON.
            const result = await res.json();
            if (result.redirect_url) {
                window.location.href = result.redirect_url;
            } else {
                success = true; // Fallback
            }
        } catch (e) {
            error = e.message;
            submitting = false;
        }
    }
</script>

<div class="min-h-screen flex items-center justify-center p-4">
    <div class="bg-white rounded-xl shadow-lg max-w-lg w-full p-8">
        {#if loading}
            <div class="flex justify-center p-8">
                <span class="text-gray-500">Loading Notice...</span>
            </div>
        {:else if error}
            <div class="bg-red-50 text-red-600 p-4 rounded-lg mb-6">
                <strong>Error:</strong> {error}
            </div>
        {:else if consentData}
            <div class="flex items-center gap-3 mb-6">
                <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-xl">🚀</div>
                <div>
                    <h1 class="text-xl font-bold text-gray-900">{consentData.activity_name || 'LAMB Activity'}</h1>
                    {#if consentData.context_title}
                        <p class="text-sm text-gray-500">{consentData.context_title}</p>
                    {/if}
                </div>
            </div>

            <p class="text-gray-700 mb-4">Before you begin, please note:</p>

            <div class="bg-blue-50 border-l-4 border-blue-400 rounded p-4 mb-6">
                <div class="flex items-start gap-2">
                    <svg class="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <div>
                        <p class="font-semibold text-blue-800 mb-2">Your instructor has enabled chat transcript review for this activity.</p>
                        <ul class="text-sm text-blue-700 space-y-2">
                            <li class="flex items-start gap-2">
                                <span class="mt-0.5">•</span>
                                <span>Your conversations with the AI assistants may be reviewed by your instructor for educational purposes.</span>
                            </li>
                            <li class="flex items-start gap-2">
                                <span class="mt-0.5">•</span>
                                <span>All transcripts are <strong>anonymized</strong> — your name and identity are not visible to the instructor.</span>
                            </li>
                            <li class="flex items-start gap-2">
                                <span class="mt-0.5">•</span>
                                <span>This helps your instructor understand how the AI tools are being used and improve the course.</span>
                            </li>
                        </ul>
                    </div>
                </div>
            </div>

            <p class="text-sm text-gray-600 mb-6 text-center">
                By clicking "I Understand &amp; Continue", you acknowledge this and agree to proceed.
            </p>

            <form onsubmit={handleConsent}>
                <div class="flex justify-center">
                    <button type="submit"
                            disabled={submitting}
                            class="bg-blue-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-blue-700 transition-colors text-base disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2">
                        {#if submitting}
                            <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Processing...
                        {:else}
                            I Understand &amp; Continue
                        {/if}
                    </button>
                </div>
            </form>
        {/if}
    </div>
</div>
