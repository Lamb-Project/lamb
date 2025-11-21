# Multimodal Support in LAMB

**Last Updated:** November 20, 2025
**Status:** ✅ Fully Implemented and Working

## Overview

LAMB now supports multimodal interactions through the OpenAI connector, allowing users to send images alongside text messages to vision-capable language models.

## Current Status ✅

**Multimodal support is fully functional** and tested with:
- ✅ OpenAI Vision API integration
- ✅ Graceful fallback to text-only when vision fails
- ✅ Comprehensive logging and debugging
- ✅ Backward compatibility with text-only requests
- ✅ Proper prompt template handling for multimodal content

## Supported Formats

### Message Format
LAMB supports OpenAI's standard multimodal message format:

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "text",
          "text": "What's in this image?"
        },
        {
          "type": "image_url",
          "image_url": {
            "url": "https://example.com/image.jpg"
          }
        }
      ]
    }
  ]
}
```

### Image Sources
- **HTTP/HTTPS URLs**: Direct links to publicly accessible images
- **Base64 Data URLs**: `data:image/jpeg;base64,{base64_data}`
- **File Uploads**: Images uploaded via multipart form data

### Supported Image Formats
- JPEG (.jpg, .jpeg)
- PNG (.png)
- GIF (.gif)
- WebP (.webp)

## API Usage

### Chat Completions with Images

```bash
curl -X POST "http://localhost:9099/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "model": "lamb_assistant.1",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "text",
            "text": "Describe this image:"
          },
          {
            "type": "image_url",
            "image_url": {
              "url": "https://example.com/image.jpg"
            }
          }
        ]
      }
    ]
  }'
```

### File Upload with Images

```bash
curl -X POST "http://localhost:9099/v1/chat/completions" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "model=lamb_assistant.1" \
  -F "messages=[{\"role\":\"user\",\"content\":[{\"type\":\"text\",\"text\":\"Analyze this:\"},{\"type\":\"image\",\"data\":\"<base64_data>\",\"mime_type\":\"image/jpeg\"}]}]" \
  -F "image=@image.jpg"
```

## Architecture

### Request Flow

```
Client Request
    ↓
Main API (/v1/chat/completions)
    ↓ (Parse multimodal messages)
Completion Pipeline
    ↓
Assistant Processing
    ↓
OpenAI Connector
    ↓ (Detect images → Try vision API)
Success → Return response
    ↓
Failure → Fallback to text-only + warning message
```

### Connector Logic

1. **Image Detection**: Check if any message contains image content
2. **Vision Attempt**: If images present, try OpenAI Vision API
3. **Fallback**: If vision fails, extract text content and add warning
4. **Response**: Return completion with appropriate handling

## Implementation Details

### OpenAI Connector Changes

#### Image Processing
- Parse multimodal content arrays
- Extract text and image components
- Validate image URLs/formats
- Convert to OpenAI Vision format

#### Prompt Processor Integration
- **Critical Fix**: Updated `simple_augment.py` to handle multimodal content in prompt templates
- When `assistant.prompt_template` contains `{user_input}`, extract text from multimodal arrays
- Combines all text parts from multimodal messages for template replacement
- Maintains backward compatibility with legacy string-only messages
- Handles both `list` (multimodal) and `str` (legacy) content types

#### Fallback Strategy
```python
# Pseudocode
if has_images(message):
    try:
        # Try vision API call
        response = await client.chat.completions.create(
            model=vision_model,
            messages=multimodal_messages
        )
        return response
    except Exception as e:
        # Fallback: extract text + add warning
        text_only_messages = extract_text_content(multimodal_messages)
        text_only_messages[0]["content"] = (
            "Unable to send image to the base LLM, multimodality is not supported. "
            + text_only_messages[0]["content"]
        )

        response = await client.chat.completions.create(
            model=fallback_model,
            messages=text_only_messages
        )
        return response
```

### Message Transformation

#### Multimodal → Vision Format
```python
def transform_to_vision_format(message):
    """Convert LAMB multimodal format to OpenAI Vision format"""
    if isinstance(message["content"], list):
        vision_content = []
        for item in message["content"]:
            if item["type"] == "text":
                vision_content.append({"type": "text", "text": item["text"]})
            elif item["type"] == "image_url":
                vision_content.append({
                    "type": "image_url",
                    "image_url": item["image_url"]
                })
        return vision_content
    else:
        # Legacy text-only format
        return message["content"]
```

#### Multimodal → Text Fallback
```python
def extract_text_for_fallback(message):
    """Extract only text content for fallback"""
    if isinstance(message["content"], list):
        text_parts = []
        for item in message["content"]:
            if item["type"] == "text":
                text_parts.append(item["text"])
        return " ".join(text_parts)
    else:
        return message["content"]
```

## Configuration

### Organization Settings
Vision support is controlled through organization configuration:

```json
{
  "providers": {
    "openai": {
      "enabled": true,
      "vision_enabled": true,
      "vision_models": ["gpt-4o", "gpt-4o-mini"],
      "fallback_model": "gpt-4o-mini"
    }
  }
}
```

### Environment Variables
```bash
# Enable vision features
OPENAI_VISION_ENABLED=true

# Default vision model
OPENAI_VISION_MODEL=gpt-4o

# Fallback model for non-vision failures
OPENAI_FALLBACK_MODEL=gpt-4o-mini
```

## Error Handling

### Vision API Failures
- **Rate Limits**: Fallback to text-only
- **Model Not Supported**: Fallback to text-only
- **Invalid Images**: Skip invalid images, continue with text
- **Network Errors**: Fallback to text-only

### Warning Messages
When fallback occurs, users receive:
```
Unable to send image to the base LLM, multimodality is not supported.
[Original text content]
```

### Debug Logging
Comprehensive logging implemented for multimodal request processing:

#### Request Level Logging (`backend/main.py`)
- HTTP method, URL, Content-Type headers
- Raw request body content (first 500 bytes)
- Multipart form field analysis
- Final parsed message structure with content types

#### Image Detection Logging (`backend/lamb/completions/connectors/openai.py`)
- Message-by-message analysis showing roles and content types
- Detailed detection results for multimodal vs text-only content
- Vision API attempt/failure logging with error details

#### Syntax Fixes
- Fixed f-string backslash syntax errors in logging code
- Resolved Python 3.11 f-string expression restrictions
- Proper variable extraction for complex logging expressions

## Validation

### Image Validation
- **File Size**: Maximum 20MB per image
- **Dimensions**: Reasonable limits (4096x4096 max)
- **Formats**: JPEG, PNG, GIF, WebP validation
- **URLs**: HTTP/HTTPS only, accessibility checks

### Security Considerations
- **URL Validation**: Prevent SSRF attacks
- **Content-Type Verification**: Ensure actual image data
- **Size Limits**: Prevent resource exhaustion
- **Rate Limiting**: Additional limits for vision requests

## Testing

### Test Cases
- Text-only messages (backward compatibility)
- Single image with text
- Multiple images with text
- Invalid image URLs
- Unsupported image formats
- Vision API failures
- Fallback behavior
- Streaming responses with images

### Example Tests

```python
def test_multimodal_fallback():
    """Test fallback when vision fails"""
    message = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Analyze:"},
            {"type": "image_url", "image_url": {"url": "invalid.jpg"}}
        ]
    }

    # Should return text-only response with warning
    response = await llm_connect([message], model="gpt-3.5-turbo")
    assert "Unable to send image" in response["choices"][0]["message"]["content"]
```

### Successful Implementation Tests
- ✅ Multimodal requests with image URLs processed correctly
- ✅ Vision API integration working with OpenAI GPT-4o
- ✅ Graceful fallback when vision API unavailable
- ✅ Prompt templates handle multimodal content properly
- ✅ Comprehensive logging captures all request processing steps
- ✅ Backward compatibility maintained for text-only requests

## Limitations

### Current Limitations
- **OpenAI Only**: Only OpenAI connector supports vision
- **Vision Models**: Requires vision-capable models (gpt-4o, gpt-4o-mini)
- **Single Connector**: Ollama connector not yet supported
- **No Image Storage**: Images not stored locally
- **URL Dependency**: Requires accessible image URLs

### Future Enhancements
- Ollama vision model support
- Local image storage and processing
- Advanced image preprocessing
- Vision model selection logic
- Batch image processing

## Troubleshooting

### Common Issues

#### Images Not Processed
- Check if vision models are configured
- Verify image URLs are accessible
- Ensure proper message format
- Check backend logs for image detection results

#### TypeError: can only concatenate str (not "list") to str
- **Issue**: Prompt processor expects string content but receives multimodal list
- **Fix**: Updated `simple_augment.py` to extract text from multimodal arrays
- **Symptoms**: HTTP 500 error when sending multimodal requests to assistants with prompt templates

#### SyntaxError: f-string expression part cannot include a backslash
- **Issue**: Python 3.11 f-string restrictions on backslash usage
- **Fix**: Extract complex expressions to variables before f-string formatting
- **Symptoms**: Backend fails to start with syntax errors in logging code

#### Fallback Messages
- Vision API temporarily unavailable
- Model doesn't support vision
- Invalid image data
- Check logs for detailed fallback reasons

#### Performance Issues
- Large images slow down responses
- Multiple images increase processing time
- Network latency for image downloads
- Enable debug logging to identify bottlenecks

### Debug Information
Enable debug logging to see multimodal request processing:
```python
import logging
logging.getLogger("multimodal").setLevel(logging.DEBUG)
logging.getLogger("multimodal.openai").setLevel(logging.DEBUG)
```

This will show:
- Raw request analysis and message parsing
- Image detection results for each message
- Vision API attempts and fallback triggers
- Prompt processor multimodal content extraction

## Vision Capabilities in Models API

### Models Endpoint with Capabilities

LAMB's `/v1/models` endpoint now includes vision capabilities information:

```json
{
  "object": "list",
  "data": [
    {
      "id": "lamb_assistant.1",
      "object": "model",
      "created": 1677609600,
      "owned_by": "lamb_v4",
      "capabilities": {
        "vision": true
      }
    },
    {
      "id": "lamb_assistant.2",
      "object": "model",
      "created": 1677609600,
      "owned_by": "lamb_v4",
      "capabilities": {
        "vision": false
      }
    }
  ]
}
```

**Capabilities Field:**
- `vision`: Boolean indicating if the assistant supports image processing
- Defaults to `false` for backward compatibility
- Only `true` for assistants with OpenAI connector and vision enabled

### Frontend Assistant Configuration

#### Vision Capability Toggle

In the assistant creation/editing form, users see a vision capability toggle:

```svelte
<!-- Only shown when OpenAI connector is selected -->
<label class="flex items-center space-x-3 cursor-pointer">
  <input type="checkbox" bind:checked={visionEnabled} class="toggle toggle-primary" />
  <div>
    <span class="text-sm font-medium text-gray-700">Enable Vision Capability</span>
    <p class="text-xs text-gray-500 mt-1">
      Allow this assistant to process images alongside text messages
    </p>
  </div>
</label>
```

#### Validation Rules

- Vision toggle only appears for OpenAI connector
- Automatically disabled when switching to non-OpenAI connectors
- Stored in assistant metadata under `capabilities.vision`

### Metadata Storage Structure

Vision capability is stored in the assistant's metadata JSON:

```json
{
  "connector": "openai",
  "llm": "gpt-4o",
  "prompt_processor": "simple_augment",
  "rag_processor": "simple_rag",
  "capabilities": {
    "vision": true
  }
}
```

**Storage Location:** `assistants.api_callback` column (as JSON string)

### Implementation Details

#### Backend Changes

**File:** `backend/main.py`

- Added `_get_assistant_capabilities()` helper function
- Enhanced `/v1/models` endpoint to include capabilities
- Parses metadata from `api_callback` column
- Provides backward compatibility for assistants without capabilities

#### Frontend Changes

**File:** `frontend/svelte-app/src/lib/components/assistants/AssistantForm.svelte`

- Added `visionEnabled` state variable
- Added vision toggle UI (conditional on OpenAI connector)
- Updated metadata parsing to load vision capability
- Updated metadata construction to save vision capability
- Added connector change validation (auto-disable vision for non-OpenAI)
- Added form reset logic for vision capability

## API Reference

### Request Parameters
- `messages`: Array of message objects (multimodal support)
- `model`: Assistant model identifier
- `stream`: Enable streaming responses
- `max_tokens`: Maximum response length

### Response Format
Standard OpenAI Chat Completion format, with multimodal content in messages.

### Models Response Format
Extended OpenAI models format with capabilities information.

### Error Codes
- `400`: Invalid image format or size
- `422`: Unsupported message format
- `500`: Vision API failure (with fallback)
- `503`: Service temporarily unavailable

## Migration Guide

### For Existing Integrations
- No changes required for text-only requests
- Multimodal requests use new content format
- Backward compatibility maintained

### For Assistant Authors
- Assistants can now handle image inputs
- Prompt templates may need updates for multimodal context
- Test with vision-capable models

## Performance Considerations

### Latency Impact
- Image downloads add network latency
- Vision models may be slower than text-only models
- Base64 encoding/decoding overhead

### Cost Impact
- Vision API calls may have different pricing
- Larger context windows for image data
- Potential for higher token usage

### Optimization Strategies
- Image preprocessing and resizing
- Caching frequently used images
- Asynchronous image processing
- Model selection based on image complexity
