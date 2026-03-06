import { SvelteMap } from 'svelte/reactivity';
import { createContext, KeyedStore } from './utils.svelte.js';
class CompletionStore {
    completions = new SvelteMap();
    data = $state([]);
    loading = $state(false);
    error = $state();
}
export class KeyedCompletionStore extends KeyedStore {
    constructor(value) {
        super(CompletionStore, value);
    }
}
export const { hasContext: hasCompletionContext, getContext: getCompletionContext, setContext: setCompletionContext, } = createContext('Completion');
