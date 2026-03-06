import type { JSONValue } from '@ai-sdk/ui-utils';
import { SvelteMap } from 'svelte/reactivity';
import { KeyedStore } from './utils.svelte.js';
declare class CompletionStore {
    completions: SvelteMap<string, string>;
    data: JSONValue[];
    loading: boolean;
    error: Error | undefined;
}
export declare class KeyedCompletionStore extends KeyedStore<CompletionStore> {
    constructor(value?: Iterable<readonly [string, CompletionStore]> | null | undefined);
}
export declare const hasCompletionContext: () => boolean, getCompletionContext: () => KeyedCompletionStore, setCompletionContext: (value: KeyedCompletionStore) => KeyedCompletionStore;
export {};
//# sourceMappingURL=completion-context.svelte.d.ts.map