import { type UIMessage, type UseChatOptions, type JSONValue, type Message, type CreateMessage, type ChatRequestOptions } from '@ai-sdk/ui-utils';
export type ChatOptions = Readonly<Omit<UseChatOptions, 'keepLastMessageOnError'> & {
    /**
     * Maximum number of sequential LLM calls (steps), e.g. when you use tool calls.
     * Must be at least 1.
     * A maximum number is required to prevent infinite loops in the case of misconfigured tools.
     * By default, it's set to 1, which means that only a single LLM call is made.
     * @default 1
     */
    maxSteps?: number;
}>;
export type { CreateMessage, Message, UIMessage };
export declare class Chat {
    #private;
    /**
     * The id of the chat. If not provided through the constructor, a random ID will be generated
     * using the provided `generateId` function, or a built-in function if not provided.
     */
    readonly id: string;
    /**
     * Additional data added on the server via StreamData.
     *
     * This is writable, so you can use it to transform or clear the chat data.
     */
    get data(): JSONValue[] | undefined;
    set data(value: JSONValue[] | undefined);
    /**
     * Hook status:
     *
     * - `submitted`: The message has been sent to the API and we're awaiting the start of the response stream.
     * - `streaming`: The response is actively streaming in from the API, receiving chunks of data.
     * - `ready`: The full response has been received and processed; a new user message can be submitted.
     * - `error`: An error occurred during the API request, preventing successful completion.
     */
    get status(): "submitted" | "streaming" | "ready" | "error";
    /** The error object of the API request */
    get error(): Error | undefined;
    /** The current value of the input. Writable, so it can be bound to form inputs. */
    input: string;
    /**
     * Current messages in the chat.
     *
     * This is writable, which is useful when you want to edit the messages on the client, and then
     * trigger {@link reload} to regenerate the AI response.
     */
    get messages(): UIMessage[];
    set messages(value: Message[]);
    constructor(options?: ChatOptions);
    /**
     * Append a user message to the chat list. This triggers the API call to fetch
     * the assistant's response.
     * @param message The message to append
     * @param options Additional options to pass to the API call
     */
    append: (message: Message | CreateMessage, { data, headers, body, experimental_attachments }?: ChatRequestOptions) => Promise<void>;
    /**
     * Reload the last AI chat response for the given chat history. If the last
     * message isn't from the assistant, it will request the API to generate a
     * new response.
     */
    reload: ({ data, headers, body }?: ChatRequestOptions) => Promise<void>;
    /**
     * Abort the current request immediately, keep the generated tokens if any.
     */
    stop: () => void;
    /** Form submission handler to automatically reset input and append a user message */
    handleSubmit: (event?: {
        preventDefault?: () => void;
    }, options?: ChatRequestOptions) => Promise<void>;
    addToolResult: ({ toolCallId, result, }: {
        toolCallId: string;
        result: unknown;
    }) => Promise<void>;
}
//# sourceMappingURL=chat.svelte.d.ts.map