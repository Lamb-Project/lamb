import json
from fastapi import HTTPException, status
import lamb.database_manager as db_manager
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="API")

def completions_get_form_data(body_str: str):
    """
    Extracts form data from a request object.
    The goal is to convert the request body to a form data object that 
    can be used by the completions endpoint. 

    -> the goal is to handle both the "messages" and "prompt" fields
    by returning a form_data object that can be used by the completions endpoint.
    Args:
        request: The request object containing form data.
    """
    logger.debug("Starting Chat Completion Request")
    # Parse the JSON body manually
    try:
        form_data = json.loads(body_str)
        logger.debug(f"Parsed JSON data: {json.dumps(form_data, indent=2)}")
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {str(e)}"
        )
    
    # Validate required fields - now either 'messages' or 'prompt' is required
    if 'model' not in form_data:
        error_msg = "Missing required field: model"
        logger.error(f"Validation error: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )

    # Handle both message formats
    if 'prompt' in form_data:
        prompt_content = form_data['prompt']
        messages = [{"role": "user", "content": prompt_content}]
        form_data['messages'] = messages
    #    print("\nConverted prompt to messages format")
    elif 'params' in form_data and 'prompt' in form_data['params']:
        # Handle prompt inside params object
        prompt_content = form_data['params']['prompt']
        # Handle if prompt is a list
        if isinstance(prompt_content, list):
            prompt_content = ' '.join(str(item) for item in prompt_content)
        # Convert to messages format
        messages = [{"role": "user", "content": prompt_content}]
        form_data['messages'] = messages
     #   print("\nConverted params.prompt to messages format")
    elif 'messages' not in form_data:
        error_msg = "Request must include either 'messages', 'prompt', or 'params.prompt' field"
      #  print(f"\nValidation error: {error_msg}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    _validate_messages(form_data['messages'])

    logger.debug(f"REQUEST Form data: {json.dumps(form_data, indent=2)}")

    return form_data


def _validate_messages(messages):
    for msg in messages:
        if not isinstance(msg, dict) or 'role' not in msg or 'content' not in msg:
            error_msg = "Invalid message format. Each message must have 'role' and 'content'"
            logger.error(f"Validation error: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
       
def helper_get_assistant_id(model: str):
    """
    Get the assistant ID from the model name.
    It can either be the assistant ID or the assistant name.
    """
    db = db_manager.LambDatabaseManager()
    logger.debug(f"Getting assistant ID for model: {model}")
    # Remove "lamb_assistant." prefix if present
    if model.startswith("lamb_assistant."):
        model = model[15:]  # Remove "lamb_assistant." prefix
    assistant = db.get_assistant_by_id(model)
    logger.debug(f"try AS ID Assistant: {assistant}")
    if assistant:
        return assistant.id
    else:
        # Remove "LAMB:" prefix if present
        if model.startswith("LAMB:"):
            model = model[5:]  # Remove first 5 characters ("LAMB:")
        assistant = db.get_assistant_by_name(model)
        logger.debug(f"try AS NAME Assistant: {assistant}")
        if assistant: 
            return assistant.id
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assistant not found: {model}"
            )

def helper_get_all_assistants(filter_deleted: bool = False):
    """
    Get all assistants from the database.
    If filter_deleted is True, it will exclude deleted assistants.
    """
    logger.debug(f"Getting all assistants with filter_deleted: {filter_deleted}")
    db = db_manager.LambDatabaseManager()
    assistants = db.get_list_of_assitants_id_and_name()
    if filter_deleted:
        unfiltered_assistants = assistants
        assistants = []
        for assistant in unfiltered_assistants:
            if assistant.get("owner") != "deleted_assistant@owi.com":
                assistants.append(assistant)
                logger.debug(f"Including assistant: {assistant.get('name')}, owner: {assistant.get('owner')}")
            else:
                logger.debug(f"Excluding deleted assistant: {assistant.get('name')}")
    return assistants


