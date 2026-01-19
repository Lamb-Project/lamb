<script>
    import { _, locale } from '$lib/i18n';

    // --- Props ---
    let {
        isOpen = $bindable(false),
        isLoading = $bindable(false),
        title = '',
        message = '',
        confirmText = '',
        cancelText = '',
        variant = 'danger', // 'danger' | 'warning' | 'info'
        onconfirm = () => {},
        oncancel = () => {}
    } = $props();

    // --- Locale Ready State (simplified pattern) ---
    // Uses $derived for reactive locale tracking - see $lib/utils/useLocaleReady.js
    let localeLoaded = $derived(!!$locale);

    // --- Computed values for variant styling ---
    /** @type {Record<string, {headerBg: string, headerBorder: string, iconColor: string, titleColor: string, confirmBg: string, confirmRing: string}>} */
    const variantStyles = {
        danger: {
            headerBg: 'bg-red-50',
            headerBorder: 'border-red-200',
            iconColor: 'text-red-600',
            titleColor: 'text-red-900',
            confirmBg: 'bg-red-600 hover:bg-red-700',
            confirmRing: 'focus:ring-red-500'
        },
        warning: {
            headerBg: 'bg-yellow-50',
            headerBorder: 'border-yellow-200',
            iconColor: 'text-yellow-600',
            titleColor: 'text-yellow-900',
            confirmBg: 'bg-yellow-600 hover:bg-yellow-700',
            confirmRing: 'focus:ring-yellow-500'
        },
        info: {
            headerBg: 'bg-blue-50',
            headerBorder: 'border-blue-200',
            iconColor: 'text-blue-600',
            titleColor: 'text-blue-900',
            confirmBg: 'bg-blue-600 hover:bg-blue-700',
            confirmRing: 'focus:ring-blue-500'
        }
    };

    let styles = $derived(variantStyles[variant] || variantStyles.danger);

    // --- Default text values ---
    let displayTitle = $derived(title || (localeLoaded ? $_('common.confirm', { default: 'Confirm' }) : 'Confirm'));
    let displayConfirmText = $derived(confirmText || (localeLoaded ? $_('common.confirm', { default: 'Confirm' }) : 'Confirm'));
    let displayCancelText = $derived(cancelText || (localeLoaded ? $_('common.cancel', { default: 'Cancel' }) : 'Cancel'));

    // --- Functions ---
    function handleConfirm() {
        if (isLoading) return;
        onconfirm();
    }

    function handleCancel() {
        if (isLoading) return;
        oncancel();
        isOpen = false;
    }

    function handleOverlayClick() {
        if (isLoading) return;
        handleCancel();
    }

    /** @param {KeyboardEvent} event */
    function handleKeydown(event) {
        if (!isOpen) return;
        if (event.key === 'Escape') {
            handleCancel();
        }
    }
</script>

<svelte:window onkeydown={handleKeydown}/>

{#if isOpen}
    <!-- Modal Overlay -->
    <div 
        class="fixed inset-0 bg-gray-500 bg-opacity-75 transition-opacity z-40" 
        onclick={handleOverlayClick} 
        aria-hidden="true"
    ></div>

    <!-- Modal Panel -->
    <div class="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div 
            class="relative bg-white rounded-lg shadow-xl overflow-hidden max-w-md w-full border border-gray-300 mx-2" 
            role="dialog" 
            aria-modal="true" 
            aria-labelledby="modal-title-confirm"
        >
            <!-- Modal Header -->
            <div class="px-4 py-3 sm:px-6 border-b flex items-center {styles.headerBg} {styles.headerBorder}">
                {#if variant === 'danger'}
                    <svg class="h-6 w-6 mr-2 {styles.iconColor}" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
                    </svg>
                {:else if variant === 'warning'}
                    <svg class="h-6 w-6 mr-2 {styles.iconColor}" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                    </svg>
                {:else}
                    <svg class="h-6 w-6 mr-2 {styles.iconColor}" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor" aria-hidden="true">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z" />
                    </svg>
                {/if}
                <h3 class="text-lg leading-6 font-medium {styles.titleColor}" id="modal-title-confirm">
                    {displayTitle}
                </h3>
            </div>

            <!-- Modal Body -->
            <div class="px-4 py-5 sm:p-6">
                <p class="text-sm text-gray-700 whitespace-pre-line break-words">
                    {message}
                </p>
                {#if isLoading}
                    <p class="text-sm text-gray-500 mt-2 flex items-center">
                        <svg class="animate-spin h-4 w-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        {localeLoaded ? $_('common.processing', { default: 'Processing...' }) : 'Processing...'}
                    </p>
                {/if}
            </div>

            <!-- Modal Footer -->
            <div class="bg-gray-50 px-4 py-3 sm:px-6 flex flex-col-reverse gap-2 sm:flex-row-reverse border-t border-gray-200">
                <button 
                    type="button" 
                    class="w-full inline-flex justify-center rounded-md border border-transparent shadow-sm px-4 py-2 text-base font-medium text-white focus:outline-none focus:ring-2 focus:ring-offset-2 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50 {styles.confirmBg} {styles.confirmRing}"
                    onclick={handleConfirm}
                    disabled={isLoading}
                    style="min-width:100px"
                >
                    {#if isLoading}
                        <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                    {/if}
                    {displayConfirmText}
                </button>
                <button 
                    type="button" 
                    class="w-full inline-flex justify-center rounded-md border border-gray-300 shadow-sm px-4 py-2 bg-white text-base font-medium text-gray-700 hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand sm:mt-0 sm:ml-3 sm:w-auto sm:text-sm disabled:opacity-50"
                    onclick={handleCancel}
                    disabled={isLoading}
                    style="min-width:100px"
                >
                    {displayCancelText}
                </button>
            </div>
        </div>
    </div>
{/if}
