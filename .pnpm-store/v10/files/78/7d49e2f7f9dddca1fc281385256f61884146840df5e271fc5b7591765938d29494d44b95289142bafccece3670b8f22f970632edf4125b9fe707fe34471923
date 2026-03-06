import { type UseCompletionOptions, type JSONValue, type RequestOptions } from '@ai-sdk/ui-utils';
export type CompletionOptions = Readonly<UseCompletionOptions>;
export declare class Completion {
    #private;
    /** The current completion result */
    get completion(): string;
    set completion(value: string);
    /**
     * Additional data added on the server via StreamData.
     *
     * This is writable, so you can use it to transform or clear the chat data.
     */
    get data(): JSONValue[];
    set data(value: JSONValue[]);
    /** The error object of the API request */
    get error(): Error | undefined;
    /** The current value of the input. Writable, so it can be bound to form inputs. */
    input: string;
    /**
     * Flag that indicates whether an API request is in progress.
     */
    get loading(): boolean;
    constructor(options?: CompletionOptions);
    /**
     * Abort the current request immediately, keep the generated tokens if any.
     */
    stop: () => void;
    /**
     * Send a new prompt to the API endpoint and update the completion state.
     */
    complete: (prompt: string, options?: RequestOptions) => Promise<string | null | undefined>;
    /** Form submission handler to automatically reset input and call the completion API */
    handleSubmit: (event?: {
        preventDefault?: () => void;
    }) => Promise<void>;
}
//# sourceMappingURL=completion.svelte.d.ts.map