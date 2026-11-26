<script>
    import { onMount } from 'svelte';
    import { page } from '$app/stores';
    import OrganizationStep, { initialOrganization } from '$lib/OrganizationStep.svelte';
    import { kindsFor, keepOrFirst } from '$lib/activityKinds.js';
    import { _, locale } from '$lib/i18n.js';

    let token = $state('');
    let loading = $state(true);
    let saving = $state(false);
    /** @type {string | null} */
    let error = $state(null);
    let saveError = $state(null);   // a refused save keeps the form, so the teacher can correct it
    let success = $state(false);

    /** LTI /lamb/v1/lti/setup/info JSON @type {any} */
    let setupData = $state(null);
    let selectedActivity = $state('');
    let selectedOrg = $state('');
    let selectedAssistants = $state([]);
    let showSharedAssistants = $state(true);
    let includeRubricAssistants = $state(false);
    /** Dynamic module fields from setup (checkbox, select, text, …) @type {Record<string, any>} */
    let dynamicOptions = $state({});

    onMount(async () => {
        token = $page.url.searchParams.get('token') ?? '';
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

            // The only organization, or the one just added with a creator code (`&org=`).
            selectedOrg = initialOrganization(setupData, $page.url.searchParams.get('org'));
            if (setupData.existing_activity) {
                const activity = setupData.existing_activity;
                selectedOrg = String(activity.organization_id);
                selectedActivity = activity.activity_type;
                includeRubricAssistants = true;
                dynamicOptions = { ...activity.setup_config, chat_visibility_enabled: activity.chat_visibility_enabled };
            }
        } catch (e) {
            error = e instanceof Error ? e.message : String(e);
        } finally {
            loading = false;
        }
    });

    // The kinds of activity this teacher can create in the chosen organization. A kind that
    // cannot be created there is not shown; the selection follows the list.
    let kinds = $derived(kindsFor(setupData, selectedOrg));
    $effect(() => {
        const next = keepOrFirst(selectedActivity, kinds);
        if (next !== selectedActivity) selectedActivity = next;
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

    function filterAndSortAssistants(list, activity, showShared, includeRubric) {
        let rows = [...list];
        if (activity === 'file_evaluation') {
            rows = rows.filter((a) => a.rubric_eval_ready);
        } else if (!includeRubric) {
            rows = rows.filter((a) => !a.rubric_eval_ready);
        }
        if (!showShared) {
            rows = rows.filter((a) => a.access_type !== 'shared');
        }
        if (activity === 'chat') {
            rows.sort((a, b) => {
                if (a.rubric_eval_ready !== b.rubric_eval_ready) return a.rubric_eval_ready ? 1 : -1;
                return String(a.name || '').localeCompare(String(b.name || ''), undefined, { sensitivity: 'base' });
            });
        } else {
            rows.sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), undefined, { sensitivity: 'base' }));
        }
        return rows;
    }

    let baseAssistantsForActivity = $derived(
        selectedActivity === 'file_evaluation'
            ? availableAssistants.filter(a => a.rubric_eval_ready)
            : availableAssistants
    );

    let assistantsForCurrentActivity = $derived(
        filterAndSortAssistants(availableAssistants, selectedActivity, showSharedAssistants, includeRubricAssistants)
    );

    let emptyDueToFilters = $derived(
        baseAssistantsForActivity.length > 0 && assistantsForCurrentActivity.length === 0
    );

    // Clear assistant selection when activity type changes
    $effect(() => {
        selectedAssistants = setupData?.existing_activity?.activity_type === selectedActivity
            ? [...setupData.existing_activity.assistant_ids] : [];
    });

    // Default first option for select/radio fields (options come from /lti/setup/info)
    $effect(() => {
        if (!setupData?.modules_fields || !selectedActivity) return;
        const fields = setupData.modules_fields[selectedActivity] || [];
        const next = { ...dynamicOptions };
        let changed = false;
        for (const f of fields) {
            if ((f.type === 'select' || f.type === 'radio') && f.options?.length) {
                const v = next[f.name];
                if (v === undefined || v === '') {
                    next[f.name] = f.options[0].value;
                    changed = true;
                }
            }
        }
        if (changed) dynamicOptions = next;
    });

    // Check if all required dynamic fields have values + conditional group validation
    function hasRequiredFields() {
        if (!setupData?.modules_fields || !selectedActivity) return true;
        const fields = setupData.modules_fields[selectedActivity] || [];
        for (const f of fields) {
            // max_group_size: skip when submission_type is not "group"
            if (f.name === 'max_group_size') {
                if (dynamicOptions.submission_type === 'group') {
                    const gs = parseInt(dynamicOptions[f.name], 10);
                    if (isNaN(gs) || gs < 2 || gs > 20) return false;
                }
                continue;
            }
            if (f.required) {
                const val = dynamicOptions[f.name];
                if (val === undefined || val === null || val === '') return false;
                if (typeof val === 'string' && val.trim() === '') return false;
            }
        }
        return true;
    }

    // lamb-0.8: a module may not use assistants at all (LLM access)
    let needsAssistants = $derived(
        !(setupData?.modules || []).some(m => m.name === selectedActivity && m.requires_assistants === false)
    );

    // Nothing can be created in the chosen organization yet: LAMB Creator comes first.
    let creatorFirst = $derived(!!selectedOrg && kinds.length === 0);

    let canSubmit = $derived(
        selectedActivity && selectedOrg
        && (!needsAssistants || (selectedAssistants.length > 0
            && selectedAssistants.every(id => assistantsForCurrentActivity.some(a => a.id === id))))
        && hasRequiredFields() && !saving
    );

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
        saveError = null;

        try {
            // Module id last so it is never overwritten by module-specific field names (e.g. submission_type).
            const payload = {
                token: token,
                organization_id: selectedOrg,
                assistant_ids: needsAssistants ? selectedAssistants : [],
                ...dynamicOptions,
                activity_type: selectedActivity,
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

            const data = await res.json();
            if (data.redirect_url) {
                window.location.href = data.redirect_url;
                return;
            }
            success = true;
            saving = false;
        } catch (e) {
            saveError = e instanceof Error ? e.message : String(e);
            saving = false;
        }
    }
</script>

<div class="min-h-screen flex items-center justify-center p-4">
    <div class="bg-white rounded-xl shadow-lg max-w-2xl w-full p-8">
        <div class="flex items-center gap-3 mb-6">
            <div class="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center text-xl shrink-0">🚀</div>
            <div>
                <h1 class="text-xl font-bold text-gray-900">LAMB Activity Setup</h1>
                {#if setupData?.existing_activity}
                    <p class="text-sm font-medium text-gray-700">{setupData.existing_activity.activity_name}</p>
                    <p class="text-sm text-gray-500 break-words">
                        {setupData.existing_activity.org_name} / {setupData.existing_activity.lms_origin || 'LMS not yet recorded'} / {setupData.existing_activity.context_title || setupData.existing_activity.context_id || 'Course not yet recorded'}
                    </p>
                {:else if setupData?.context_title}
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

                <!-- Organization, always shown: the instructor's organizations, the chosen one, and
                     under it the way into LAMB Creator for that organization. The form follows. -->
                <OrganizationStep {token} info={setupData} bind:selected={selectedOrg} {creatorFirst} />

                <!-- Step 0: Activity Type Selection. Once the organization is chosen: the kinds this
                     teacher can create there, and only those. -->
                {#if selectedOrg && kinds.length === 0}
                    {#if $locale}
                        <div class="mb-6 p-4 border border-amber-300 rounded-lg bg-amber-50" data-no-activity-kinds>
                            <p class="text-sm text-amber-800 font-medium mb-2">{$_('setupHub.nothingTitle')}</p>
                            <p class="text-sm text-amber-700">{$_('setupHub.nothingBody')}</p>
                        </div>
                    {/if}
                {:else if selectedOrg}
                <div class="mb-6" data-activity-kinds>
                    <h2 class="text-lg font-semibold text-gray-800 mb-3">Activity Type</h2>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {#each kinds as mod (mod.name)}
                            <label class="flex items-start gap-3 p-4 border rounded-xl cursor-pointer hover:border-blue-500 hover:bg-blue-50 transition-all {selectedActivity === mod.name ? 'border-blue-500 bg-blue-50 ring-2 ring-blue-500 ring-opacity-50' : ''}">
                                <input type="radio" 
                                    name="activity_type" 
                                    value={mod.name} 
                                    bind:group={selectedActivity}
                                    class="mt-1 text-blue-600 focus:ring-blue-500" required>
                                <div>
                                    <span class="font-medium text-gray-900 block mb-1">{mod.name === 'file_evaluation' ? $_('setupHub.supervisedAssessment') : mod.display_name}</span>
                                    <span class="text-sm text-gray-500">{mod.description}</span>
                                </div>
                            </label>
                        {/each}
                    </div>
                </div>
                {/if}

                <!-- Step 2: Assistant Selection -->
                {#if selectedOrg && selectedActivity && needsAssistants}
                    <div class="mb-6">
                        <h2 class="text-lg font-semibold text-gray-800 mb-1">Select Assistants</h2>
                        <p class="text-sm text-gray-600 mb-3">Choose which AI assistants will be available in this activity.</p>

                        <!-- Filters -->
                        <div class="flex flex-wrap items-center gap-x-5 gap-y-1 mb-3">
                            <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                                <input type="checkbox" bind:checked={showSharedAssistants} class="text-blue-600 rounded focus:ring-blue-500" />
                                Include shared assistants
                            </label>
                            {#if selectedActivity === 'chat'}
                                <label class="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                                    <input type="checkbox" bind:checked={includeRubricAssistants} class="text-blue-600 rounded focus:ring-blue-500" />
                                    Include assistants with a rubric
                                </label>
                            {/if}
                        </div>

                        <div class="space-y-2 max-h-96 overflow-y-auto pr-2">
                            {#each assistantsForCurrentActivity as a}
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
                                        <p class="text-sm text-gray-500">by {a.owner_name || a.owner}</p>
                                    </div>
                                </label>
                            {/each}
                            {#if assistantsForCurrentActivity.length === 0 && emptyDueToFilters}
                                <p class="text-sm text-gray-500 p-4 border rounded-lg bg-gray-50 italic">No assistants match the current filters. Adjust the filters above.</p>
                            {/if}
                        </div>
                    </div>
                {/if}

                <!-- Step 3: Options -->
                {#if selectedOrg && selectedActivity && currentModuleFields.length > 0}
                    <div class="mb-6">
                        <h2 class="text-lg font-semibold text-gray-800 mb-3">Options</h2>
                        <div class="space-y-3">
                            {#each currentModuleFields as f}
                                {#if f.type === 'checkbox'}
                                    <label class="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-blue-50 transition-colors">
                                        <input type="checkbox" 
                                            name={f.name}
                                            disabled={!!setupData.existing_activity && f.name === 'chat_visibility_enabled'}
                                            bind:checked={dynamicOptions[f.name]}
                                            class="mt-1 text-blue-600 rounded focus:ring-blue-500">
                                        <div>
                                            <span class="font-medium text-gray-900">{f.label}</span>
                                            {#if f.name === 'chat_visibility_enabled'}
                                                <p class="text-sm text-gray-500 mt-0.5">Teachers of this activity can read students' conversations, with each student's name as your LMS sends it. Students are told the first time they open the chat; entering the chat means they accept. This choice cannot be changed after setup.</p>
                                            {/if}
                                        </div>
                                    </label>
                                {:else if f.type === 'select'}
                                    <div class="p-3 border rounded-lg bg-white">
                                        <label class="block font-medium text-gray-900 mb-1" for="dyn-{f.name}">{f.label}</label>
                                        <select
                                            id="dyn-{f.name}"
                                            name={f.name}
                                            bind:value={dynamicOptions[f.name]}
                                            class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500">
                                            {#each (f.options || []) as opt}
                                                <option class="bg-white text-gray-900" value={opt.value}>{opt.label}</option>
                                            {/each}
                                        </select>
                                    </div>
                                {:else if f.type === 'radio'}
                                    <div class="p-3 border rounded-lg bg-white">
                                        <span class="block font-medium text-gray-900 mb-2">
                                            {f.label}{#if f.required}<span class="text-red-500 ml-1">*</span>{/if}
                                        </span>
                                        <div class="flex flex-col gap-2">
                                            {#each (f.options || []) as opt}
                                                <label class="flex items-center gap-2 cursor-pointer">
                                                    <input type="radio"
                                                        name={f.name}
                                                        value={opt.value}
                                                        bind:group={dynamicOptions[f.name]}
                                                        class="text-blue-600 focus:ring-blue-500" />
                                                    <span class="text-gray-900">{opt.label}</span>
                                                </label>
                                            {/each}
                                        </div>
                                    </div>
                                {:else if f.type === 'text'}
                                    <div class="p-3 border rounded-lg bg-white">
                                        <label class="block font-medium text-gray-900 mb-1" for="dyn-{f.name}">
                                            {f.label}{#if f.required}<span class="text-red-500 ml-1">*</span>{/if}
                                        </label>
                                        <input
                                            id="dyn-{f.name}"
                                            type="text"
                                            name={f.name}
                                            bind:value={dynamicOptions[f.name]}
                                            class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder={f.label}
                                        />
                                    </div>
                                {:else if f.type === 'number'}
                                    {#if f.name !== 'max_group_size' || dynamicOptions.submission_type === 'group'}
                                    <div class="p-3 border rounded-lg bg-white">
                                        <label class="block font-medium text-gray-900 mb-1" for="dyn-{f.name}">
                                            {f.label}{#if f.name === 'max_group_size' || f.required}<span class="text-red-500 ml-1">*</span>{/if}
                                        </label>
                                        {#if f.name === 'max_group_size'}
                                            <p class="text-xs text-gray-400 mb-1">Min 2, Max 20</p>
                                        {/if}
                                        <input
                                            id="dyn-{f.name}"
                                            type="number"
                                            min={f.name === 'max_group_size' ? '2' : '1'}
                                            max={f.name === 'max_group_size' ? '20' : undefined}
                                            name={f.name}
                                            bind:value={dynamicOptions[f.name]}
                                            class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            required={f.name === 'max_group_size' || f.required}
                                        />
                                    </div>
                                    {/if}
                                {:else if f.type === 'datetime'}
                                    <div class="p-3 border rounded-lg bg-white">
                                        <label class="block font-medium text-gray-900 mb-1" for="dyn-{f.name}">
                                            {f.label}{#if f.required}<span class="text-red-500 ml-1">*</span>{/if}
                                        </label>
                                        <input
                                            id="dyn-{f.name}"
                                            type="datetime-local"
                                            name={f.name}
                                            bind:value={dynamicOptions[f.name]}
                                            required={f.required}
                                            class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                        />
                                    </div>
                                {:else if f.type === 'textarea'}
                                    <div class="p-3 border rounded-lg bg-white">
                                        <label class="block font-medium text-gray-900 mb-1" for="dyn-{f.name}">
                                            {f.label}{#if f.required}<span class="text-red-500 ml-1">*</span>{/if}
                                        </label>
                                        <textarea
                                            id="dyn-{f.name}"
                                            name={f.name}
                                            bind:value={dynamicOptions[f.name]}
                                            rows="4"
                                            class="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                                            placeholder={f.label}
                                            required={f.required}
                                        ></textarea>
                                    </div>
                                {/if}
                            {/each}
                        </div>
                    </div>
                {/if}

                {#if saveError}
                    <div role="alert" class="bg-red-50 text-red-600 p-4 rounded-lg mb-4">
                        <strong>Not saved:</strong> {saveError}
                    </div>
                {/if}
                <!-- Submit: only when there is a kind of activity to save. -->
                {#if selectedActivity}
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
                {/if}
            </form>
        {/if}
    </div>
</div>
