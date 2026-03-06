import { type FetchFunction } from '@ai-sdk/provider-utils';
import { type DeepPartial, type Schema } from '@ai-sdk/ui-utils';
import { type z } from 'zod';
export type Experimental_StructuredObjectOptions<RESULT> = {
    /**
     * The API endpoint. It should stream JSON that matches the schema as chunked text.
     */
    api: string;
    /**
     * A Zod schema that defines the shape of the complete object.
     */
    schema: z.Schema<RESULT, z.ZodTypeDef, unknown> | Schema<RESULT>;
    /**
     * An unique identifier. If not provided, a random one will be
     * generated. When provided, the `useObject` hook with the same `id` will
     * have shared states across components.
     */
    id?: string;
    /**
     * An optional value for the initial object.
     */
    initialValue?: DeepPartial<RESULT>;
    /**
     * Custom fetch implementation. You can use it as a middleware to intercept requests,
     * or to provide a custom fetch implementation for e.g. testing.
     */
    fetch?: FetchFunction;
    /**
     * Callback that is called when the stream has finished.
     */
    onFinish?: (event: {
        /**
         * The generated object (typed according to the schema).
         * Can be undefined if the final object does not match the schema.
         */
        object: RESULT | undefined;
        /**
         * Optional error object. This is e.g. a TypeValidationError when the final object does not match the schema.
         */
        error: Error | undefined;
    }) => Promise<void> | void;
    /**
     * Callback function to be called when an error is encountered.
     */
    onError?: (error: Error) => void;
    /**
     * Additional HTTP headers to be included in the request.
     */
    headers?: Record<string, string> | Headers;
    /**
     * The credentials mode to be used for the fetch request.
     * Possible values are: 'omit', 'same-origin', 'include'.
     * Defaults to 'same-origin'.
     */
    credentials?: RequestCredentials;
};
export declare class StructuredObject<RESULT, INPUT = unknown> {
    #private;
    /**
     * The current value for the generated object. Updated as the API streams JSON chunks.
     */
    get object(): DeepPartial<RESULT> | undefined;
    /** The error object of the API request */
    get error(): Error | undefined;
    /**
     * Flag that indicates whether an API request is in progress.
     */
    get loading(): boolean;
    constructor(options: Experimental_StructuredObjectOptions<RESULT>);
    /**
     * Abort the current request immediately, keep the current partial object if any.
     */
    stop: () => void;
    /**
     * Calls the API with the provided input as JSON body.
     */
    submit: (input: INPUT) => Promise<void>;
}
//# sourceMappingURL=structured-object.svelte.d.ts.map