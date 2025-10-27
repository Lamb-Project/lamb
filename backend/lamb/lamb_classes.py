from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime

class Organization(BaseModel):
    id: int = Field(default=0)
    slug: str
    name: str
    is_system: bool = Field(default=False)
    status: str = Field(default="active")
    config: Dict[str, Any]
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    
    class Config:
        from_attributes = True
    
    def get_setup(self, setup_name: str = "default") -> Optional[Dict[str, Any]]:
        """Get a specific setup configuration"""
        return self.config.get("setups", {}).get(setup_name)
    
    def get_provider_config(self, provider: str, setup: str = "default") -> Optional[Dict[str, Any]]:
        """Get provider configuration from a specific setup"""
        setup_config = self.get_setup(setup)
        return setup_config.get("providers", {}).get(provider) if setup_config else None

class OrganizationRole(BaseModel):
    id: int = Field(default=0)
    organization_id: int
    user_id: int
    role: str  # 'owner', 'admin', 'member'
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    
    class Config:
        from_attributes = True

class Assistant(BaseModel):
    id: int = Field(default=0)
    organization_id: Optional[int] = None  # Organization the assistant belongs to
    name: str
    description: str
    owner: str
    api_callback: str  # DEPRECATED: Use metadata property instead. Kept for DB compatibility.
    system_prompt: str
    prompt_template: str
    pre_retrieval_endpoint: str  # DEPRECATED: Always empty string, kept for DB compatibility
    post_retrieval_endpoint: str  # DEPRECATED: Always empty string, kept for DB compatibility
    RAG_endpoint: str  # DEPRECATED: Mostly unused, always empty string, kept for DB compatibility
    RAG_Top_k: int
    RAG_collections: str

    class Config:
        from_attributes = True
    
    @property
    def metadata(self) -> str:
        """
        Virtual field that maps to api_callback for backward compatibility.
        
        IMPORTANT FOR FUTURE DEVELOPERS:
        - This property provides the semantic name 'metadata' for what's stored in 'api_callback'
        - The DB column remains 'api_callback' to avoid database schema migration
        - All new code should use 'metadata' instead of 'api_callback'
        - Contains JSON-encoded plugin configuration like:
          {
              "prompt_processor": "simple_augment",
              "connector": "openai",
              "llm": "gpt-4o-mini",
              "rag_processor": "no_rag",
              "file_path": ""
          }
        """
        return self.api_callback
    
    @metadata.setter
    def metadata(self, value: str):
        """Set metadata by updating the underlying api_callback field"""
        self.api_callback = value

    # def __init__(self, assistant_data): 
    #     super().__init__()
    #     self.id = assistant_data['id']  # This is the database id - for the add_assistant function it is set by the database
    #     self.name = assistant_data['name']  # The name of the assistant
    #     self.description = assistant_data['description']  # The description of the assistant
    #     self.owner = assistant_data['owner']  # The owner of the assistant - email
    #     self.api_callback = assistant_data['api_callback']  # The api callback url for the RAG queries to open-webui
    #     self.system_prompt = assistant_data['system_prompt']  # The system prompt for the assistant
    #     self.prompt_template = assistant_data['prompt_template']  # The prompt template for the assistant 
    #     self.pre_retrieval_endpoint = assistant_data['pre_retrieval_endpoint']  # The pre-retrieval endpoint for the assistant
    #     self.post_retrieval_endpoint = assistant_data['post_retrieval_endpoint']  # The post-retrieval endpoint for the assistant
    #     self.llm = assistant_data['llm']  # text identifier for the LLM used by the assistant , ex "Claude 3.5 Sonnet"

class LTIUser(BaseModel):
    id: int = Field(default=0)
    assistant_id: str
    assistant_name: str
    group_id: str
    group_name: str
    assistant_owner: str
    user_email: str
    user_name: str
    user_display_name: str
    lti_context_id: str
    lti_app_id: str

class PromptTemplate(BaseModel):
    id: int = Field(default=0)
    organization_id: int
    owner_email: str
    name: str
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    prompt_template: Optional[str] = None
    is_shared: bool = Field(default=False)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    updated_at: int = Field(default_factory=lambda: int(datetime.now().timestamp()))
    
    # Additional fields for display purposes (populated from joins)
    owner_name: Optional[str] = None
    is_owner: Optional[bool] = None
    
    class Config:
        from_attributes = True
   
