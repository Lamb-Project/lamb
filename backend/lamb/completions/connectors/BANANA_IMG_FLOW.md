# Banana Image Connector Flow Diagram

## Request Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Request                               │
│  (Open WebUI, API Client, or other chat interface)                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ POST /v1/chat/completions
                             │ {"model": "lamb_assistant.123", "messages": [...]}
                             ▼
                    ┌────────────────────┐
                    │  Banana IMG        │
                    │  Connector         │
                    │  llm_connect()     │
                    └────────┬───────────┘
                             │
                             │ _is_title_generation_request()?
                             │
                ┌────────────┴────────────┐
                │                         │
          YES   │                         │   NO
    (Title      │                         │   (Image
     Request)   ▼                         ▼    Request)
        ┌───────────────────┐     ┌──────────────────┐
        │ GPT-4o-mini       │     │ Vertex AI        │
        │ Title Generation  │     │ Imagen           │
        └─────────┬─────────┘     └────────┬─────────┘
                  │                         │
                  │ 1. Get org OpenAI key   │ 1. Get org GCP project
                  │ 2. Call GPT-4o-mini     │ 2. Initialize Vertex AI
                  │ 3. Return text response │ 3. Generate image(s)
                  │                         │ 4. Save to filesystem
                  │                         │ 5. Generate markdown
                  ▼                         ▼
        ┌───────────────────┐     ┌──────────────────┐
        │  Text Response    │     │ Markdown Response│
        │  {                │     │  {               │
        │   "content":      │     │   "content":     │
        │     "Title text"  │     │     "![img](...)"│
        │  }                │     │  }               │
        └─────────┬─────────┘     └────────┬─────────┘
                  │                         │
                  └──────────┬──────────────┘
                             │
                             ▼
                    ┌────────────────────┐
                    │   Client Receives  │
                    │   Response         │
                    └────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
          Title │                         │ Image
        Response│                         │ Response
                ▼                         ▼
        ┌───────────────┐         ┌──────────────────┐
        │ Open WebUI    │         │ Open WebUI       │
        │ sets chat     │         │ renders markdown │
        │ title/tags    │         │ displays image   │
        └───────────────┘         └──────────────────┘
```

## Title Detection Logic

```
┌─────────────────────────────────────────────────┐
│  _is_title_generation_request(messages)         │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Extract last user    │
        │ message content      │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ Check against        │
        │ patterns:            │
        │ - "generate.*title"  │
        │ - "create.*title"    │
        │ - "suggest.*title"   │
        │ - "generate.*tags"   │
        │ - "categorizing.*    │
        │    themes"           │
        │ - "chat history"     │
        │ - "conversation      │
        │    title"            │
        │ - "summarize.*       │
        │    conversation"     │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ Pattern match?       │
        └──────┬───────────────┘
               │
      ┌────────┴────────┐
      │                 │
     YES               NO
      │                 │
      ▼                 ▼
┌──────────┐     ┌──────────────┐
│ Return   │     │ Return       │
│ True     │     │ False        │
└──────────┘     └──────────────┘
```

## Image Storage Flow

```
┌─────────────────────────────────────────────────┐
│  Image Generation Complete                       │
│  (Vertex AI returns PIL Image objects)          │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Sanitize user email  │
        │ user@example.com →   │
        │ user_at_example_com  │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────────────────────┐
        │ Create directory (if needed):    │
        │ /backend/static/public/          │
        │   {user_id}/img/                 │
        └──────┬───────────────────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ Generate filename:   │
        │ img_{timestamp}_     │
        │ {uuid}.{format}      │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ Save image to file:  │
        │ image.save(path)     │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ Generate public URL: │
        │ /static/public/      │
        │ {user_id}/img/       │
        │ {filename}           │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ Create markdown:     │
        │ ![Generated Image]   │
        │ ({url})              │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ Return chat          │
        │ completion with      │
        │ markdown content     │
        └──────────────────────┘
```

## Configuration Resolution

```
┌─────────────────────────────────────────────────┐
│  Get Organization Configuration                  │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ assistant_owner      │
        │ provided?            │
        └──────┬───────────────┘
               │
      ┌────────┴────────┐
      │                 │
     YES               NO
      │                 │
      ▼                 ▼
┌──────────────┐  ┌─────────────────┐
│ Get org      │  │ Use environment │
│ config via   │  │ variables       │
│ resolver     │  └────────┬────────┘
└──────┬───────┘           │
       │                   │
       ▼                   │
┌──────────────┐           │
│ Org config   │           │
│ found?       │           │
└──────┬───────┘           │
       │                   │
  ┌────┴────┐              │
  │         │              │
 YES       NO              │
  │         │              │
  ▼         └──────────────┘
┌──────────────┐           │
│ Use org      │◄──────────┘
│ API keys     │
└──────────────┘

For Title Generation:
- Look for "openai" provider in org config
- Get api_key, base_url, models
- Prefer gpt-4o-mini if available
- Fallback to env: OPENAI_API_KEY

For Image Generation:
- Look for "google" provider in org config
- Get project_id, location
- Fallback to env: GOOGLE_CLOUD_PROJECT
```

## Error Handling

```
┌─────────────────────────────────────────────────┐
│  Request Processing                              │
└──────────────────┬──────────────────────────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Try operation        │
        └──────┬───────────────┘
               │
               ▼
        ┌──────────────────────┐
        │ Exception raised?    │
        └──────┬───────────────┘
               │
      ┌────────┴────────┐
      │                 │
     YES               NO
      │                 │
      ▼                 ▼
┌──────────────────┐  ┌──────────────┐
│ Log error with   │  │ Return       │
│ emoji indicator: │  │ success      │
│ ❌ operation     │  │ response     │
│ failed: {error}  │  └──────────────┘
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Raise ValueError │
│ with descriptive │
│ message          │
└──────────────────┘
```

## Integration with Chat Interface

```
Open WebUI Behavior:

1. User sends message
   ┌─────────────────────┐
   │ "Draw a sunset"     │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ LAMB Backend        │
   │ banana_img          │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ Returns markdown    │
   │ ![img](url)         │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ OWI renders markdown│
   │ displays image      │
   └─────────────────────┘

2. OWI requests title
   ┌─────────────────────┐
   │ "Generate title     │
   │  for chat history"  │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ LAMB Backend        │
   │ banana_img          │
   │ (detects pattern)   │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ Routes to GPT-4o-   │
   │ mini, returns text  │
   └──────────┬──────────┘
              │
              ▼
   ┌─────────────────────┐
   │ OWI sets chat title │
   └─────────────────────┘
```

