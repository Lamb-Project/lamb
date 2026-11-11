---
id: configure-agent
name: Agent configuration
description: Explain current model availability and who can change the agent configuration
optional_context: [language]
---

Read `lamb assistant config` for the organisation's actual model availability and defaults. Distinguish the assistant completion defaults from the AAC driver recorded in the session response policy; do not infer one from the other.

The trusted session brief states the administration level. If it is `none`, explain which setting the user needs and ask them to contact their organisation administrator. Do not provide administrative procedures or offer to change a setting. You may continue with assistant configuration using available models.

If the brief grants an administrative layer, follow that layer's configuration instructions. Do not invent a settings command that is absent from the generated command reference. Any UI-only change must be described as a user action. Do not claim a change from showing the form or from a user's intention; verify what is observable and state any verification limit.

A session's starting language remains fixed. Explain an organisation's configured fallback when it applies; changing the frontend language does not change an existing session. Offer a new conversation for a different session language.
