from abc import ABC, abstractmethod
from pydantic import BaseModel
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from typing import List, Dict, Any, Optional

class LTIContext(BaseModel):
    """Normalized context passed from the Router to the Module"""
    resource_link_id: str
    lms_user_id: str
    lms_email: str
    username: str
    display_name: str
    roles: str
    is_instructor: bool
    context_id: str
    context_title: str

class SetupField(BaseModel):
    """Defines extra fields the module needs on the setup page"""
    name: str           # e.g., 'rubric_pdf' or 'chat_visibility_enabled'
    label: str          # "Upload Rubric"
    field_type: str     # 'file', 'checkbox', 'select', 'number'
    required: bool = False
    options: List[Dict[str, str]] = []  # For select fields

class ActivityModule(ABC):
    """The Contract every module must fulfill."""
    name: str            # Unique identifier (e.g., "chat", "file_evaluation")
    display_name: str    # Human readable ("AI Chat Activity")
    description: str     # Shown to instructors in the setup dropdown
    
    @abstractmethod
    def get_migrations(self) -> List[str]:
        """SQL statements to create module-specific tables."""
        pass

    @abstractmethod
    def get_routers(self) -> List[APIRouter]:
        """FastAPI routers with module endpoints, mounted under /lamb/v1/modules/{name}/"""
        pass
        
    @abstractmethod
    def get_setup_fields(self) -> List[SetupField]:
        """Extra configuration fields for the activity setup page."""
        pass
        
    @abstractmethod
    def on_activity_configured(self, activity_id: int, setup_data: Dict[str, Any]) -> None:
        """Called when an instructor finishes the setup form. 
        Raise an HTTPException(status_code=400, detail="...") if the configuration is invalid.
        """
        pass
        
    @abstractmethod
    def on_student_launch(self, ctx: LTIContext) -> RedirectResponse:
        """Called when a student launches an activity of this type."""
        pass
        
    @abstractmethod
    def on_instructor_launch(self, ctx: LTIContext) -> RedirectResponse:
        """Called when an instructor launches an activity of this type."""
        pass

    @abstractmethod
    def get_frontend_build_path(self) -> Optional[str]:
        """Path to built SvelteKit SPA for this module (served at /m/{name}/)."""
        pass
