from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import logging
import requests
import os

class OWIModel:
    def __init__(self, db_connection):
        self.db = db_connection


    def create_model_api(self, 
                        token: str,
                        model_id: str, 
                        name: str, 
                        group_id: str,
                        created_at: int,
                        owned_by: str = "lamb_v4",
                        description: Optional[str] = None, 
                        suggestion_prompts: Optional[List[str]] = None, 
                        capabilities: Optional[Dict] = None, 
                        params: Optional[Dict] = None,
                        ) -> Optional[Dict]:
        """
        Creates a new model via the OWI API
        
        Args:
            model_id: Unique identifier for the model
            name: Name of the model
            group_id: Group ID for access control
            created_at: Timestamp of creation
            owned_by: Owner of the model
            description: Model description
            suggestion_prompts: List of suggestion prompts
            capabilities: Model capabilities
            params: Additional parameters
            
        Returns:
            Optional[Dict]: The created model data or None if failed
        """
        
        OWI_BASE_URL = os.getenv('OWI_BASE_URL')

        # Prepare model data
        model_data = {
            "id": "lamb_assistant." + model_id,
            "name": name,
            "meta": {
                "profile_image_url": "/static/favicon.png",
                "description": description or "assistant created with lamb",
                "suggestion_prompts": suggestion_prompts,
                "tags": [],
                "capabilities": capabilities or {
                    "vision": True,
                    "citations": True
                }
            },
            "params": params or {},
            "object": "model",
            "created": created_at,
            "owned_by": owned_by,
            "access_control": {
                "read": {
                    "group_ids": [group_id],
                    "user_ids": []
                },
                "write": {
                    "group_ids": [group_id],
                    "user_ids": []
                }
            }
        }
        
        logging.info(f"Creating model with data: {model_data}")
        
        try:
            # Print equivalent curl command for debugging
            curl_command = f"""curl -X POST "{OWI_BASE_URL}/api/v1/models/create" \\
                -H "Accept: application/json" \\
                -H "Content-Type: application/json" \\
                -H "Authorization: Bearer {token}" \\
                -d '{json.dumps(model_data, indent=2)}'"""
            #logging.info(f"Equivalent curl command:\n{curl_command}")
            response = requests.post(
                f"{OWI_BASE_URL}/api/v1/models/create",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                json=model_data
            )
            
            #logging.info(f"API Response Status: {response.status_code}")
            #logging.info(f"API Response Headers: {dict(response.headers)}")
            
            if not response.ok:
                error_data = response.json()
                logging.info(f"Equivalent curl command:\n{curl_command}")
                logging.error(f"API Error Response: {error_data}")
                return None
            
            result = response.json()
            #logging.info(f"API Success Response: {result}")
            return result
            
        except Exception as e:
            logging.error(f"Error creating model via API: {str(e)}")
            return None

    def create_model(
        self,
        model_id: str,
        user_id: str,
        name: str,
        base_model_id: Optional[str] = None,
        meta: Optional[Dict] = None,
        params: Optional[Dict] = None,
        access_control: Optional[Dict] = None
    ) -> bool:
        """
        Create a new model with specified permissions
        """
        current_time = int(datetime.now().timestamp())
        
        # Default values
        meta = meta or {
            "profile_image_url": "/static/favicon.png",
            "description": "",
            "capabilities": {"vision": False, "citations": True},
            "suggestion_prompts": None,
            "tags": []
        }
        
        params = params or {}
        
        # Default access control structure
        access_control = access_control or {
            "read": {"group_ids": [], "user_ids": []},
            "write": {"group_ids": [], "user_ids": []}
        }

        try:
            query = """
                INSERT INTO model (
                    id, user_id, base_model_id, name, meta, params,
                    created_at, updated_at, access_control, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            result = self.db.execute_query(
                query,
                (
                    model_id,
                    user_id,
                    base_model_id,
                    name,
                    json.dumps(meta),
                    json.dumps(params),
                    current_time,
                    current_time,
                    json.dumps(access_control),
                    True
                )
            )
            return result is not None
        except Exception as e:
            print(f"Error creating model: {e}")
            return False

    def add_group_to_model(
        self,
        model_id: str,
        group_id: str,
        permission_type: str = "read"
    ) -> bool:
        """
        Add a group to model's access control list
        permission_type can be 'read' or 'write'
        """
        try:
            query = "SELECT access_control FROM model WHERE id = ?"
            logging.info(f"Getting current access control for model {model_id}")
            result = self.db.execute_query(query, (model_id,), fetch_one=True)
            
            if not result:
                logging.error(f"No model found with id {model_id}")
                return False
            
            access_control = json.loads(result[0]) if result[0] else {
                "read": {"group_ids": [], "user_ids": []},
                "write": {"group_ids": [], "user_ids": []}
            }
            logging.info(f"Current access control: {access_control}")
            
            if permission_type not in ["read", "write"]:
                raise ValueError("Permission type must be 'read' or 'write'")
            
            if group_id not in access_control[permission_type]["group_ids"]:
                access_control[permission_type]["group_ids"].append(group_id)
                logging.info(f"Added group {group_id} to {permission_type} access. New access control: {access_control}")
            
            update_query = """
                UPDATE model 
                SET access_control = ?,
                    updated_at = ?
                WHERE id = ?
            """
            
            current_time = int(datetime.now().timestamp())
            success = self.db.execute_query(
                update_query,
                (json.dumps(access_control), current_time, model_id)
            )
            logging.info(f"Update result: {success}")
            
            return success is not None
            
        except Exception as e:
            logging.error(f"Error adding group to model: {e}")
            return False

    def remove_group_from_model(
        self,
        model_id: str,
        group_id: str,
        permission_type: str = "read"
    ) -> bool:
        """
        Remove a group from model's access control list
        """
        try:
            query = "SELECT access_control FROM model WHERE id = ?"
            result = self.db.execute(query, (model_id,)).fetchone()
            
            if not result:
                return False
            
            access_control = json.loads(result[0])
            
            if permission_type not in ["read", "write"]:
                raise ValueError("Permission type must be 'read' or 'write'")
            
            if group_id in access_control[permission_type]["group_ids"]:
                access_control[permission_type]["group_ids"].remove(group_id)
            
            update_query = """
                UPDATE model 
                SET access_control = ?,
                    updated_at = ?
                WHERE id = ?
            """
            
            current_time = int(datetime.now().timestamp())
            self.db.execute(
                update_query,
                (json.dumps(access_control), current_time, model_id)
            )
            
            return True
            
        except Exception as e:
            print(f"Error removing group from model: {e}")
            return False

    def get_model_groups(self, model_id: str) -> Dict[str, List[str]]:
        """
        Get all groups associated with a model
        Returns a dictionary with read and write group lists
        """
        try:
            query = "SELECT access_control FROM model WHERE id = ?"
            result = self.db.execute(query, (model_id,)).fetchone()
            
            if not result:
                return {"read": [], "write": []}
            
            access_control = json.loads(result[0])
            return {
                "read": access_control["read"]["group_ids"],
                "write": access_control["write"]["group_ids"]
            }
            
        except Exception as e:
            print(f"Error getting model groups: {e}")
            return {"read": [], "write": []}

    def add_group_to_model_by_name(
        self,
        user_id: str,
        model_name: str,
        group_id: str,
        permission_type: str = "read"
    ) -> Optional[Dict]:
        """
        Add a group to a model's permissions, creating the model if it doesn't exist
        
        Args:
            user_id: ID of the model owner
            model_name: Name of the model
            group_id: ID of the group to add
            permission_type: Type of permission ("read" or "write")
            
        Returns:
            Optional[Dict]: Model data if successful, None if failed
        """
        try:
            # Check if model exists
            query = """
                SELECT * FROM model 
                WHERE name = ? AND user_id = ? AND is_active = 1
            """
            existing_model = self.db.execute_query(query, (model_name, user_id), fetch_one=True)

            if existing_model:
                # Add group to existing model
                success = self.add_group_to_model(
                    model_id=existing_model[0],
                    group_id=group_id,
                    permission_type=permission_type
                )
                
                if not success:
                    return None
                
                # Get updated model
                updated_model = self.db.execute_query(
                    "SELECT * FROM model WHERE id = ?", 
                    (existing_model[0],),
                    fetch_one=True
                )
                
            else:
                # Create new model with group permission
                import uuid
                model_id = str(uuid.uuid4())
                
                # Prepare access control with the group
                access_control = {
                    "read": {"group_ids": [], "user_ids": []},
                    "write": {"group_ids": [], "user_ids": []}
                }
                access_control[permission_type]["group_ids"].append(group_id)
                
                # Create model query
                create_query = """
                    INSERT INTO model (
                        id, user_id, name, access_control, 
                        created_at, updated_at, is_active
                    ) VALUES (?, ?, ?, ?, ?, ?, 1)
                """
                current_time = int(datetime.now().timestamp())
                success = self.db.execute_query(
                    create_query,
                    (
                        model_id, user_id, model_name,
                        json.dumps(access_control),
                        current_time, current_time
                    )
                )
                
                if not success:
                    return None
                    
                updated_model = self.db.execute_query(
                    "SELECT * FROM model WHERE id = ?", 
                    (model_id,),
                    fetch_one=True
                )
                
            if not updated_model:
                return None
                
            # Format model data
            return {
                "id": updated_model[0],
                "name": updated_model[3],
                "base_model_id": updated_model[2],
                "meta": json.loads(updated_model[4]) if updated_model[4] else {},
                "params": json.loads(updated_model[5]) if updated_model[5] else {},
                "access_control": json.loads(updated_model[8]) if updated_model[8] else {},
                "is_active": bool(updated_model[9])
            }
                
        except Exception as e:
            print(f"Error in add_group_to_model_by_name: {e}")
            return None
