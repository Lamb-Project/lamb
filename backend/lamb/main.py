import os
import logging
from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from utils.pipelines.auth import bearer_security, get_current_user
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import List
from .database_manager import LambDatabaseManager
from config import API_KEY  # Import the API_KEY from your config file
from fastapi import APIRouter
from .assistant_router import assistant_router  # Add this import
from .lti_users_router import router as lti_users_router
from .owi_bridge.owi_router import router as owi_router
from .owi_bridge.owi_users import OwiUserManager
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from .simple_lti.simple_lti_main import router as simple_lti_router
from .creator_user_router import router as creator_user_router
from .completions.main import router as completions_router
from .config_router import router as config_router  # Add this import
from .mcp_router import router as mcp_router  # Add MCP router import
from .organization_router import router as organization_router  # Add organization router import

logging.basicConfig(level=logging.DEBUG)

app = FastAPI(
    title="LAMB API",
    description="LAMB API for managing users and assistants",
    version="1.0.0"
)

# Mount the static directory
app.mount("/static", StaticFiles(directory="static"), name="static")

db_manager = LambDatabaseManager()


# Initialize templates
templates = Jinja2Templates(directory=[
    "lamb/templates",  # Main templates directory
    "lamb/lti/templates"  # LTI templates directory
])

# Make sure the templates can find each other by setting the correct paths
templates.env.loader.searchpath = [
    os.path.abspath("lamb/templates"),
    os.path.abspath("lamb/lti/templates")
]

@app.get("/v1")
async def read_index(request: Request):
    if os.getenv("DEV_MODE") == "true":
        return templates.TemplateResponse("index.html", {"request": request, "api_key": API_KEY})
    else:
        return JSONResponse(content={"error": "Not found"}, status_code=404)

@app.get("/v1/auth")
async def read_permissions(request: Request):
    return templates.TemplateResponse("permissions.html", {"request": request, "api_key": API_KEY})

@app.get("/v1/OWI")
async def read_owi(request: Request):
    return templates.TemplateResponse("owi_test.html", {"request": request, "api_key": API_KEY})

app.include_router(assistant_router, prefix="/v1/assistant")

security = HTTPBearer()


class ModelFilter(BaseModel):
    include: List[str]
    exclude: List[str]

class UserPermissions(BaseModel):
    user_email: EmailStr
    filter: ModelFilter

router = APIRouter()

@router.get("/")
async def root(request: Request):
    if os.getenv("DEV_MODE") == "true":
        return templates.TemplateResponse("index.html", {"request": request, "api_key": API_KEY})
    else:
        return JSONResponse(content={"error": "Not found"}, status_code=404)

@router.post("/update_permissions")
async def update_permissions(user_permissions: UserPermissions, str = Depends(get_current_user)):
    logging.debug("Entering update_permissions method")
    try:
        logging.debug(f"Received user_permissions: {user_permissions}")
        db_manager.update_model_permissions(user_permissions.dict())
        logging.debug("Permissions updated successfully in the database")
        return {"message": "Permissions updated successfully"}
    except Exception as e:
        logging.debug(f"Error updating permissions: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/get_permissions/{user_email}")
async def get_permissions(user_email: EmailStr, str = Depends(get_current_user)):
    
    try:
        permissions = db_manager.get_model_permissions(user_email)
        if permissions:
            logging.debug(f"Permissions found for user_email: {user_email}")
            return permissions
        else:
            logging.debug(f"No permissions found for user_email: {user_email}")
            return []
    except Exception as e:
        logging.debug(f"Error retrieving permissions for user_email: {user_email}, error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.post("/create_database_and_tables")
async def create_database_and_tables(str = Depends(get_current_user)):
    try:
        db_manager.create_database_and_tables()
        return JSONResponse(content={"message": "Database and tables created successfully"}, status_code=200)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@router.post("/filter_models") 
async def filter_models(request: Request, str = Depends(get_current_user)):
    logging.debug("Entering filter_models endpoint")
    try:
        logging.debug("request: %s", request   )
        # Parse the request body
        body = await request.json()
        logging.debug(f"Received request body: {body}")

        # Extract email and models from the body
        email = body.get('email')
        models = body.get('models')

        logging.debug(f"Extracted email: {email}, models: {models}")

        # Validate the input
        if not email or not models:
            raise HTTPException(status_code=422, detail="Missing email or models in request body")

        # Call the filter_models method
        filtered_models = db_manager.filter_models(email, models)
        logging.debug(f"Filtered models: {filtered_models}")

        return filtered_models
    except Exception as e:
        logging.error(f"Error in filter_models: {str(e)}")
        return JSONResponse(content={"error": str(e)}, status_code=500)

app.include_router(router, prefix="/v1/auth")
app.include_router(assistant_router, prefix="/v1/assistant")  # Add this line
app.include_router(lti_users_router, prefix="/v1/lti_users")
app.include_router(owi_router, prefix="/v1/OWI")
app.include_router(simple_lti_router)
app.include_router(creator_user_router, prefix="/v1/creator_user")
app.include_router(completions_router, prefix="/v1/completions")
app.include_router(config_router, prefix="/v1/config")  # Add the config router
app.include_router(mcp_router, prefix="/v1/mcp")  # Add the MCP router
app.include_router(organization_router, prefix="/v1")  # Add the organization router

# Evaluaitor (Rubrics) router
from .evaluaitor.rubrics import router as evaluaitor_router
app.include_router(evaluaitor_router, prefix="/v1/evaluaitor", tags=["Evaluaitor"])

@app.get("/v1/lti_users")
async def read_lti_users(request: Request):
    return templates.TemplateResponse("lti_users.html", {"request": request, "api_key": API_KEY})

@app.get("/v1/simple_lti")
async def read_simple_lti(request: Request):
    return templates.TemplateResponse("simple_lti.html", {"request": request, "api_key": API_KEY})

# Direct test endpoint for role updates - bypassing router
@app.post("/v1/OWI/users/direct-role-update")
async def direct_role_update(request: Request):
    import logging
    logging.error("[DIRECT_ENDPOINT] Direct role update endpoint called")
    try:
        data = await request.json()
        logging.error(f"[DIRECT_ENDPOINT] Request data: {data}")
        
        user_id = data.get('user_id')
        new_role = data.get('role')
        
        if not user_id or not new_role:
            logging.error(f"[DIRECT_ENDPOINT] Missing required fields. user_id: {user_id}, role: {new_role}")
            return {"success": False, "message": "Missing required fields"}
            
        logging.error(f"[DIRECT_ENDPOINT] Attempting to update user {user_id} to role {new_role}")
        
        # Using the user_manager directly - bypassing all middleware
        from .owi_bridge.owi_users import OwiUserManager
        user_manager = OwiUserManager()
        
        result = user_manager.update_user_role(str(user_id), new_role)
        logging.error(f"[DIRECT_ENDPOINT] Update result: {result}")
        
        return {"success": result, "message": "Role updated successfully" if result else "Failed to update role"}
    except Exception as e:
        import traceback
        logging.error(f"[DIRECT_ENDPOINT] Exception: {type(e).__name__}: {str(e)}")
        logging.error(f"[DIRECT_ENDPOINT] Traceback:\n{traceback.format_exc()}")
        return {"success": False, "message": f"Error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=2222)
