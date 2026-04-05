from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class HealthOut(BaseModel):
    status: str
    deepseek_enabled: bool


class CsrfTokenOut(BaseModel):
    csrf_token: str
    expires_in: int


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    conversation_id: Optional[str] = Field(default=None, max_length=80)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return value.strip()


class ChatMessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class BookReference(BaseModel):
    product_id: int
    sku_ids: List[int]
    title: str
    title_en: Optional[str] = None
    author: Optional[str] = None
    author_en: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    reply: str
    references: List[BookReference] = []
    history: List[ChatMessageOut] = []
    action_suggestion: Optional[Dict[str, Any]] = None


class ConfirmationUiOut(BaseModel):
    centered: bool = True
    require_manual_action: bool = True
    font_size_pt: int = 18
    dialog_width: str = "min(92vw, 560px)"
    confirm_label: str = "Confirm"
    cancel_label: str = "Cancel"


class OperationPreview(BaseModel):
    sku_id: Optional[int] = None
    cart_item_id: Optional[int] = None
    product_title: str
    option_summary: Optional[str] = None
    quantity: Optional[int] = None


class CartActionResponse(BaseModel):
    requires_confirmation: bool = True
    confirmation_message: str
    confirmation_token: str
    preview: OperationPreview
    ui: ConfirmationUiOut = ConfirmationUiOut()


class CartMutationOut(BaseModel):
    success: bool
    message: str


class CartItemOut(BaseModel):
    item_id: int
    sku_id: int
    product_id: int
    product_title: str
    option_summary: Optional[str] = None
    quantity: int
    is_available: bool
    stock_quantity: Optional[int] = None


class CartListOut(BaseModel):
    items: List[CartItemOut]


class AddCartRequest(BaseModel):
    sku_id: int
    quantity: int = Field(default=1, ge=1, le=99)
    confirmed: bool = False
    confirmation_token: Optional[str] = None


class UpdateCartRequest(BaseModel):
    item_id: int
    quantity: int = Field(ge=1, le=99)
    confirmed: bool = False
    confirmation_token: Optional[str] = None


class RemoveCartRequest(BaseModel):
    item_id: int
    confirmed: bool = False
    confirmation_token: Optional[str] = None
