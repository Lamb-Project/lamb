import { createContext, KeyedStore } from './utils.svelte.js';
class ChatStore {
    messages = $state([]);
    data = $state();
    status = $state('ready');
    error = $state();
}
export class KeyedChatStore extends KeyedStore {
    constructor(value) {
        super(ChatStore, value);
    }
}
export const { hasContext: hasChatContext, getContext: getChatContext, setContext: setChatContext, } = createContext('Chat');
