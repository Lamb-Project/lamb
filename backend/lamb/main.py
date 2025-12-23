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
from .lti_users_router import router as lti_users_router
from .owi_bridge.owi_router import router as owi_router
from .owi_bridge.owi_users import OwiUserManager
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from .simple_lti.simple_lti_main import router as simple_lti_router
from .completions.main import router as completions_router
from .mcp_router import router as mcp_router  # MCP protocol - KEEP (used by frontend for external MCP clients)

logging.basicConfig(level=logging.WARNING)

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

# Removed unused template endpoints:
# - /v1/auth (permissions.html) - unused legacy model permissions system
# - /v1/OWI (owi_test.html) - use /lamb/v1/OWI/ instead
# - /v1/assistant (assistants.html) - logic moved to AssistantService
# - /v1/creator_user (creator_users.html) - logic moved to CreatorUserService
# - /v1/organization (various) - logic moved to OrganizationService

security = HTTPBearer()


class ModelFilter(BaseModel):
    include: List[str]
    exclude: List[str]

class UserPermissions(BaseModel):
    user_email: EmailStr
    filter: ModelFilter

# REMOVED: Legacy /v1/auth router (unused model permissions system)
# REMOVED: assistant_router (logic moved to AssistantService)
# REMOVED: creator_user_router (logic moved to CreatorUserService)
# REMOVED: organization_router (logic moved to OrganizationService)
# REMOVED: config_router (unused configuration management)
app.include_router(lti_users_router, prefix="/v1/lti_users")
app.include_router(owi_router, prefix="/v1/OWI")
app.include_router(simple_lti_router)
app.include_router(completions_router, prefix="/v1/completions")
app.include_router(mcp_router, prefix="/v1/mcp")  # MCP protocol - KEEP (used by frontend)

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
