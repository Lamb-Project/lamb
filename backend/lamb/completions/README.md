# Completion system-prompt context (0.9)

The completion workflow initializes the assistant's base system prompt once per
conversation, applies conversation-start filters, and reuses that prompt for all
later turns. This includes assistants without filters and every prompt processor.
RAG, prompt-template expansion and message assembly still run on every request.
Edits to base instructions or filters affect new conversations.

## Saved conversations

Creator chat and native Open WebUI retain context through their existing verified
conversation adapters. API-key callers may use `POST /v1/conversations` and pass
the returned `id` as `conversation_id` to `/v1/chat/completions`. Existing random
values from #553 are retained. Storage keeps the existing schema-35 table name
`prompt_filter_states` for compatibility; lifecycle code is now in
`conversation_state.py`.

Older chats with no retained prompt, including the old unfiltered `null` sentinel,
return 409 asking for a new conversation. No original prompt can be reconstructed
reliably from the current assistant definition. The old chat is not deleted.

## Calls without a saved conversation ID

A fresh single-turn completion works without an ID, including enabled filters.
To continue using caller-held context, an authorized backend may request:

```json
{
  "model": "lamb_assistant.42",
  "messages": [{"role": "user", "content": "What is your budget?"}],
  "return_prompt_context": true,
  "stream": false
}
```

The response includes `prompt_context` alongside the ordinary completion fields:

```json
{
  "version": 1,
  "assistant_id": 42,
  "organization_id": 3,
  "system_prompt": "The initialized instructions for this conversation."
}
```

Retain that exact object and send it as `prompt_context` with subsequent requests
and their conversation history. It is checked against the selected assistant and
organization. Do not combine it with `conversation_id` or a signed native-chat
reference. With `stream: true`, opting in emits an initial SSE `data` chunk with
`choices: []` and `prompt_context`; subsequent chunks use the normal connector
format. No prompt context is returned unless requested. The payload is limited to
100,000 prompt characters.

For compatibility, an authorized stateless API backend may supply one leading
`system` message instead. That message is treated as already initialized and is
not filtered; the adapter removes it from history and supplies it as the base
prompt. Use either this form or `prompt_context`, not both. Other caller-supplied
`system` or `developer` messages are rejected. A request containing prior assistant
answers without initialized context or a saved conversation returns 409. A request
without such history or context is a fresh call; the caller must retain context
when retrying or sending only the latest message of an existing conversation.

Saved evaluation fixtures explicitly initialize ephemeral context, even when the
fixture includes multiple turns. In-process callers can retain a `PromptContext`
object across calls using `run_lamb_assistant(..., prompt_context=context)`.

## Trust and processor compatibility

Caller-held context is for trusted backends. Creator API keys remain limited to
their own published assistants; service keys carry the service's existing scope.
The caller owns authoritative history, permitted resets and intended behavior.
This context is not an authentication token and cannot grant resource access.
LAMB still enforces entry-point authentication, current permissions, conversation
ownership and organization isolation. Never expose service credentials or treat a
learner's browser as the authoritative source of teacher instructions.

The native Open WebUI inlet strips context-return/override options and forwards
verified chat identity instead. Saved chats reject caller-supplied privileged
message roles. Prompts are not secret storage or an authorization mechanism.

Processors receive the resolved base prompt in a request-local assistant copy.
The common dispatcher ensures one exact base system message is first, removing
exact duplicate copies produced by legacy processors. A processor may emit
separate dynamic system messages; these still change per request. Processors that
embed the base text inside another system message should separate it to avoid
repeating instructions. Filters never traverse assembled messages or RAG content.
