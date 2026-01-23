#!/usr/bin/env python3
"""
Test script for the lamb-kb-server API.

This script tests the complete workflow:
1. Creating a collection with default embeddings
2. Creating test files with different content
3. Ingesting each file using different chunking strategies
4. Performing queries to test the system
"""

import os
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class LambKBClient:
    """Client for interacting with the lamb-kb-server API."""
    
    def __init__(self, base_url: str, api_key: str):
        """Initialize the client.
        
        Args:
            base_url: Base URL of the lamb-kb-server API
            api_key: API key for authentication
        """
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make a request to the API.
        
        Args:
            method: HTTP method (get, post, etc.)
            endpoint: API endpoint (without base URL)
            **kwargs: Additional arguments to pass to requests
            
        Returns:
            Response JSON
            
        Raises:
            Exception: If the request fails
        """
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.pop("headers", self.headers)
        timeout = kwargs.pop("timeout", 60)  # Default 60 second timeout
        
        # Log request details
        is_file_upload = 'files' in kwargs
        log_msg = f"Requesting {method.upper()} {url}"
        if is_file_upload:
            log_msg += f" (with file upload)"
        logger.info(log_msg)
        
        try:
            # For file uploads, we want to track progress
            if is_file_upload:
                logger.info(f"Starting file upload to {endpoint}")
            
            # Make the request with timeout
            response = requests.request(
                method, 
                url, 
                headers=headers, 
                timeout=timeout,
                **kwargs
            )
            
            # Log response
            logger.info(f"Received response: HTTP {response.status_code}")
            
            # Check status
            response.raise_for_status()
            
            # Return JSON if there's content
            if response.content:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON response: {response.text[:500]}")
                    raise Exception(f"Invalid JSON response from API")
            return {}
            
        except requests.exceptions.Timeout:
            logger.error(f"Request to {url} timed out after {timeout} seconds")
            raise Exception(f"API request timed out: {endpoint}")
            
        except requests.exceptions.ConnectionError:
            logger.error(f"Connection error while connecting to {url}")
            raise Exception(f"Connection error: {endpoint}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            if hasattr(e, "response") and e.response is not None:
                status = e.response.status_code
                logger.error(f"Response status: {status}")
                error_text = e.response.text[:500]  # Limit error text to 500 chars
                logger.error(f"Response content: {error_text}")
                
                # Special handling for common error codes
                if status == 404:
                    if "plugin not found" in error_text.lower():
                        logger.error("Plugin not found error - check that the plugin exists and is correctly registered")
                    elif "collection not found" in error_text.lower():
                        logger.error("Collection not found error - check the collection ID")
                
                if status == 413:
                    logger.error("File size may be too large for the server to handle")
                
            raise
    
    def create_collection(self, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new collection.
        
        Args:
            collection_data: Collection data
            
        Returns:
            Created collection data
        """
        return self._request("post", "/collections", json=collection_data)
        
    def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections.
        
        Returns:
            List of collections
        """
        response = self._request("get", "/collections")
        # The /collections endpoint returns a response with format: {"total": count, "items": [collections]}
        return response.get("items", [])
        
    def get_collection_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a collection by name.
        
        Args:
            name: Collection name
            
        Returns:
            Collection data or None if not found
        """
        collections = self.list_collections()
        for collection in collections:
            if collection.get("name") == name:
                return collection
        return None
    
    def create_test_file(self, content: str, file_path: str) -> None:
        """Create a test file with the given content.
        
        Args:
            content: File content
            file_path: Path to create the file at
        """
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            f.write(content)
        logger.info(f"Created test file: {file_path}")
    
    def upload_file(self, collection_id: int, file_path: str) -> Dict[str, Any]:
        """Upload a file to a collection.
        
        Args:
            collection_id: Collection ID
            file_path: Path to the file to upload
            
        Returns:
            Upload response data
        """
        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            return self._request(
                "post", 
                f"/collections/{collection_id}/upload",
                headers={"Authorization": f"Bearer {self.headers['Authorization'].split(' ')[1]}"},
                files=files
            )
    
    def ingest_file(self, collection_id: int, file_path: str, plugin_name: str, plugin_params: Dict[str, Any]) -> Dict[str, Any]:
        """Process a file with an ingestion plugin.
        
        Args:
            collection_id: Collection ID
            file_path: Path to the file to ingest
            plugin_name: Name of the ingestion plugin to use
            plugin_params: Parameters for the plugin
            
        Returns:
            Ingestion response data
        """
        data = {
            "file_path": file_path,
            "plugin_name": plugin_name,
            "plugin_params": json.dumps(plugin_params)
        }
        return self._request(
            "post", 
            f"/collections/{collection_id}/ingest",
            data=data,
            headers={"Authorization": f"Bearer {self.headers['Authorization'].split(' ')[1]}"}
        )
    
    def add_documents(self, collection_id: int, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Add documents to a collection.
        
        Args:
            collection_id: Collection ID
            documents: Documents to add
            
        Returns:
            Add documents response data
        """
        data = {"documents": documents}
        return self._request("post", f"/collections/{collection_id}/documents", json=data)
    
    def ingest_file_to_collection(self, collection_id: int, file_path: str, plugin_name: str, plugin_params: Dict[str, Any]) -> Dict[str, Any]:
        """Upload and ingest a file directly to a collection.
        
        Args:
            collection_id: Collection ID
            file_path: Path to the file to ingest
            plugin_name: Name of the ingestion plugin to use
            plugin_params: Parameters for the plugin
            
        Returns:
            Ingestion response data
        """
        # Log file info before sending
        file_size = os.path.getsize(file_path)
        logger.info(f"Preparing to upload file: {file_path} (size: {file_size} bytes)")
        logger.info(f"Plugin params: {json.dumps(plugin_params)}")
        
        try:
            with open(file_path, "rb") as f:
                # Create basic file object
                file_content = f.read()
                logger.info(f"File read into memory successfully: {len(file_content)} bytes")
                
                # Prepare multipart form data
                files = {"file": (os.path.basename(file_path), file_content)}
                data = {
                    "plugin_name": plugin_name,
                    "plugin_params": json.dumps(plugin_params)
                }
                
                logger.info(f"Sending request to: /collections/{collection_id}/ingest-file")
                response = self._request(
                    "post", 
                    f"/collections/{collection_id}/ingest-file",
                    headers={"Authorization": f"Bearer {self.headers['Authorization'].split(' ')[1]}"},
                    data=data,
                    files=files,
                    timeout=30  # Add timeout to prevent hanging indefinitely
                )
                logger.info("File upload and ingestion completed successfully")
                return response
        except Exception as e:
            logger.error(f"Error during file upload: {str(e)}")
            raise
    
    def query_collection(self, collection_id: int, query_text: str, plugin_name: str, plugin_params: Dict[str, Any]) -> Dict[str, Any]:
        """Query a collection.
        
        Args:
            collection_id: Collection ID
            query_text: Query text
            plugin_name: Name of the query plugin to use
            plugin_params: Parameters for the plugin
            
        Returns:
            Query response data
        """
        data = {
            "query_text": query_text,
            "plugin_params": plugin_params
        }
        return self._request(
            "post", 
            f"/collections/{collection_id}/query?plugin_name={plugin_name}",
            json=data
        )
        
    def list_files(self, collection_id: int, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List files in a collection.
        
        Args:
            collection_id: Collection ID
            status: Optional filter by status (completed, processing, failed, deleted)
            
        Returns:
            List of file registry entries
        """
        endpoint = f"/collections/{collection_id}/files"
        if status:
            endpoint += f"?status={status}"
        return self._request("get", endpoint)
        
    def update_file_status(self, file_id: int, status: str) -> Dict[str, Any]:
        """Update the status of a file in the registry.
        
        Args:
            file_id: File registry entry ID
            status: New status (completed, processing, failed, deleted)
            
        Returns:
            Updated file registry entry
        """
        return self._request("put", f"/files/{file_id}/status?status={status}")


def main():
    """Run the test script."""
    # Load params
    with open("params.json", "r") as f:
        params = json.load(f)
    
    # Create client
    client = LambKBClient(
        base_url=params["api"]["base_url"],
        api_key=params["api"]["api_key"]
    )
    
    collection_id = None
    success = True
    
    try:
        # Step 1: Get or create collection
        collection_name = params["collection"]["name"]
        logger.info(f"Looking for collection: {collection_name}")
        
        try:
            collection = client.get_collection_by_name(collection_name)
            
            if collection:
                logger.info(f"Using existing collection: {collection_name}")
                collection_id = collection["id"]
                logger.info(f"Collection details: {json.dumps(collection, indent=2)}")
            else:
                logger.info(f"Creating new collection: {collection_name}")
                collection = client.create_collection(params["collection"])
                collection_id = collection["id"]
                logger.info(f"Created collection with ID: {collection_id}")
        except Exception as e:
            logger.error(f"Error with collection: {str(e)}")
            # Try to create a collection with a unique name if there was an error
            unique_name = f"{collection_name}-{int(time.time())}"
            logger.info(f"Trying with unique collection name: {unique_name}")
            params["collection"]["name"] = unique_name
            collection = client.create_collection(params["collection"])
            collection_id = collection["id"]
            logger.info(f"Created collection with ID: {collection_id}")
        
        if not collection_id:
            logger.error("Failed to get or create a collection")
            return False
        
        # Verify the collection exists by checking a specific collection
        try:
            logger.info(f"Verifying collection with ID: {collection_id}")
            specific_collection = client._request("get", f"/collections/{collection_id}")
            logger.info(f"Verified collection exists with ID: {collection_id}")
        except Exception as e:
            logger.error(f"Error verifying collection: {str(e)}")
            logger.info("Listing all available collections:")
            try:
                all_collections = client._request("get", "/collections")
                logger.info(f"Available collections: {json.dumps(all_collections, indent=2)}")
                if all_collections.get("items") and len(all_collections.get("items")) > 0:
                    # Try to use the first available collection
                    collection = all_collections["items"][0]
                    collection_id = collection["id"]
                    logger.info(f"Using first available collection with ID: {collection_id}")
            except Exception as e2:
                logger.error(f"Error listing collections: {str(e2)}")
                return False
            
        # Step 2: Create and ingest test files
        for i, file_data in enumerate(params["test_files"], 1):
            file_path = file_data["path"]
            
            try:
                # Create test file
                logger.info(f"Creating test file {i}/{len(params['test_files'])}: {file_path}")
                client.create_test_file(file_data["content"], file_path)
                
                # Upload and ingest file
                logger.info(f"Ingesting file {i}/{len(params['test_files'])}: {file_path}")
                logger.info(f"Using chunking strategy: {file_data['params']['chunk_unit']} with size {file_data['params']['chunk_size']}")
                ingest_result = client.ingest_file_to_collection(
                    collection_id=collection_id,
                    file_path=file_path,
                    plugin_name=file_data["plugin"],
                    plugin_params=file_data["params"]
                )
                logger.info(f"Ingestion result: Added {ingest_result['documents_added']} documents")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
                success = False
                # Continue with next file
                continue
        
        # Step 3: Wait a moment for embeddings to be processed
        logger.info("Waiting for embeddings to be processed...")
        time.sleep(2)
        
        # List available plugins from the plugins directory
        try:
            logger.info("Checking available query plugins in the filesystem...")
            query_plugin_files = [f for f in os.listdir(os.path.join(os.path.dirname(__file__), 'plugins')) 
                              if f.endswith('.py') and f != '__init__.py']
            logger.info(f"Plugin files found: {query_plugin_files}")
            # Note: The API doesn't have an endpoint to list plugins, 
            # instead they're loaded dynamically from the plugins directory
        except Exception as e:
            logger.error(f"Error listing query plugins: {str(e)}")
            
        # Step 4: Query the collection
        logger.info("\n" + "="*80)
        logger.info("Running queries:")
        for i, query_data in enumerate(params["queries"], 1):
            try:
                logger.info("-"*80)
                logger.info(f"Query {i}/{len(params['queries'])}: '{query_data['query_text']}'")
                query_result = client.query_collection(
                    collection_id=collection_id,
                    query_text=query_data["query_text"],
                    plugin_name=query_data["plugin"],
                    plugin_params=query_data["params"]
                )
                
                logger.info(f"Found {len(query_result['results'])} results in {query_result['timing']['total_ms']:.2f}ms")
                
                # Show results
                for j, result in enumerate(query_result["results"], 1):
                    logger.info(f"  Result {j} (similarity: {result['similarity']:.4f}):")
                    text = result["data"]
                    # Truncate long text for display
                    if len(text) > 100:
                        text = text[:97] + "..."
                    logger.info(f"    {text}")
                    logger.info(f"    Metadata: {json.dumps(result['metadata'])}")
            except Exception as e:
                logger.error(f"Error running query '{query_data['query_text']}': {str(e)}")
                success = False
                # Continue with next query
                continue
        
        # Step 5: Test file registry functionality
        logger.info("\n" + "="*80)
        logger.info("Testing file registry functionality:")
        try:
            # List all files in the collection
            logger.info("Listing all files in the collection...")
            files = client.list_files(collection_id)
            logger.info(f"Found {len(files)} files in collection {collection_id}")
            
            # Verify that the number of files matches the number of test files ingested
            expected_file_count = len(params["test_files"])
            if len(files) == expected_file_count:
                logger.info(f"✅ Verification passed: Found expected number of files ({expected_file_count})")
            else:
                logger.warning(f"❌ Verification failed: Expected {expected_file_count} files, but found {len(files)}")
                success = False
            
            # Create a dictionary of expected filenames from the test files
            expected_files = {os.path.basename(file_data["path"]): file_data for file_data in params["test_files"]}
            found_files = set()
            
            # Display file details and verify each file
            for i, file in enumerate(files, 1):
                logger.info(f"File {i}: ID={file['id']}, Filename={file['original_filename']}, Status={file['status']}")
                logger.info(f"  Plugin: {file['plugin_name']}, Chunks: {file['document_count']}")
                
                # Track which expected files were found
                found_files.add(file['original_filename'])
                
                # Verify file status is 'completed'
                if file['status'] == 'completed':
                    logger.info(f"✅ Verification passed: File {file['original_filename']} has 'completed' status")
                else:
                    logger.warning(f"❌ Verification failed: File {file['original_filename']} has '{file['status']}' status instead of 'completed'")
                    success = False
                
                # Verify document count is greater than 0
                if file['document_count'] > 0:
                    logger.info(f"✅ Verification passed: File {file['original_filename']} has {file['document_count']} documents")
                else:
                    logger.warning(f"❌ Verification failed: File {file['original_filename']} has 0 documents")
                    success = False
            
            # Verify all expected files were found
            missing_files = set(expected_files.keys()) - found_files
            if not missing_files:
                logger.info("✅ Verification passed: All expected files were found in the registry")
            else:
                logger.warning(f"❌ Verification failed: The following files were not found in the registry: {missing_files}")
                success = False
            
            # Test file status updates if files exist
            if files:
                test_file = files[0]
                file_id = test_file['id']
                original_status = test_file['status']
                new_status = "deleted" if original_status != "deleted" else "completed"
                
                logger.info(f"Updating file {file_id} status from '{original_status}' to '{new_status}'...")
                updated_file = client.update_file_status(file_id, new_status)
                logger.info(f"Updated file status: {updated_file['status']}")
                
                # Verify the status was updated correctly
                if updated_file['status'] == new_status:
                    logger.info(f"✅ Verification passed: File status was updated to '{new_status}'")
                else:
                    logger.warning(f"❌ Verification failed: File status update failed, got '{updated_file['status']}' instead of '{new_status}'")
                    success = False
                
                # Verify the change by listing files with the new status
                logger.info(f"Listing files with status '{new_status}'...")
                filtered_files = client.list_files(collection_id, status=new_status)
                logger.info(f"Found {len(filtered_files)} files with status '{new_status}'")
                
                # Verify that filtering by status works
                if len(filtered_files) > 0:
                    logger.info(f"✅ Verification passed: Successfully filtered files by status '{new_status}'")
                else:
                    logger.warning(f"❌ Verification failed: No files found when filtering by status '{new_status}'")
                    success = False
                
                # Restore original status
                logger.info(f"Restoring file {file_id} to original status '{original_status}'...")
                restored_file = client.update_file_status(file_id, original_status)
                logger.info(f"Restored file status: {restored_file['status']}")
            else:
                logger.info("No files found in collection to test status updates")
        except Exception as e:
            logger.error(f"Error testing file registry: {str(e)}")
            success = False
            
        logger.info("\n" + "="*80)
        if success:
            logger.info("Test completed successfully!")
        else:
            logger.info("Test completed with some errors. Check the log for details.")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")
        success = False
        
    # Clean up test files
    try:
        for file_data in params["test_files"]:
            file_path = file_data["path"]
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed test file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up test files: {str(e)}")
        
    return success


if __name__ == "__main__":
    # Exit with appropriate exit code
    success = main()
    if not success:
        # Exit with error code if tests failed
        import sys
        sys.exit(1)
