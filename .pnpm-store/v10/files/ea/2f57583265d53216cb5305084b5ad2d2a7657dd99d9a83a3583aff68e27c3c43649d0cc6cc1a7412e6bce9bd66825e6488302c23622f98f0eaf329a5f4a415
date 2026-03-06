import { SvelteMap } from 'svelte/reactivity';
export declare function createContext<T>(name: string): {
    hasContext: () => boolean;
    getContext: () => T;
    setContext: (value: T) => T;
};
export declare function promiseWithResolvers<T>(): {
    promise: Promise<T>;
    resolve: (value: T) => void;
    reject: (reason?: unknown) => void;
};
export declare class KeyedStore<T> extends SvelteMap<string, T> {
    #private;
    constructor(itemConstructor: new () => T, value?: Iterable<readonly [string, T]> | null | undefined);
    get(key: string): T;
}
//# sourceMappingURL=utils.svelte.d.ts.map