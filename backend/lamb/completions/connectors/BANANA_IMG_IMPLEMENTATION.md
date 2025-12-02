# Banana Image Connector Implementation

## Overview

The `banana_img.py` connector has been enhanced to intelligently handle both image generation requests and chat interface metadata requests (titles/tags).

## Key Changes

### 1. Request Type Detection

Added `_is_title_generation_request()` function that uses regex pattern matching to detect when Open WebUI or other chat interfaces are requesting conversation titles or tags instead of actual image generation.

**Detection Patterns:**
- "generate.*title"
- "create.*title"
- "suggest.*title"
- "generate.*tags"
- "categorizing.*themes"
- "chat history"
- "conversation title"
- "summarize.*conversation"

### 2. Intelligent Routing

The connector now routes requests based on detected type:

- **Title/Tags Requests** → `_generate_title_with_gpt()` using GPT-4o-mini
- **Image Generation Requests** → Vertex AI Imagen (original behavior)

### 3. Title Generation with GPT-4o-mini

Added `_generate_title_with_gpt()` function that:
- Uses organization-specific OpenAI configuration
- Falls back to environment variables if needed
- Selects gpt-4o-mini or smallest available model
- Returns OpenAI-compatible chat completion format

### 4. Image Storage System

Images are now saved to the filesystem instead of being base64-encoded:

**Storage Path:**
```
/backend/static/public/{user_id}/img/{filename}
```

**Filename Format:**
```
img_{timestamp}_{uuid}.{format}
```

**Example:**
```
/backend/static/public/user_at_example_com/img/img_1701234567890_a1b2c3d4.jpeg
```

### 5. Markdown Response Format

Instead of returning base64-encoded images in JSON, the connector now returns markdown with image links:

**Single Image:**
```markdown
![Generated Image](/static/public/user_at_example_com/img/img_1701234567890_a1b2c3d4.jpeg)
```

**Multiple Images:**
```markdown
![Generated Image 1](/static/public/user_at_example_com/img/img_1701234567890_a1b2c3d4.jpeg)

![Generated Image 2](/static/public/user_at_example_com/img/img_1701234568123_b2c3d4e5.jpeg)
```

### 6. User-Specific Directories

Each user gets their own image directory based on sanitized email:
- `user@example.com` → `user_at_example_com`
- Prevents conflicts between users
- Enables per-user cleanup if needed

## Technical Details

### New Imports

```python
import time
import uuid
import re
from pathlib import Path
from openai import AsyncOpenAI
```

### Modified Functions

1. **`llm_connect()`** - Added routing logic at the beginning
2. **Image processing** - Changed from base64 to file storage
3. **Response format** - Changed from custom image response to chat completion with markdown

### New Functions

1. **`_is_title_generation_request(messages)`** - Detects title requests
2. **`_generate_title_with_gpt(messages, assistant_owner, project_id)`** - Generates titles

## Configuration Requirements

### Organization Config

```json
{
  "google": {
    "enabled": true,
    "project_id": "my-project-id",
    "location": "us-central1"
  },
  "openai": {
    "enabled": true,
    "api_key": "sk-...",
    "models": ["gpt-4o-mini", "gpt-4o"]
  }
}
```

### Environment Variables (Fallback)

```bash
# For Vertex AI Imagen
GOOGLE_CLOUD_PROJECT=my-project-id
GOOGLE_CLOUD_LOCATION=us-central1

# For title generation
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://api.openai.com/v1
```

## Testing

### Test Title Generation

```bash
curl -X POST http://localhost:9099/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lamb_assistant.YOUR_ASSISTANT_ID",
    "messages": [
      {
        "role": "user",
        "content": "Generate a title for this conversation about AI"
      }
    ]
  }'
```

**Expected:** JSON response with text content (not an image).

### Test Image Generation

```bash
curl -X POST http://localhost:9099/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lamb_assistant.YOUR_ASSISTANT_ID",
    "messages": [
      {
        "role": "user",
        "content": "A beautiful sunset over mountains"
      }
    ],
    "aspect_ratio": "16:9"
  }'
```

**Expected:** JSON response with markdown image link in content.

### Verify Image Storage

After successful image generation:

```bash
ls -la backend/static/public/*/img/
```

Should show generated images.

### Test in Open WebUI

1. Create assistant with `banana_img` connector
2. Publish assistant to Open WebUI
3. Open chat with assistant
4. Send image generation prompt
5. Verify image displays inline in chat
6. Check conversation title generation works automatically

## Logging

The connector includes emoji-rich logging for debugging:

- 🎯 Detected title generation request
- 📝 Generating title using GPT-4o-mini
- 🔀 Routing to GPT-4o-mini for title generation
- 🍌 Calling Vertex AI Image Generation
- 📁 Image storage directory created
- 💾 Image saved to filesystem
- ✅ Generated images with markdown

## Benefits

1. **Chat Interface Compatibility**: Handles Open WebUI's title/tags requests gracefully
2. **Better Performance**: No large base64 payloads in JSON responses
3. **Persistent Images**: Images stored permanently (can be referenced later)
4. **Bandwidth Efficiency**: Markdown links instead of embedded data
5. **User Isolation**: Each user has separate image directory
6. **Organization-Aware**: Respects org-specific API keys for both services

## Potential Improvements

1. **Image Cleanup**: Add TTL or manual cleanup mechanism
2. **CDN Integration**: Serve images from CDN instead of backend
3. **Thumbnail Generation**: Create thumbnails for faster loading
4. **Image Metadata**: Store generation parameters with images
5. **Usage Tracking**: Log image generation for analytics
6. **Rate Limiting**: Prevent abuse of image generation

## Migration Notes

If you have existing assistants using `banana_img` connector:

- **No migration needed** - Changes are backward compatible
- **Storage space** - Monitor disk usage as images accumulate
- **Static file serving** - Ensure `/static/public/` is properly served by backend

## Support

For issues or questions:
- Check logs for emoji indicators
- Verify organization config has both `google` and `openai` providers
- Ensure static file directory has write permissions
- Test title generation separately from image generation

