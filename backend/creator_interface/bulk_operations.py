"""
Bulk Operations Module for Organization Admins

This module handles bulk user creation, validation, and management operations
for organization administrators.

Author: LAMB Development Team
Date: November 2025
"""

import re
import json
import secrets
from typing import Dict, List, Any, Optional, Tuple
from fastapi import UploadFile

from backend.lamb.database_manager import LambDatabaseManager
from backend.utils.pipelines.user_creator_manager import UserCreatorManager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")


class BulkImportValidator:
    """Validates bulk user import data"""
    
    EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    MAX_USERS = 500
    MIN_USERS = 1
    VALID_USER_TYPES = ['creator', 'end_user']
    SUPPORTED_VERSION = '1.0'
    
    def __init__(self, organization_id: int):
        """
        Initialize validator for specific organization
        
        Args:
            organization_id: ID of the organization to validate against
        """
        self.organization_id = organization_id
        self.db_manager = LambDatabaseManager()
    
    def validate_import_data(self, data: Dict) -> Dict:
        """
        Validate entire import data structure
        
        Args:
            data: Parsed JSON data from import file
        
        Returns:
            {
                "valid": bool,
                "summary": {"total": int, "valid": int, "invalid": int},
                "users": [validated user objects],
                "error": str (if schema invalid)
            }
        """
        # 1. Validate top-level structure
        if not isinstance(data, dict):
            return self._error_response("Data must be a JSON object")
        
        if 'version' not in data:
            return self._error_response("Missing 'version' field")
        
        if data['version'] != self.SUPPORTED_VERSION:
            return self._error_response(
                f"Unsupported version: {data['version']}. Expected: {self.SUPPORTED_VERSION}"
            )
        
        if 'users' not in data:
            return self._error_response("Missing 'users' array")
        
        if not isinstance(data['users'], list):
            return self._error_response("'users' must be an array")
        
        if len(data['users']) < self.MIN_USERS:
            return self._error_response("'users' array cannot be empty")
        
        if len(data['users']) > self.MAX_USERS:
            return self._error_response(
                f"Too many users (max {self.MAX_USERS}, got {len(data['users'])})"
            )
        
        # 2. Validate each user
        validated_users = []
        emails_in_file = set()
        
        for idx, user in enumerate(data['users']):
            validated_user = self._validate_user(user, idx, emails_in_file)
            validated_users.append(validated_user)
            
            if validated_user['valid']:
                emails_in_file.add(validated_user['email'].lower())
        
        # 3. Generate summary
        valid_count = sum(1 for u in validated_users if u['valid'])
        invalid_count = len(validated_users) - valid_count
        
        return {
            "valid": invalid_count == 0,
            "summary": {
                "total": len(validated_users),
                "valid": valid_count,
                "invalid": invalid_count
            },
            "users": validated_users,
            "error": None
        }
    
    def _validate_user(
        self, 
        user: Dict, 
        index: int, 
        emails_in_file: set
    ) -> Dict:
        """
        Validate individual user
        
        Args:
            user: User data dict
            index: Position in file (for error reporting)
            emails_in_file: Set of emails already seen in file
        
        Returns:
            {
                "email": str,
                "name": str,
                "user_type": str,
                "enabled": bool,
                "valid": bool,
                "errors": [str],
                "line": int
            }
        """
        errors = []
        
        # Validate user is a dict
        if not isinstance(user, dict):
            return {
                "email": "",
                "name": "",
                "user_type": "creator",
                "enabled": False,
                "valid": False,
                "errors": [f"User at index {index} is not a valid object"],
                "line": index + 1
            }
        
        # Extract fields with defaults
        email = user.get('email', '').strip()
        name = user.get('name', '').strip()
        user_type = user.get('user_type', 'creator')
        enabled = user.get('enabled', False)
        
        # Validate email
        if not email:
            errors.append("Email is required")
        elif not self.EMAIL_REGEX.match(email):
            errors.append("Invalid email format")
        elif email.lower() in emails_in_file:
            errors.append("Duplicate email in file")
        else:
            # Check if email exists in organization
            existing_user = self.db_manager.get_creator_user_by_email(email)
            if existing_user:
                if existing_user['organization_id'] == self.organization_id:
                    errors.append("Email already exists in your organization")
                else:
                    errors.append("Email exists in another organization")
        
        # Validate name
        if not name:
            errors.append("Name is required")
        elif len(name) > 100:
            errors.append("Name too long (max 100 characters)")
        elif len(name) < 1:
            errors.append("Name cannot be empty")
        
        # Validate user_type
        if not isinstance(user_type, str):
            errors.append("user_type must be a string")
        elif user_type not in self.VALID_USER_TYPES:
            errors.append(
                f"Invalid user_type '{user_type}' "
                f"(must be one of: {', '.join(self.VALID_USER_TYPES)})"
            )
        
        # Validate enabled
        if not isinstance(enabled, bool):
            errors.append("enabled must be boolean (true/false)")
        
        return {
            "email": email,
            "name": name,
            "user_type": user_type,
            "enabled": enabled,
            "valid": len(errors) == 0,
            "errors": errors,
            "line": index + 1
        }
    
    def _error_response(self, error: str) -> Dict:
        """Return error response for schema-level failures"""
        return {
            "valid": False,
            "summary": None,
            "users": [],
            "error": error
        }


class BulkUserCreator:
    """Handles bulk user creation with detailed result tracking"""
    
    def __init__(
        self,
        organization_id: int,
        admin_user_id: int,
        admin_email: str
    ):
        """
        Initialize bulk user creator
        
        Args:
            organization_id: Organization to create users in
            admin_user_id: ID of admin performing the operation
            admin_email: Email of admin (for logging)
        """
        self.organization_id = organization_id
        self.admin_user_id = admin_user_id
        self.admin_email = admin_email
        self.user_creator = UserCreatorManager()
        self.db_manager = LambDatabaseManager()
    
    async def create_users(self, users: List[Dict]) -> Dict:
        """
        Create multiple users with result tracking
        
        Args:
            users: List of user dicts with email, name, user_type, enabled
        
        Returns:
            {
                "success": bool,
                "summary": {
                    "total": int,
                    "created": int,
                    "failed": int,
                    "skipped": int
                },
                "results": [
                    {
                        "email": str,
                        "name": str,
                        "status": "success" | "failed" | "skipped",
                        "user_id": int | None,
                        "message": str
                    }
                ]
            }
        """
        results = []
        created_count = 0
        failed_count = 0
        skipped_count = 0
        
        logger.info(
            f"Bulk user creation started by {self.admin_email} "
            f"for organization {self.organization_id}: {len(users)} users"
        )
        
        for user in users:
            result = await self._create_single_user(user)
            results.append(result)
            
            if result['status'] == 'success':
                created_count += 1
            elif result['status'] == 'failed':
                failed_count += 1
            elif result['status'] == 'skipped':
                skipped_count += 1
        
        logger.info(
            f"Bulk user creation completed: "
            f"{created_count} created, {failed_count} failed, {skipped_count} skipped"
        )
        
        return {
            "success": True,
            "summary": {
                "total": len(users),
                "created": created_count,
                "failed": failed_count,
                "skipped": skipped_count
            },
            "results": results
        }
    
    async def _create_single_user(self, user: Dict) -> Dict:
        """
        Create a single user with error handling
        
        Args:
            user: User data dict
        
        Returns:
            {
                "email": str,
                "name": str,
                "status": str,
                "user_id": int | None,
                "message": str
            }
        """
        email = user['email']
        name = user['name']
        user_type = user.get('user_type', 'creator')
        enabled = user.get('enabled', False)
        
        try:
            # Check if user already exists (shouldn't happen if validation worked)
            existing_user = self.db_manager.get_creator_user_by_email(email)
            if existing_user:
                logger.warning(f"User {email} already exists, skipping")
                return {
                    "email": email,
                    "name": name,
                    "status": "skipped",
                    "user_id": existing_user['id'],
                    "message": "User already exists"
                }
            
            # Generate random secure password
            password = secrets.token_urlsafe(32)
            
            # Create user via UserCreatorManager
            result = await self.user_creator.create_user(
                email=email,
                name=name,
                password=password,
                role='user',  # Default role
                organization_id=self.organization_id,
                user_type=user_type
            )
            
            if not result.get('success'):
                logger.error(f"Failed to create user {email}: {result.get('message')}")
                return {
                    "email": email,
                    "name": name,
                    "status": "failed",
                    "user_id": None,
                    "message": result.get('message', 'Unknown error')
                }
            
            user_id = result['user_id']
            
            # Set enabled status if different from default (default is enabled=1)
            if not enabled:
                self.db_manager.disable_user(user_id)
                logger.info(f"User {email} created in disabled state")
            
            logger.info(f"Created user {email} (ID: {user_id})")
            
            return {
                "email": email,
                "name": name,
                "status": "success",
                "user_id": user_id,
                "message": "User created successfully" + (" (disabled)" if not enabled else "")
            }
        
        except Exception as e:
            logger.error(f"Exception creating user {email}: {str(e)}", exc_info=True)
            return {
                "email": email,
                "name": name,
                "status": "failed",
                "user_id": None,
                "message": f"Error: {str(e)}"
            }


# Utility Functions

async def validate_bulk_import_file(
    file: UploadFile,
    organization_id: int,
    max_file_size_mb: int = 5
) -> Dict:
    """
    Validate uploaded JSON file for bulk import
    
    Args:
        file: Uploaded file
        organization_id: Organization ID for validation context
        max_file_size_mb: Maximum file size in MB
    
    Returns:
        Validation result dict
    """
    # Check file size
    max_size_bytes = max_file_size_mb * 1024 * 1024
    
    # Read file content
    content = await file.read()
    
    if len(content) > max_size_bytes:
        return {
            "valid": False,
            "summary": None,
            "users": [],
            "error": f"File too large (max {max_file_size_mb}MB)"
        }
    
    # Parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        return {
            "valid": False,
            "summary": None,
            "users": [],
            "error": f"Invalid JSON syntax: {str(e)}"
        }
    
    # Validate data
    validator = BulkImportValidator(organization_id)
    return validator.validate_import_data(data)


def generate_import_template() -> Dict:
    """
    Generate bulk user import template with examples and documentation
    
    Returns:
        Template dict ready for JSON serialization
    """
    return {
        "_comment": "LAMB Bulk User Import Template v1.0",
        "_instructions": [
            "Fill in the users array with your user data",
            "Required fields: email, name",
            "Optional fields: user_type (default: creator), enabled (default: false)",
            "Valid user_types: creator, end_user",
            "Maximum 500 users per import",
            "Users will be created with random secure passwords",
            "Administrators should provide passwords to users separately"
        ],
        "_field_descriptions": {
            "email": "User's email address (must be unique)",
            "name": "User's full name",
            "user_type": "Type of account - 'creator' for full access, 'end_user' for chat-only",
            "enabled": "Whether account is active - false to create in disabled state"
        },
        "version": "1.0",
        "users": [
            {
                "email": "john.doe@example.com",
                "name": "John Doe",
                "user_type": "creator",
                "enabled": False
            },
            {
                "email": "jane.smith@example.com",
                "name": "Jane Smith",
                "user_type": "end_user",
                "enabled": False
            },
            {
                "email": "instructor@example.com",
                "name": "Course Instructor",
                "user_type": "creator",
                "enabled": True
            }
        ]
    }


def log_bulk_operation(
    db_manager: LambDatabaseManager,
    organization_id: int,
    admin_user_id: int,
    admin_email: str,
    operation_type: str,
    total_count: int,
    success_count: int,
    failure_count: int,
    details: Dict
) -> Optional[int]:
    """
    Log bulk operation to database
    
    Args:
        db_manager: Database manager instance
        organization_id: Organization ID
        admin_user_id: Admin user ID
        admin_email: Admin email
        operation_type: Type of operation (user_creation, user_activation, etc.)
        total_count: Total items processed
        success_count: Successful operations
        failure_count: Failed operations
        details: Additional details dict
    
    Returns:
        Log ID if successful, None if failed
    """
    try:
        log_id = db_manager.log_bulk_import(
            organization_id=organization_id,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
            operation_type=operation_type,
            total_count=total_count,
            success_count=success_count,
            failure_count=failure_count,
            details=details
        )
        logger.info(f"Logged bulk operation {operation_type} with ID {log_id}")
        return log_id
    except Exception as e:
        logger.error(f"Failed to log bulk operation: {str(e)}", exc_info=True)
        return None

