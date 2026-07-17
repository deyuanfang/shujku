from pydantic import BaseModel
from typing import Optional, Any


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int


class APIResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Optional[Any] = None
