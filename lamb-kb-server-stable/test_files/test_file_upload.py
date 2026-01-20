#!/usr/bin/env python3
"""
Test script for file uploading only.
This script focuses specifically on testing the file upload functionality
to diagnose issues with file ingestion.
"""

import os
import sys
import json
import time
import logging
import requests

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# API Configuration
API_URL = "http://localhost:9090"
API_TOKEN = "0p3n-w3bu!"  # Default token
COLLECTION_ID = 1  # Use our newly created collection

def test_file_upload(file_path, plugin_name="simple_ingest", chunk_size=100, chunk_unit="char", chunk_overlap=20):
    """Test uploading a file to the API."""
    # Verify file exists
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False
    
    file_size = os.path.getsize(file_path)
    logger.info(f"Testing file upload: {file_path} (size: {file_size} bytes)")
    
    # Prepare the URL
    url = f"{API_URL}/collections/{COLLECTION_ID}/ingest-file"
    logger.info(f"Target URL: {url}")
    
    # Prepare headers
    headers = {
        "Authorization": f"Bearer {API_TOKEN}"
    }
    logger.info(f"Using headers: {headers}")
    
    # Prepare plugin parameters
    plugin_params = {
        "chunk_size": chunk_size,
        "chunk_unit": chunk_unit, 
        "chunk_overlap": chunk_overlap
    }
    logger.info(f"Plugin params: {json.dumps(plugin_params)}")
    
    # Open file and create multipart form data
    try:
        with open(file_path, 'rb') as f:
            logger.info("File opened successfully")
            
            # Use a tuple for the file data: (filename, file_object, content_type)
            files = {
                'file': (os.path.basename(file_path), f, 'application/octet-stream')
            }
            
            # Prepare form data
            data = {
                'plugin_name': plugin_name,
                'plugin_params': json.dumps(plugin_params)
            }
            
            logger.info("Sending request...")
            start_time = time.time()
            
            try:
                response = requests.post(
                    url, 
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=30  # Add a timeout to prevent indefinite hanging
                )
                
                end_time = time.time()
                elapsed = end_time - start_time
                logger.info(f"Request completed in {elapsed:.2f} seconds")
                
                # Log response details
                logger.info(f"Response status code: {response.status_code}")
                
                if response.status_code == 200:
                    logger.info("File upload successful!")
                    logger.info(f"Response content: {response.text[:500]}...")
                    return True
                else:
                    logger.error(f"Upload failed with status code: {response.status_code}")
                    logger.error(f"Response content: {response.text}")
                    return False
                    
            except requests.exceptions.Timeout:
                logger.error(f"Request timed out after 30 seconds")
                return False
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request failed: {str(e)}")
                return False
    
    except Exception as e:
        logger.error(f"Error preparing file upload: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function."""
    # Create a small test file if it doesn't exist
    test_file = "test_upload.txt"
    if not os.path.exists(test_file):
        with open(test_file, "w") as f:
            f.write("This is a test file for uploading.\n" * 10)
    
    # Test file upload
    success = test_file_upload(test_file)
    
    if success:
        logger.info("Test completed successfully!")
    else:
        logger.error("Test failed!")
        
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
