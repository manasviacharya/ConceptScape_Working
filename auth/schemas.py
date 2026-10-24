from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: str
    password: str


class WorkspaceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)


class WorkspaceMemberRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=320)
