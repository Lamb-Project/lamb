import { generateId, isAbortError, safeValidateTypes, } from '@ai-sdk/provider-utils';
import { asSchema, isDeepEqualData, parsePartialJson, } from '@ai-sdk/ui-utils';
import {} from 'zod';
import { getStructuredObjectContext, hasStructuredObjectContext, KeyedStructuredObjectStore, } from './structured-object-context.svelte.js';
export class StructuredObject {
    #options = {};
    #id = $derived(this.#options.id ?? generateId());
    #keyedStore = $state();
    #store = $derived(this.#keyedStore.get(this.#id));
    #abortController;
    /**
     * The current value for the generated object. Updated as the API streams JSON chunks.
     */
    get object() {
        return this.#store.object;
    }
    set #object(value) {
        this.#store.object = value;
    }
    /** The error object of the API request */
    get error() {
        return this.#store.error;
    }
    /**
     * Flag that indicates whether an API request is in progress.
     */
    get loading() {
        return this.#store.loading;
    }
    constructor(options) {
        if (hasStructuredObjectContext()) {
            this.#keyedStore = getStructuredObjectContext();
        }
        else {
            this.#keyedStore = new KeyedStructuredObjectStore();
        }
        this.#options = options;
        this.#object = options.initialValue;
    }
    /**
     * Abort the current request immediately, keep the current partial object if any.
     */
    stop = () => {
        try {
            this.#abortController?.abort();
        }
        catch {
            // ignore
        }
        finally {
            this.#store.loading = false;
            this.#abortController = undefined;
        }
    };
    /**
     * Calls the API with the provided input as JSON body.
     */
    submit = async (input) => {
        try {
            this.#store.object = undefined; // reset the data
            this.#store.loading = true;
            this.#store.error = undefined;
            const abortController = new AbortController();
            this.#abortController = abortController;
            const actualFetch = this.#options.fetch ?? fetch;
            const response = await actualFetch(this.#options.api, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...this.#options.headers,
                },
                credentials: this.#options.credentials,
                signal: abortController.signal,
                body: JSON.stringify(input),
            });
            if (!response.ok) {
                throw new Error((await response.text()) ?? 'Failed to fetch the response.');
            }
            if (response.body == null) {
                throw new Error('The response body is empty.');
            }
            let accumulatedText = '';
            let latestObject = undefined;
            await response.body.pipeThrough(new TextDecoderStream()).pipeTo(new WritableStream({
                write: chunk => {
                    if (abortController?.signal.aborted) {
                        throw new DOMException('Stream aborted', 'AbortError');
                    }
                    accumulatedText += chunk;
                    const { value } = parsePartialJson(accumulatedText);
                    const currentObject = value;
                    if (!isDeepEqualData(latestObject, currentObject)) {
                        latestObject = currentObject;
                        this.#store.object = currentObject;
                    }
                },
                close: () => {
                    this.#store.loading = false;
                    this.#abortController = undefined;
                    if (this.#options.onFinish != null) {
                        const validationResult = safeValidateTypes({
                            value: latestObject,
                            schema: asSchema(this.#options.schema),
                        });
                        this.#options.onFinish(validationResult.success
                            ? { object: validationResult.value, error: undefined }
                            : { object: undefined, error: validationResult.error });
                    }
                },
            }));
        }
        catch (error) {
            if (isAbortError(error)) {
                return;
            }
            const coalescedError = error instanceof Error ? error : new Error(String(error));
            if (this.#options.onError) {
                this.#options.onError(coalescedError);
            }
            this.#store.loading = false;
            this.#store.error = coalescedError;
        }
    };
}
