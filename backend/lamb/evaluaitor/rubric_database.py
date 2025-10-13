"""
Rubric Database Manager for LAMB Evaluaitor feature
Handles all database operations for rubrics including CRUD, visibility, and showcase management.
"""

import sqlite3
import json
import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..database_manager import LambDatabaseManager


class RubricDatabaseManager:
    """Database manager for rubric operations"""

    def __init__(self):
        """Initialize with reference to main database manager"""
        self.db_manager = LambDatabaseManager()

    def create_rubric(self, rubric_data: dict, owner_email: str, organization_id: int, is_public: bool = False) -> dict:
        """
        Create a new rubric

        Args:
            rubric_data: Complete rubric JSON structure
            owner_email: Owner's email address
            organization_id: Organization ID
            is_public: Whether rubric should be public (default False)

        Returns:
            Created rubric record as dict
        """
        connection = self.db_manager.get_connection()
        if not connection:
            raise Exception("Database connection failed")

        try:
            with connection:
                cursor = connection.cursor()

                # Generate unique rubric_id
                rubric_id = str(uuid.uuid4())

                # Prepare data
                title = rubric_data.get('title', 'Untitled Rubric')
                description = rubric_data.get('description', '')
                rubric_data_json = json.dumps(rubric_data)
                created_at = int(datetime.now().timestamp())
                updated_at = created_at

                # Insert rubric
                cursor.execute(f"""
                    INSERT INTO {self.db_manager.table_prefix}rubrics (
                        rubric_id, organization_id, owner_email, title, description,
                        rubric_data, is_public, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rubric_id, organization_id, owner_email, title, description,
                    rubric_data_json, is_public, created_at, updated_at
                ))

                rubric_record = {
                    'id': cursor.lastrowid,
                    'rubric_id': rubric_id,
                    'organization_id': organization_id,
                    'owner_email': owner_email,
                    'title': title,
                    'description': description,
                    'rubric_data': rubric_data,
                    'is_public': is_public,
                    'is_showcase': False,
                    'parent_rubric_id': None,
                    'created_at': created_at,
                    'updated_at': updated_at
                }

                return rubric_record

        except sqlite3.Error as e:
            logging.error(f"Error creating rubric: {e}")
            raise Exception(f"Failed to create rubric: {e}")
        finally:
            if connection:
                connection.close()

    def get_rubric_by_id(self, rubric_id: str, requesting_user_email: str) -> Optional[dict]:
        """
        Get a rubric by ID with access control

        Args:
            rubric_id: Rubric unique identifier
            requesting_user_email: Email of user making the request

        Returns:
            Rubric record or None if not found or not accessible
        """
        connection = self.db_manager.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()

                # Get rubric with ownership check
                cursor.execute(f"""
                    SELECT r.*, o.slug as organization_slug
                    FROM {self.db_manager.table_prefix}rubrics r
                    JOIN {self.db_manager.table_prefix}organizations o ON r.organization_id = o.id
                    WHERE r.rubric_id = ?
                """, (rubric_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                # Convert row to dict
                columns = [desc[0] for desc in cursor.description]
                rubric_dict = dict(zip(columns, row))

                # Access control: user can access if they own it or it's public in their organization
                if rubric_dict['owner_email'] == requesting_user_email:
                    # User owns this rubric
                    pass
                elif rubric_dict['is_public']:
                    # Check if user is in the same organization
                    user_org = self.db_manager.get_user_organization_by_email(requesting_user_email)
                    if user_org and user_org['id'] == rubric_dict['organization_id']:
                        # User is in same organization and rubric is public
                        pass
                    else:
                        return None
                else:
                    # Not accessible
                    return None

                # Parse JSON data
                rubric_dict['rubric_data'] = json.loads(rubric_dict['rubric_data'])

                return rubric_dict

        except sqlite3.Error as e:
            logging.error(f"Error getting rubric {rubric_id}: {e}")
            return None
        finally:
            if connection:
                connection.close()

    def get_rubrics_by_owner(self, owner_email: str, limit: int = 10, offset: int = 0, filters: dict = None) -> list[dict]:
        """
        Get rubrics owned by a specific user

        Args:
            owner_email: Owner's email
            limit: Maximum number of results
            offset: Pagination offset
            filters: Optional filters (subject, grade_level, etc.)

        Returns:
            List of rubric records
        """
        if filters is None:
            filters = {}

        connection = self.db_manager.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                # Build query with filters
                where_conditions = ["r.owner_email = ?"]
                params = [owner_email]

                if filters.get('subject'):
                    where_conditions.append("JSON_EXTRACT(r.rubric_data, '$.metadata.subject') LIKE ?")
                    params.append(f"%{filters['subject']}%")

                if filters.get('grade_level'):
                    where_conditions.append("JSON_EXTRACT(r.rubric_data, '$.metadata.gradeLevel') LIKE ?")
                    params.append(f"%{filters['grade_level']}%")

                if filters.get('is_public') is not None:
                    where_conditions.append("r.is_public = ?")
                    params.append(filters['is_public'])

                where_clause = " AND ".join(where_conditions)

                query = f"""
                    SELECT r.*, o.slug as organization_slug
                    FROM {self.db_manager.table_prefix}rubrics r
                    JOIN {self.db_manager.table_prefix}organizations o ON r.organization_id = o.id
                    WHERE {where_clause}
                    ORDER BY r.updated_at DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])

                cursor.execute(query, params)

                rubrics = []
                for row in cursor.fetchall():
                    columns = [desc[0] for desc in cursor.description]
                    rubric_dict = dict(zip(columns, row))
                    rubric_dict['rubric_data'] = json.loads(rubric_dict['rubric_data'])
                    rubrics.append(rubric_dict)

                return rubrics

        except sqlite3.Error as e:
            logging.error(f"Error getting rubrics for {owner_email}: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def get_public_rubrics(self, organization_id: int, limit: int = 10, offset: int = 0, filters: dict = None) -> list[dict]:
        """
        Get public rubrics in an organization

        Args:
            organization_id: Organization ID
            limit: Maximum number of results
            offset: Pagination offset
            filters: Optional filters

        Returns:
            List of public rubric records
        """
        if filters is None:
            filters = {}

        connection = self.db_manager.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                # Build query
                where_conditions = ["r.organization_id = ?", "r.is_public = 1"]
                params = [organization_id]

                if filters.get('subject'):
                    where_conditions.append("JSON_EXTRACT(r.rubric_data, '$.metadata.subject') LIKE ?")
                    params.append(f"%{filters['subject']}%")

                if filters.get('grade_level'):
                    where_conditions.append("JSON_EXTRACT(r.rubric_data, '$.metadata.gradeLevel') LIKE ?")
                    params.append(f"%{filters['grade_level']}%")

                where_clause = " AND ".join(where_conditions)

                query = f"""
                    SELECT r.*, o.slug as organization_slug
                    FROM {self.db_manager.table_prefix}rubrics r
                    JOIN {self.db_manager.table_prefix}organizations o ON r.organization_id = o.id
                    WHERE {where_clause}
                    ORDER BY r.is_showcase DESC, r.updated_at DESC
                    LIMIT ? OFFSET ?
                """
                params.extend([limit, offset])

                cursor.execute(query, params)

                rubrics = []
                for row in cursor.fetchall():
                    columns = [desc[0] for desc in cursor.description]
                    rubric_dict = dict(zip(columns, row))
                    rubric_dict['rubric_data'] = json.loads(rubric_dict['rubric_data'])
                    rubrics.append(rubric_dict)

                return rubrics

        except sqlite3.Error as e:
            logging.error(f"Error getting public rubrics for org {organization_id}: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def get_showcase_rubrics(self, organization_id: int) -> list[dict]:
        """
        Get showcase rubrics for an organization

        Args:
            organization_id: Organization ID

        Returns:
            List of showcase rubric records
        """
        connection = self.db_manager.get_connection()
        if not connection:
            return []

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    SELECT r.*, o.slug as organization_slug
                    FROM {self.db_manager.table_prefix}rubrics r
                    JOIN {self.db_manager.table_prefix}organizations o ON r.organization_id = o.id
                    WHERE r.organization_id = ? AND r.is_showcase = 1
                    ORDER BY r.updated_at DESC
                """, (organization_id,))

                rubrics = []
                for row in cursor.fetchall():
                    columns = [desc[0] for desc in cursor.description]
                    rubric_dict = dict(zip(columns, row))
                    rubric_dict['rubric_data'] = json.loads(rubric_dict['rubric_data'])
                    rubrics.append(rubric_dict)

                return rubrics

        except sqlite3.Error as e:
            logging.error(f"Error getting showcase rubrics for org {organization_id}: {e}")
            return []
        finally:
            if connection:
                connection.close()

    def update_rubric(self, rubric_id: str, rubric_data: dict, owner_email: str) -> dict:
        """
        Update an existing rubric

        Args:
            rubric_id: Rubric unique identifier
            rubric_data: Updated rubric JSON structure
            owner_email: Owner's email (for verification)

        Returns:
            Updated rubric record
        """
        connection = self.db_manager.get_connection()
        if not connection:
            raise Exception("Database connection failed")

        try:
            with connection:
                cursor = connection.cursor()

                # Verify ownership
                cursor.execute(f"""
                    SELECT id FROM {self.db_manager.table_prefix}rubrics
                    WHERE rubric_id = ? AND owner_email = ?
                """, (rubric_id, owner_email))

                if not cursor.fetchone():
                    raise Exception("Rubric not found or access denied")

                # Update rubric
                title = rubric_data.get('title', 'Untitled Rubric')
                description = rubric_data.get('description', '')
                rubric_data_json = json.dumps(rubric_data)
                updated_at = int(datetime.now().timestamp())

                cursor.execute(f"""
                    UPDATE {self.db_manager.table_prefix}rubrics
                    SET title = ?, description = ?, rubric_data = ?, updated_at = ?
                    WHERE rubric_id = ? AND owner_email = ?
                """, (title, description, rubric_data_json, updated_at, rubric_id, owner_email))

                if cursor.rowcount == 0:
                    raise Exception("Rubric update failed")

                # Get updated record
                updated_rubric = self.get_rubric_by_id(rubric_id, owner_email)
                if not updated_rubric:
                    raise Exception("Failed to retrieve updated rubric")

                return updated_rubric

        except sqlite3.Error as e:
            logging.error(f"Error updating rubric {rubric_id}: {e}")
            raise Exception(f"Failed to update rubric: {e}")
        finally:
            if connection:
                connection.close()

    def toggle_rubric_visibility(self, rubric_id: str, is_public: bool, owner_email: str) -> bool:
        """
        Toggle rubric visibility (public/private)

        Args:
            rubric_id: Rubric unique identifier
            is_public: New visibility state
            owner_email: Owner's email (for verification)

        Returns:
            Success status
        """
        connection = self.db_manager.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                updated_at = int(datetime.now().timestamp())

                cursor.execute(f"""
                    UPDATE {self.db_manager.table_prefix}rubrics
                    SET is_public = ?, updated_at = ?
                    WHERE rubric_id = ? AND owner_email = ?
                """, (is_public, updated_at, rubric_id, owner_email))

                # If making private, also remove showcase status
                if not is_public:
                    cursor.execute(f"""
                        UPDATE {self.db_manager.table_prefix}rubrics
                        SET is_showcase = 0
                        WHERE rubric_id = ? AND owner_email = ?
                    """, (rubric_id, owner_email))

                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logging.error(f"Error toggling visibility for rubric {rubric_id}: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def set_showcase_status(self, rubric_id: str, is_showcase: bool, admin_email: str) -> bool:
        """
        Set showcase status (admin only)

        Args:
            rubric_id: Rubric unique identifier
            is_showcase: New showcase state
            admin_email: Admin email (for verification)

        Returns:
            Success status
        """
        connection = self.db_manager.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                # Verify admin status (simplified - should check proper admin role)
                # For now, just check if user exists in system org with admin role
                system_org = self.db_manager.get_organization_by_slug("lamb")
                if not system_org:
                    return False

                admin_check = self.db_manager.get_user_organization_role(system_org['id'], admin_email)
                if admin_check != 'admin':
                    return False

                updated_at = int(datetime.now().timestamp())

                cursor.execute(f"""
                    UPDATE {self.db_manager.table_prefix}rubrics
                    SET is_showcase = ?, updated_at = ?
                    WHERE rubric_id = ?
                """, (is_showcase, updated_at, rubric_id))

                # If setting as showcase, also make public
                if is_showcase:
                    cursor.execute(f"""
                        UPDATE {self.db_manager.table_prefix}rubrics
                        SET is_public = 1
                        WHERE rubric_id = ?
                    """, (rubric_id,))

                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logging.error(f"Error setting showcase status for rubric {rubric_id}: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def delete_rubric(self, rubric_id: str, owner_email: str) -> bool:
        """
        Delete a rubric

        Args:
            rubric_id: Rubric unique identifier
            owner_email: Owner's email (for verification)

        Returns:
            Success status
        """
        connection = self.db_manager.get_connection()
        if not connection:
            return False

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    DELETE FROM {self.db_manager.table_prefix}rubrics
                    WHERE rubric_id = ? AND owner_email = ?
                """, (rubric_id, owner_email))

                return cursor.rowcount > 0

        except sqlite3.Error as e:
            logging.error(f"Error deleting rubric {rubric_id}: {e}")
            return False
        finally:
            if connection:
                connection.close()

    def count_rubrics(self, owner_email: str, filters: dict = None) -> int:
        """
        Count rubrics for a user with optional filters

        Args:
            owner_email: Owner's email
            filters: Optional filters

        Returns:
            Count of rubrics
        """
        if filters is None:
            filters = {}

        connection = self.db_manager.get_connection()
        if not connection:
            return 0

        try:
            with connection:
                cursor = connection.cursor()

                # Build query with filters
                where_conditions = ["owner_email = ?"]
                params = [owner_email]

                if filters.get('subject'):
                    where_conditions.append("JSON_EXTRACT(rubric_data, '$.metadata.subject') LIKE ?")
                    params.append(f"%{filters['subject']}%")

                if filters.get('grade_level'):
                    where_conditions.append("JSON_EXTRACT(rubric_data, '$.metadata.gradeLevel') LIKE ?")
                    params.append(f"%{filters['grade_level']}%")

                if filters.get('is_public') is not None:
                    where_conditions.append("is_public = ?")
                    params.append(filters['is_public'])

                where_clause = " AND ".join(where_conditions)

                cursor.execute(f"""
                    SELECT COUNT(*) FROM {self.db_manager.table_prefix}rubrics
                    WHERE {where_clause}
                """, params)

                return cursor.fetchone()[0]

        except sqlite3.Error as e:
            logging.error(f"Error counting rubrics for {owner_email}: {e}")
            return 0
        finally:
            if connection:
                connection.close()

    def duplicate_rubric(self, rubric_id: str, new_owner_email: str) -> dict:
        """
        Duplicate a rubric as a template

        Args:
            rubric_id: Source rubric ID
            new_owner_email: New owner's email

        Returns:
            New rubric record
        """
        # Get source rubric (without ownership check for templates)
        source_rubric = self._get_rubric_by_id_unchecked(rubric_id)
        if not source_rubric:
            raise Exception("Source rubric not found")

        # Get new owner's organization
        new_owner_org = self.db_manager.get_user_organization_by_email(new_owner_email)
        if not new_owner_org:
            raise Exception("New owner not found in any organization")

        # Create duplicate
        new_rubric_data = json.loads(source_rubric['rubric_data'])
        new_rubric_data['title'] = f"{new_rubric_data['title']} (Copy)"
        new_rubric_data['rubricId'] = str(uuid.uuid4())  # Generate new ID

        return self.create_rubric(
            rubric_data=new_rubric_data,
            owner_email=new_owner_email,
            organization_id=new_owner_org['id'],
            is_public=False
        )

    def _get_rubric_by_id_unchecked(self, rubric_id: str) -> Optional[dict]:
        """
        Get rubric without access control (internal use only)

        Args:
            rubric_id: Rubric unique identifier

        Returns:
            Rubric record or None
        """
        connection = self.db_manager.get_connection()
        if not connection:
            return None

        try:
            with connection:
                cursor = connection.cursor()

                cursor.execute(f"""
                    SELECT r.*, o.slug as organization_slug
                    FROM {self.db_manager.table_prefix}rubrics r
                    JOIN {self.db_manager.table_prefix}organizations o ON r.organization_id = o.id
                    WHERE r.rubric_id = ?
                """, (rubric_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                columns = [desc[0] for desc in cursor.description]
                rubric_dict = dict(zip(columns, row))
                rubric_dict['rubric_data'] = json.loads(rubric_dict['rubric_data'])

                return rubric_dict

        except sqlite3.Error as e:
            logging.error(f"Error getting rubric {rubric_id}: {e}")
            return None
        finally:
            if connection:
                connection.close()
