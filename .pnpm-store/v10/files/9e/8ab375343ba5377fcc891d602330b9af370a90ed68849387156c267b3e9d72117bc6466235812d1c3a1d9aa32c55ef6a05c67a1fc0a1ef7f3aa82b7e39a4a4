import { generateId, callCompletionApi, } from '@ai-sdk/ui-utils';
import { KeyedCompletionStore, getCompletionContext, hasCompletionContext, } from './completion-context.svelte.js';
export class Completion {
    #options = {};
    #api = $derived(this.#options.api ?? '/api/completion');
    #id = $derived(this.#options.id ?? generateId());
    #streamProtocol = $derived(this.#options.streamProtocol ?? 'data');
    #keyedStore = $state();
    #store = $derived(this.#keyedStore.get(this.#id));
    #abortController;
    /** The current completion result */
    get completion() {
        return this.#store.completions.get(this.#id) ?? '';
    }
    set completion(value) {
        this.#store.completions.set(this.#id, value);
    }
    /**
     * Additional data added on the server via StreamData.
     *
     * This is writable, so you can use it to transform or clear the chat data.
     */
    get data() {
        return this.#store.data;
    }
    set data(value) {
        this.#store.data = value;
    }
    /** The error object of the API request */
    get error() {
        return this.#store.error;
    }
    /** The current value of the input. Writable, so it can be bound to form inputs. */
    input = $state();
    /**
     * Flag that indicates whether an API request is in progress.
     */
    get loading() {
        return this.#store.loading;
    }
    constructor(options = {}) {
        if (hasCompletionContext()) {
            this.#keyedStore = getCompletionContext();
        }
        else {
            this.#keyedStore = new KeyedCompletionStore();
        }
        this.#options = options;
        this.completion = options.initialCompletion ?? '';
        this.input = options.initialInput ?? '';
    }
    /**
     * Abort the current request immediately, keep the generated tokens if any.
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
     * Send a new prompt to the API endpoint and update the completion state.
     */
    complete = async (prompt, options) => this.#triggerRequest(prompt, options);
    /** Form submission handler to automatically reset input and call the completion API */
    handleSubmit = async (event) => {
        event?.preventDefault?.();
        if (this.input) {
            await this.complete(this.input);
        }
    };
    #triggerRequest = async (prompt, options) => {
        return callCompletionApi({
            api: this.#api,
            prompt,
            credentials: this.#options.credentials,
            headers: { ...this.#options.headers, ...options?.headers },
            body: {
                ...this.#options.body,
                ...options?.body,
            },
            streamProtocol: this.#streamProtocol,
            fetch: this.#options.fetch,
            // throttle streamed ui updates:
            setCompletion: completion => {
                this.completion = completion;
            },
            onData: data => {
                this.data.push(...data);
            },
            setLoading: loading => {
                this.#store.loading = loading;
            },
            setError: error => {
                this.#store.error = error;
            },
            setAbortController: abortController => {
                this.#abortController = abortController ?? undefined;
            },
            onResponse: this.#options.onResponse,
            onFinish: this.#options.onFinish,
            onError: this.#options.onError,
        });
    };
}
