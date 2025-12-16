<script>
    import { _, locale } from '$lib/i18n';
    import { goto } from '$app/navigation';
    import { user } from '$lib/stores/userStore';
    import { fade, fly } from 'svelte/transition';

    // --- Props ---
    let {
        isOpen = $bindable(false)
    } = $props();

    // --- Internal State ---
    let localeLoaded = $state(false);

    // --- Lifecycle ---
    let localeUnsubscribe = () => {};
    $effect(() => {
        localeUnsubscribe = locale.subscribe(value => {
            localeLoaded = !!value;
        });
        return () => {
            localeUnsubscribe();
        };
    });

    // --- Functions ---
    function handleGoToLogin() {
        // Logout user to clear token
        user.logout();
        // Close modal
        isOpen = false;
        // Redirect to home/login page
        goto('/');
    }

    /** @param {KeyboardEvent} event */
    function handleKeydown(event) {
        if (event.key === 'Escape' || event.key === 'Enter') {
            handleGoToLogin();
        }
    }
</script>

<svelte:window onkeydown={handleKeydown}/>

{#if isOpen}
    <!-- Modal Backdrop -->
    <div 
        class="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-expired-title"
        transition:fade={{ duration: 200 }}
    >
        <!-- Modal Content -->
        <div 
            class="bg-white rounded-lg shadow-xl max-w-md w-full p-6"
            transition:fly={{ y: 20, duration: 200 }}
        >
            <!-- Icon -->
            <div class="flex items-center justify-center w-12 h-12 mx-auto mb-4 bg-red-100 rounded-full">
                <svg class="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
            </div>

            <!-- Title -->
            <h3 
                id="session-expired-title"
                class="text-lg font-semibold text-gray-900 text-center mb-2"
            >
                {localeLoaded ? $_(`Session Expired`) : 'Session Expired'}
            </h3>

            <!-- Message -->
            <p class="text-gray-600 text-center mb-6">
                {localeLoaded ? $_(`Your session has expired or the token is invalid. Please sign in again to continue.`) : 'Your session has expired or the token is invalid. Please sign in again to continue.'}
            </p>

            <!-- Actions -->
            <div class="flex justify-center">
                <button
                    type="button"
                    onclick={handleGoToLogin}
                    class="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
                >
                    {localeLoaded ? $_(`Go to Login`) : 'Go to Login'}
                </button>
            </div>
        </div>
    </div>
{/if}

