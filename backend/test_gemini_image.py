#!/usr/bin/env python3
"""
Test script for Gemini image generation using Google Gen AI.

Usage:
    python test_gemini_image.py "a beautiful sunset over mountains"

Environment variables (from .env file or environment):
    GOOGLE_API_KEY: Google Gen AI API key (required)
    GOOGLE_CLOUD_LOCATION: Google Cloud location (optional)
    GOOGLE_CLOUD_PROJECT: Google Cloud project ID (optional)
"""

import os
import sys
import base64
import logging
import time
import uuid
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv
from google import genai
from PIL import Image
from lamb.logging_config import get_logger

# Load environment variables from .env file
load_dotenv()

logger = get_logger(__name__, component="MAIN")


def main():
    # Check for prompt argument
    if len(sys.argv) < 2:
        print("Usage: python test_gemini_image.py \"your prompt here\"")
        sys.exit(1)
    
    prompt = sys.argv[1]
    
    # Get environment variables
    api_key = os.getenv("GOOGLE_API_KEY")
    cloud_location = os.getenv("GOOGLE_CLOUD_LOCATION")
    cloud_project = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    if not api_key:
        logger.error("❌ GOOGLE_API_KEY not found in .env file or environment variables")
        logger.error("   Please set GOOGLE_API_KEY in backend/.env file")
        sys.exit(1)
    
    logger.info(f"🔑 Using API key: {api_key[:10]}...")
    if cloud_location:
        logger.info(f"📍 Cloud location: {cloud_location}")
    else:
        logger.info("📍 Cloud location: not set (using default)")
    if cloud_project:
        logger.info(f"🏗️  Cloud project: {cloud_project}")
    else:
        logger.info("🏗️  Cloud project: not set (using default)")
    
    # Initialize Google Gen AI client
    try:
        logger.info("🔧 Initializing Google Gen AI client...")
        client = genai.Client(api_key=api_key)
        logger.info("✅ Client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize client: {e}")
        sys.exit(1)
    
    # Generate image using Gemini model
    model = "gemini-2.5-flash-image"
    logger.info(f"🖼️  Generating image with model: {model}")
    logger.info(f"📝 Prompt: {prompt}")
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        logger.info("✅ Image generation request completed")
    except Exception as e:
        logger.error(f"❌ Failed to generate image: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
    
    # Extract images from response
    generated_images = []
    if hasattr(response, 'candidates') and response.candidates:
        logger.info(f"📦 Found {len(response.candidates)} candidate(s)")
        for candidate in response.candidates:
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                logger.info(f"📄 Found {len(candidate.content.parts)} part(s) in candidate")
                for part in candidate.content.parts:
                    if hasattr(part, 'inline_data'):
                        logger.info("🖼️  Found inline_data (image)")
                        inline_data = part.inline_data
                        logger.debug(f"   inline_data type: {type(inline_data)}")
                        logger.debug(f"   inline_data attributes: {[a for a in dir(inline_data) if not a.startswith('_')]}")
                        generated_images.append(inline_data)
                    else:
                        logger.debug(f"Part type: {type(part)}, attributes: {[a for a in dir(part) if not a.startswith('_')]}")
    
    if not generated_images:
        logger.error("❌ No images found in response")
        logger.error(f"Response type: {type(response)}")
        logger.error(f"Response attributes: {[a for a in dir(response) if not a.startswith('_')]}")
        sys.exit(1)
    
    logger.info(f"✅ Extracted {len(generated_images)} image(s)")
    
    # Process and save images
    output_dir = Path(__file__).parent / "test_output"
    output_dir.mkdir(exist_ok=True)
    
    for i, generated_image in enumerate(generated_images):
        try:
            # Skip None images
            if generated_image is None:
                logger.warning(f"⚠️  Image {i+1} is None, skipping")
                continue
            
            # Get mime type early (needed for output format)
            mime_type = 'image/png'  # default
            
            # Handle Gemini inline_data format
            if hasattr(generated_image, 'data') or hasattr(generated_image, 'mime_type'):
                logger.info(f"📸 Processing image {i+1} (inline_data format)")
                
                # Get mime type if available
                mime_type = getattr(generated_image, 'mime_type', 'image/png')
                logger.info(f"   MIME type: {mime_type}")
                
                # Debug: Check available attributes and methods
                available_attrs = [a for a in dir(generated_image) if not a.startswith('_')]
                logger.debug(f"   Available attributes: {available_attrs}")
                
                # Check if there's a helper method to get the image
                pil_image = None
                if hasattr(generated_image, 'as_image') and callable(getattr(generated_image, 'as_image')):
                    logger.info("   Using as_image() method")
                    try:
                        pil_image = generated_image.as_image()
                        logger.info("   ✅ Successfully got image via as_image()")
                    except Exception as e:
                        logger.warning(f"   as_image() failed: {e}, trying data attribute")
                
                if pil_image is None:
                    # Try using data attribute
                    data_value = generated_image.data
                    logger.info(f"   Data type: {type(data_value)}")
                    
                    if isinstance(data_value, (str, bytes)):
                        logger.info(f"   Data length: {len(data_value)}")
                    
                    # Try different decoding approaches
                    image_bytes = None
                    if isinstance(data_value, bytes):
                        # Already bytes, use directly
                        logger.info("   Data is already bytes, using directly")
                        image_bytes = data_value
                        # Debug: Check first few bytes to identify format
                        if len(image_bytes) >= 4:
                            header = image_bytes[:4]
                            logger.debug(f"   First 4 bytes (hex): {header.hex()}")
                            # PNG: 89 50 4E 47
                            # JPEG: FF D8 FF E0 or FF D8 FF E1
                            if header.startswith(b'\x89PNG'):
                                logger.debug("   Detected PNG format")
                            elif header.startswith(b'\xff\xd8\xff'):
                                logger.debug("   Detected JPEG format")
                            else:
                                logger.warning(f"   Unknown image format header: {header.hex()}")
                    elif isinstance(data_value, str):
                        # Try base64 decode
                        logger.info("   Data is string, attempting base64 decode")
                        logger.debug(f"   String preview (first 50 chars): {data_value[:50]}...")
                        try:
                            image_bytes = base64.b64decode(data_value)
                            logger.info("   Successfully decoded base64")
                        except Exception as decode_error:
                            logger.error(f"   Failed to decode base64: {decode_error}")
                            # Maybe it's a data URL?
                            if data_value.startswith('data:'):
                                logger.info("   Detected data URL format, extracting base64")
                                # Extract base64 part from data URL
                                base64_part = data_value.split(',')[1] if ',' in data_value else data_value
                                image_bytes = base64.b64decode(base64_part)
                            else:
                                raise ValueError(f"Cannot decode image data: {decode_error}")
                    else:
                        raise ValueError(f"Unknown data type: {type(data_value)}")
                    
                    # Now try to open the image
                    logger.info(f"   Attempting to open image (size: {len(image_bytes)} bytes)")
                    if len(image_bytes) == 0:
                        raise ValueError("Image data is empty")
                    
                    # Create BytesIO and ensure pointer is at start
                    image_buffer = BytesIO(image_bytes)
                    image_buffer.seek(0)
                    
                    # Try to identify the format first
                    try:
                        pil_image = Image.open(image_buffer)
                        # Verify it's a valid image
                        pil_image.verify()
                        logger.info(f"   ✅ Successfully opened and verified image")
                        # Reopen after verify (verify closes the image)
                        image_buffer.seek(0)
                        pil_image = Image.open(image_buffer)
                    except Exception as img_error:
                        logger.error(f"   Failed to open image: {img_error}")
                        # Try to save raw bytes for debugging
                        debug_file = output_dir / f"debug_raw_data_{i+1}.bin"
                        with open(debug_file, 'wb') as f:
                            f.write(image_bytes)
                        logger.error(f"   Saved raw data to {debug_file} for debugging")
                        raise
            else:
                logger.error(f"❌ Unknown image format: {type(generated_image)}")
                logger.error(f"   Attributes: {[a for a in dir(generated_image) if not a.startswith('_')]}")
                continue
            
            # Verify we have a valid PIL Image
            if pil_image is None:
                logger.error(f"❌ Failed to extract image data for image {i+1}")
                continue
            
            # Check if it's actually a PIL Image
            if not isinstance(pil_image, Image.Image):
                logger.warning(f"   Image object is not standard PIL Image: {type(pil_image)}")
                # Try to convert if possible
                if hasattr(pil_image, '_pil_image'):
                    pil_image = pil_image._pil_image
                else:
                    logger.error(f"   Cannot convert to PIL Image")
                    continue
            
            # Convert to RGB if necessary (for JPEG compatibility)
            if hasattr(pil_image, 'mode') and pil_image.mode != 'RGB':
                logger.info(f"   Converting from {pil_image.mode} to RGB")
                pil_image = pil_image.convert('RGB')
            
            # Determine output format from mime type
            if 'jpeg' in mime_type or 'jpg' in mime_type:
                output_format = 'JPEG'
                extension = 'jpg'
            elif 'png' in mime_type:
                output_format = 'PNG'
                extension = 'png'
            elif 'webp' in mime_type:
                output_format = 'WEBP'
                extension = 'webp'
            else:
                output_format = 'PNG'
                extension = 'png'
            
            # Generate filename
            timestamp = int(time.time() * 1000)
            unique_id = str(uuid.uuid4())[:8]
            filename = f"gemini_test_{timestamp}_{unique_id}.{extension}"
            file_path = output_dir / filename
            
            # Save image - try with format parameter first, fallback to extension-based
            logger.info(f"💾 Saving image {i+1} to: {file_path}")
            try:
                # PIL Image.save() accepts format as second positional or keyword argument
                pil_image.save(str(file_path), format=output_format)
            except TypeError:
                # Fallback: let PIL detect format from extension
                logger.info(f"   Format parameter failed, using extension-based detection")
                pil_image.save(str(file_path))
            
            # Verify file was created
            if file_path.exists():
                file_size = file_path.stat().st_size
                logger.info(f"✅ Image {i+1} saved successfully!")
                logger.info(f"   File: {file_path}")
                logger.info(f"   Size: {file_size} bytes")
                logger.info(f"   Format: {output_format}")
                logger.info(f"   Dimensions: {pil_image.size[0]}x{pil_image.size[1]}")
            else:
                logger.error(f"❌ File was not created: {file_path}")
                
        except Exception as img_error:
            logger.error(f"❌ Error processing image {i+1}: {img_error}")
            import traceback
            logger.error(traceback.format_exc())
            continue
    
    logger.info("🎉 Test completed!")


if __name__ == "__main__":
    main()

