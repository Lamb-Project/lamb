import sqlite3
import os
import logging
import json
import time
from typing import List, Dict, Optional
from dotenv import load_dotenv

logging.basicConfig(level=logging.WARNING)

# Load environment variables
load_dotenv()

# Configurable wait settings to avoid magic numbers
DB_POLL_INTERVAL_SECONDS = float(os.getenv('OWI_DB_POLL_INTERVAL_SECONDS', '1'))

class OwiDatabaseManager:
    def __init__(self):
#        logging.debug("Initializing OwiDatabaseManager")
        try:
            # Get OWI_PATH from environment variables
            owi_path = os.getenv('OWI_PATH')
            if not owi_path:
                logging.error("OWI_PATH not found in environment variables")
                raise ValueError("OWI_PATH must be specified in .env file")
            
            self.db_path = os.path.join(owi_path, 'webui.db')
            if not os.path.exists(self.db_path):
                # Wait indefinitely for the database file to appear (user can cancel the app if desired)
                poll_interval = DB_POLL_INTERVAL_SECONDS
                logging.warning(
                    f"Database file not found at: {self.db_path}. Waiting until it becomes available..."
                )
                elapsed = 0.0
                while not os.path.exists(self.db_path):
                    time.sleep(poll_interval)
                    elapsed += poll_interval
                    logging.info(
                        f"Still waiting for database at: {self.db_path} (waited {int(elapsed)}s)"
                    )
            
#            logging.debug(f"Found database at: {self.db_path}")

        except Exception as e:
            logging.error(f"Error during initialization: {e}")
            raise

    
    def execute_query(self, query: str, params: tuple = (), fetch_one: bool = False) -> Optional[Dict]:
        """Execute a query and return results"""
#        logging.debug(f"Executing query: {query} with params: {params}")
        try:
            conn = self.get_connection()
            if not conn:
                return None
                
            cursor = conn.cursor()
            with conn:  # This ensures proper transaction handling
                cursor.execute(query, params)
                conn.commit()  # Explicitly commit the transaction
            
            if fetch_one:
                result = cursor.fetchone()
            else:
                result = cursor.fetchall()
                
            conn.close()
            return result
        except sqlite3.Error as e:
            logging.error(f"Database error in execute_query: {e}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in execute_query: {e}")
            return None

    def get_all_users(self) -> list[dict]:
        """
        Retrieve all users from the database
        
        Returns:
            list[dict]: List of all users as dictionaries
        """
        try:
            query = "SELECT * FROM user"
            results = self.execute_query(query, fetch_one=False)
            if results:
                users = [self._row_to_dict(row) for row in results]
 #               logging.debug(f"Retrieved {len(users)} users")
                return users
            logging.debug("No users found in database")
            return []
        except Exception as e:
            logging.error(f"Unexpected error in get_all_users: {e}")
            return []

    def get_user_by_id(self, user_id: str) -> dict | None:
        """Get user by ID"""
        if not user_id:
            logging.error("get_user_by_id called with empty user_id")
            return None
            
        try:
            query = "SELECT * FROM user WHERE id = ?"
            result = self.execute_query(query, (user_id,), fetch_one=True)
            if result:
 #               logging.debug(f"User found with id: {user_id}")
                return self._row_to_dict(result)
 #           logging.debug(f"No user found with id: {user_id}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in get_user_by_id: {e}")
            return None

    def get_user_by_email(self, email: str) -> dict | None:
        """Get user by email"""
        if not email:
            logging.error("get_user_by_email called with empty email")
            return None
            
        try:
            query = "SELECT * FROM user WHERE email = ?"
            result = self.execute_query(query, (email,), fetch_one=True)
            if result:
                #logging.debug(f"User found with email: {email}")
                return self._row_to_dict(result)
 #           logging.debug(f"No user found with email: {email}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error in get_user_by_email: {e}")
            return None

    def get_connection(self):
#        logging.debug(f"Attempting to connect to database at: {self.db_path}")
        try:
            connection = sqlite3.connect(self.db_path)
#            logging.debug("Database connection established successfully")
            return connection
        except sqlite3.Error as e:
            logging.error(f"Failed to connect to database: {e}")
            return None

    def display_tables_content(self):
        """Get the contents of all relevant tables in the OWI database"""
#        logging.debug("Getting contents of OWI database tables")
        
        connection = self.get_connection()
        if not connection:
            logging.error("Could not connect to database")
            return {"error": "Could not connect to database"}
        
        cursor = connection.cursor()
        
        tables = {
            'users': 'SELECT * FROM user',
            'groups': 'SELECT * FROM group',
            'auth': 'SELECT * FROM auth',
            'messages': 'SELECT * FROM model'
        }
        
        result = {}
        
        try:
            for table_name, query in tables.items():
                try:
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    
                    # Get column names
                    column_names = [description[0] for description in cursor.description]
                    
                    # Convert rows to list of dictionaries
                    table_data = []
                    for row in rows:
                        row_dict = dict(zip(column_names, row))
                        table_data.append(row_dict)
                    
                    result[table_name] = {
                        "columns": column_names,
                        "data": table_data
                    }
                    
                except sqlite3.Error as e:
                    result[table_name] = {"error": str(e)}
                    
        except Exception as e:
            logging.error(f"Error getting tables content: {e}")
            return {"error": str(e)}
        finally:
            connection.close()
#            logging.debug("Database connection closed")
            
        return result

    def _row_to_dict(self, row: tuple) -> dict:
        """
        Convert a database row to a dictionary using column names
        
        Args:
            row (tuple): Database row
            
        Returns:
            dict: Row data as dictionary
        """
        try:
            if not row:
                return {}
                
            columns = [
                'id', 'name', 'email', 'role', 'profile_image_url', 
                'api_key', 'created_at', 'updated_at', 'last_active_at',
                'settings', 'info', 'oauth_sub'
            ]
            
            if len(row) != len(columns):
                logging.error(f"Row length ({len(row)}) does not match columns length ({len(columns)})")
                return {}
                
            return dict(zip(columns, row))
        except Exception as e:
            logging.error(f"Error in _row_to_dict: {e}")
            return {}

    def get_group_by_id(self, group_id: str) -> Optional[Dict]:
        """Get group by ID"""
        if not group_id:
            return None
            
        try:
            query = 'SELECT * FROM "group" WHERE id = ?'
            result = self.execute_query(query, (group_id,), fetch_one=True)
            if result:
                columns = [
                    'id', 'user_ids', 'name', 'description', 
                    'created_at', 'updated_at', 'permissions'
                ]
                
                if len(result) == len(columns):
                    group_data = dict(zip(columns, result))
                    # Parse JSON fields
                    if isinstance(group_data.get('user_ids'), str):
                        try:
                            group_data['user_ids'] = json.loads(group_data['user_ids'])
                        except:
                            group_data['user_ids'] = []
                    if isinstance(group_data.get('permissions'), str):
                        try:
                            group_data['permissions'] = json.loads(group_data['permissions'])
                        except:
                            group_data['permissions'] = {}
                    return group_data
            return None
        except Exception as e:
            logging.error(f"Error in get_group_by_id: {e}")
            return None

    def get_users_in_group(self, group_id: str) -> List[Dict]:
        """Get all users in a group"""
        connection = self.get_connection()
        if connection:
            try:
                with connection:
                    cursor = connection.cursor()
                    cursor.execute("""
                        SELECT u.* 
                        FROM user u
                        JOIN "group" g ON g.id = ? AND json_array_contains(g.user_ids, u.id)
                    """, (group_id,))
                    
                    columns = [col[0] for col in cursor.description]
                    return [dict(zip(columns, row)) for row in cursor.fetchall()]
            except sqlite3.Error as e:
                logging.error(f"Error getting users in group: {e}")
                return []
            finally:
                connection.close()
        return []


    def get_config(self) -> dict | None:
        """
        Get the configuration record from the config table.
        Returns the entire record as a dictionary with modified OpenAI config, or None if not found.
        """
        try:
            query = """
                SELECT id, data, version, created_at, updated_at 
                FROM config 
                WHERE id = 1
            """
            result = self.execute_query(query, fetch_one=True)
            
            if result:
                # Parse the original config data
                config_data = json.loads(result[1])
                
                # Get values from environment variables
                lamb_base_url = os.getenv('LAMB_BASE_URL')
                api_key = os.getenv('OPENAI_API_KEY')
                
                # Modify the openai section
                if 'openai' in config_data:
                    config_data['openai'] = {
                        'api_base': lamb_base_url,
                        'api_key': api_key
                    }
                
                config_record = {
                    'id': result[0],
                    'data': config_data,
                    'version': result[2],
                    'created_at': result[3],
                    'updated_at': result[4]
                }
                logging.debug("Config record retrieved and modified successfully")
                return config_record
                
            logging.debug("No config record found")
            return None
            
        except Exception as e:
            logging.error(f"Error retrieving config record: {e}")
            return None

    def set_owi_config(self) -> bool:
        """
        Updates the OpenAI configuration in the config table to use LAMB_BASE_URL.
        Returns True if successful, False otherwise.
        """
        try:
            # First get current config
            query = "SELECT data FROM config WHERE id = 1"
            result = self.execute_query(query, fetch_one=True)
            
            if not result:
                logging.error("No config record found to update")
                return False
            
            # Parse current config
            config_data = json.loads(result[0])
            
            # Get values from environment variables
            lamb_base_url = os.getenv('LAMB_BASE_URL')
            api_key = os.getenv('OPENAI_API_KEY')
            
            if not lamb_base_url:
                logging.error("LAMB_BASE_URL not found in environment variables")
                return False
            
            # Modify the openai section while preserving structure
            if 'openai' in config_data:
                config_data['openai'].update({
                    'enable': True,
                    'api_base_urls': [lamb_base_url],
                    'api_keys': [api_key],
                    'api_configs': {
                        lamb_base_url: {
                            'enable': True,
                            'prefix_id': '',
                            'model_ids': []
                        }
                    }
                })
                
                # Update the config in database
                update_query = """
                    UPDATE config 
                    SET data = ?, 
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE id = 1
                """
                self.execute_query(update_query, (json.dumps(config_data),))
                logging.debug("Config updated successfully")
                return True
            
            logging.error("No openai section found in config")
            return False
            
        except Exception as e:
            logging.error(f"Error updating config: {e}")
            return False

    