<script>
    import { onMount } from 'svelte';
    import { page } from '$app/stores';

    let token = $state('');
    let loading = $state(true);
    let saving = $state(false);
    let error = $state(null);
    let success = $state(false);

    let setupData = $state(null);
    let selectedActivity = $state('');
    let selectedOrg = $state('');
    let selectedAssistants = $state([]);
    // dynamic fields will be stored here
    let dynamicOptions = $state({});

    onMount(async () => {
        token = $page.url.searchParams.get('token');
        if (!token) {
            error = "Missing LTI authorization token.";
            loading = false;
            return;
        }

        try {
            const res = await fetch(`/lamb/v1/lti/setup/info?token=${token}`);
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || "Failed to load configuration info");
            }
            setupData = await res.json();
            
            if (setupData.modules && setupData.modules.length > 0) {
                selectedActivity = setupData.modules[0].name;
            }

            if (!setupData.needs_org_selection && Object.keys(setupData.orgs_with_assistants).length > 0) {
                selectedOrg = Object.keys(setupData.orgs_with_assistants)[0];
            }
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    });

    let currentModuleFields = $derived(
        (setupData && setupData.modules_fields && selectedActivity) 
            ? (setupData.modules_fields[selectedActivity] || []) 
            : []
    );

    let availableAssistants = $derived(
        (setupData && selectedOrg) 
            ? (setupData.orgs_with_assistants[selectedOrg] || []) 
            : []
    );

    let canSubmit = $derived(selectedActivity && selectedOrg && selectedAssistants.length > 0 && !saving);

    function toggleAssistant(id) {
        if (selectedAssistants.includes(id)) {
            selectedAssistants = selectedAssistants.filter(a => a !== id);
        } else {
            selectedAssistants = [...selectedAssistants, id];
        }
    }

    async function handleSubmit(e) {
        e.preventDefault();
        if (!canSubmit) return;
        
        saving = true;
        error = null;

        try {
            // Transform dynamic options into the flat structure backend expects
            const payload = {
                token: token,
                activity_type: selectedActivity,
                organization_id: selectedOrg,
                assistant_ids: selectedAssistants,
                // Include any dynamic checkbox or select inputs explicitly
                ...dynamicOptions
            };

            const res = await fetch('/lamb/v1/lti/configure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                throw new Error(errData.detail || "Failed to save configuration");
            }
            
            success = true;
        } catch (e) {
            error = e.message;
            saving = false;
        }
    }
</script>

<div class="min-h-screen flex items-center justify-center p-4">
    <div class="bg-white rounded-xl shadow-lg max-w-2xl w-full p-8">
        <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-xl">🚀</div>
            <div>
                <h1 class="text-xl font-bold text-gray-900">LAMB Activity Setup</h1>
                {#if setupData?.context_title}
                    <p class="text-sm text-gray-500">Course: {setupData.context_title}</p>
                {/if}
            </div>
        </div>

        {#if loading}
            <div class="flex justify-center p-8">
                <span class="text-gray-500">Loading Configuration...</span>
            </div>
        {:else if error}
            <div class="bg-red-50 text-red-600 p-4 rounded-lg mb-6">
                <strong>Error:</strong> {error}
            </div>
        {:else if success}
            <div class="bg-green-50 text-green-700 p-6 rounded-lg text-center border border-green-200">
                <div class="text-3xl mb-2">✅</div>
                <h2 class="text-lg font-bold mb-2">Configuration Saved Successfully!</h2>
                <p class="text-sm">The LAMB activity is now configured. You can close this window or return to the course page.</p>
            </div>
        {:else}
            <form onsubmit={handleSubmit}>
                
                <!-- Step 0: Activity Type Selection -->
                <div class="mb-6">
                    <h2 class="text-lg font-semibold text-gray-800 mb-3">Activity Type</h2>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {#each setupData.modules as mod}
                            <label class="flex items-start gap-3 p-4 border rounded-xl cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-all {selectedActivity === mod.name ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-500 ring-opacity-50' : ''}">
                                <input type="radio" 
                                    name="activity_type" 
                                    value={mod.name} 
                                    bind:group={selectedActivity}
                                    class="mt-1 text-blue-600 focus:ring-blue-500" required>
                                <div>
                                    <span class="font-medium text-gray-900 block mb-1">{mod.display_name}</span>
                                    <span class="text-sm text-gray-500">{mod.description}</span>
                                </div>
                            </label>
                        {/each}
                    </div>
                </div>

                <!-- Step 1: Organization Selection -->
                {#if setupData.needs_org_selection}
                    <div class="mb-6">
                        <h2 class="text-lg font-semibold text-gray-800 mb-3">Choose Organization</h2>
                        <p class="text-sm text-gray-600 mb-4">
                            You have accounts in multiple organizations. Choose one for this activity.
                            <span class="text-amber-600 font-medium">This cannot be changed later.</span>
                        </p>
                        {#each Object.entries(setupData.orgs_with_assistants) as [org_id, assistants]}
                            <label class="flex items-center gap-3 p-3 border rounded-lg mb-2 cursor-pointer hover:bg-blue-50 transition-colors {selectedOrg === org_id ? 'border-blue-500 bg-blue-50' : ''}">
                                <input type="radio" 
                                    name="organization_id" 
                                    value={org_id} 
                                    bind:group={selectedOrg}
                                    class="text-blue-600 focus:ring-blue-500" required>
                                <div>
                                    <span class="font-medium text-gray-900">{setupData.org_names?.[org_id] || `Organization ${org_id}`}</span>
                                    <span class="text-sm text-gray-500 ml-2">({assistants.length} published assistants)</span>
                                </div>
                            </label>
                        {/each}
                    </div>
                {/if}

                <!-- Step 2: Assistant Selection -->
                {#if selectedOrg}
                    <div class="mb-6">
                        <h2 class="text-lg font-semibold text-gray-800 mb-1">Select Assistants</h2>
                        <p class="text-sm text-gray-600 mb-4">Choose which AI assistants will be available in this activity.</p>
                        
                        <div class="space-y-2 max-h-96 overflow-y-auto pr-2">
                            {#each availableAssistants as a}
                                <label class="flex items-start gap-3 p-3 flex-wrap border rounded-lg cursor-pointer hover:bg-blue-50 transition-colors {selectedAssistants.includes(a.id) ? 'border-blue-300 bg-blue-50' : ''}">
                                    <input type="checkbox" 
                                        name="assistant_ids" 
                                        value={a.id}
                                        checked={selectedAssistants.includes(a.id)}
                                        onchange={() => toggleAssistant(a.id)}
                                        class="mt-1 text-blue-600 rounded focus:ring-blue-500">
                                    <div>
                                        <span class="font-medium text-gray-900">{a.name}</span>
                                        {#if a.access_type === 'shared'}
                                            <span class="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full ml-2 font-medium">shared</span>
                                        {/if}
                                        <p class="text-sm text-gray-500">by {a.owner}</p>
                                    </div>
                                </label>
                            {/each}
                            {#if availableAssistants.length === 0}
                                <p class="text-sm text-gray-500 p-4 border rounded-lg bg-gray-50 italic">No published assistants found.</p>
                            {/if}
                        </div>
                    </div>
                {:else if setupData.needs_org_selection}
                    <div class="mb-6">
                        <h2 class="text-lg font-semibold text-gray-800 mb-1">Select Assistants</h2>
                        <p class="text-sm text-gray-400 italic">Select an organization above to see available assistants.</p>
                    </div>
                {/if}

                <!-- Step 3: Options -->
                {#if selectedOrg && currentModuleFields.length > 0}
                    <div class="mb-6">
                        <h2 class="text-lg font-semibold text-gray-800 mb-3">Options</h2>
                        <div class="space-y-3">
                            {#each currentModuleFields as f}
                                {#if f.type === 'checkbox'}
                                    <label class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-blue-50 transition-colors">
                                        <input type="checkbox" 
                                            name={f.name} 
                                            bind:checked={dynamicOptions[f.name]}
                                            class="mt-1 text-blue-600 rounded focus:ring-blue-500">
                                        <div>
                                            <span class="font-medium text-gray-900">{f.label}</span>
                                            {#if f.name === 'chat_visibility_enabled'}
                                                <p class="text-sm text-gray-500 mt-0.5">Students will be notified and must accept before using the tool. Chat content is always anonymized.</p>
                                            {/if}
                                        </div>
                                    </label>
                                {:else if f.type === 'select'}
                                    <div class="p-3 border rounded-lg">
                                        <label class="block font-medium text-gray-900 mb-1">{f.label}</label>
                                        <select 
                                            name={f.name} 
                                            bind:value={dynamicOptions[f.name]}
                                            class="w-full border-gray-300 rounded-lg shadow-sm focus:border-blue-500 focus:ring-blue-500">
                                            {#each (f.options || []) as opt}
                                                <option value={opt.value}>{opt.label}</option>
                                            {/each}
                                        </select>
                                    </div>
                                {/if}
                            {/each}
                        </div>
                    </div>
                {/if}

                <!-- Submit -->
                <div class="flex justify-end pt-4 border-t border-gray-100">
                    <button type="submit" 
                        class="bg-blue-600 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                        disabled={!canSubmit}>
                        {#if saving}
                            <svg class="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Saving...
                        {:else}
                            Save &amp; Launch
                        {/if}
                    </button>
                </div>
            </form>
        {/if}
    </div>
</div>
