import { createContext, KeyedStore } from './utils.svelte.js';
export class StructuredObjectStore {
    object = $state();
    loading = $state(false);
    error = $state();
}
export class KeyedStructuredObjectStore extends KeyedStore {
    constructor(value) {
        super(StructuredObjectStore, value);
    }
}
export const { hasContext: hasStructuredObjectContext, getContext: getStructuredObjectContext, setContext: setStructuredObjectContext, } = createContext('StructuredObject');
