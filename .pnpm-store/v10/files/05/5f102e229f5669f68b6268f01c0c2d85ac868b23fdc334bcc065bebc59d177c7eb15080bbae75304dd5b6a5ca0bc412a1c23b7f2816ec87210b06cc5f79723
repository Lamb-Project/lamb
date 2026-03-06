import type { JSONValue, UIMessage } from '@ai-sdk/ui-utils';
import { KeyedStore } from './utils.svelte.js';
declare class ChatStore {
    messages: UIMessage[];
    data: JSONValue[] | undefined;
    status: "submitted" | "streaming" | "ready" | "error";
    error: Error | undefined;
}
export declare class KeyedChatStore extends KeyedStore<ChatStore> {
    constructor(value?: Iterable<readonly [string, ChatStore]> | null | undefined);
}
export declare const hasChatContext: () => boolean, getChatContext: () => KeyedChatStore, setChatContext: (value: KeyedChatStore) => KeyedChatStore;
export {};
//# sourceMappingURL=chat-context.svelte.d.ts.map