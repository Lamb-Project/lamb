import type { DeepPartial } from '@ai-sdk/ui-utils';
import { KeyedStore } from './utils.svelte.js';
export declare class StructuredObjectStore<RESULT> {
    object: DeepPartial<RESULT> | undefined;
    loading: boolean;
    error: Error | undefined;
}
export declare class KeyedStructuredObjectStore extends KeyedStore<StructuredObjectStore<unknown>> {
    constructor(value?: Iterable<readonly [string, StructuredObjectStore<unknown>]> | null | undefined);
}
export declare const hasStructuredObjectContext: () => boolean, getStructuredObjectContext: () => KeyedStructuredObjectStore, setStructuredObjectContext: (value: KeyedStructuredObjectStore) => KeyedStructuredObjectStore;
//# sourceMappingURL=structured-object-context.svelte.d.ts.map