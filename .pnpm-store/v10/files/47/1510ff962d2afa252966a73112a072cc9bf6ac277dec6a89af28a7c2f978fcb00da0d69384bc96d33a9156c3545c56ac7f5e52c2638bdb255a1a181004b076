import { hasContext, getContext, setContext, untrack } from 'svelte';
import { SvelteMap } from 'svelte/reactivity';
export function createContext(name) {
    const key = Symbol(name);
    return {
        hasContext: () => {
            // At the time of writing there's no way to determine if we're
            // currently initializing a component without a try-catch
            try {
                return hasContext(key);
            }
            catch (e) {
                if (typeof e === 'object' &&
                    e !== null &&
                    'message' in e &&
                    typeof e.message === 'string' &&
                    e.message?.includes('lifecycle_outside_component')) {
                    return false;
                }
                throw e;
            }
        },
        getContext: () => getContext(key),
        setContext: (value) => setContext(key, value),
    };
}
export function promiseWithResolvers() {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => {
        resolve = res;
        reject = rej;
    });
    return { promise, resolve: resolve, reject: reject };
}
export class KeyedStore extends SvelteMap {
    #itemConstructor;
    constructor(itemConstructor, value) {
        super(value);
        this.#itemConstructor = itemConstructor;
    }
    get(key) {
        const test = super.get(key) ??
            // Untrack here because this is technically a state mutation, meaning
            // deriveds downstream would fail. Because this is idempotent (even
            // though it's not pure), it's safe.
            untrack(() => this.set(key, new this.#itemConstructor())).get(key);
        return test;
    }
}
