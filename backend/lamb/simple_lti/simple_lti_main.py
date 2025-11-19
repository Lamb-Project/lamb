from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
import logging
import os

# Configure logging
logging.basicConfig(level=logging.WARNING)

# Initialize router
router = APIRouter(
    prefix="/simple_lti",
    tags=["Simple LTI"],
    responses={404: {"description": "Not found"}}
)

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

@router.get("/")
async def simple_lti_page(request: Request):
    """Serve the Simple LTI interface"""
    try:
        return templates.TemplateResponse("simple_lti.html", {"request": request})
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error serving Simple LTI page: {str(e)}"
        )

# Add more endpoints as needed for Simple LTI functionality
@router.post("/launch")
async def lti_launch(request: Request):
    """Handle LTI launch requests"""
    try:
        # Add your LTI launch logic here
        data = await request.json()
        return {"status": "success", "message": "LTI launch successful"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error during LTI launch: {str(e)}"
        )

@router.get("/config")
async def lti_config(request: Request):
    """Provide LTI configuration"""
    try:
        return {
            "status": "success",
            "config": {
                "version": "1.1.0",
                "title": "LAMB Simple LTI Tool",
                "description": "LAMB Simple LTI Tool"
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting LTI config: {str(e)}"
        )
