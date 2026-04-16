from __future__ import annotations

from typing import Any, Dict, Literal, Optional, Union

from fastapi import APIRouter, Body, HTTPException, Request, Response
from starlette.concurrency import run_in_threadpool

from .container import Container, get_lock
from .repositories import cart as cart_repo
from .repositories import catalog as catalog_repo
from .schemas import (
    AddCartRequest,
    CartActionResponse,
    CartItemOut,
    CartListOut,
    CartMutationOut,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    CsrfTokenOut,
    HealthOut,
    OperationPreview,
    RemoveCartRequest,
    UpdateCartRequest,
)
from .security import issue_confirmation_token, issue_csrf_token, require_user_id, verify_confirmation_token, verify_csrf
from .services.filters import validate_safe_text
from .services.skills import SkillContext


router = APIRouter()


def _container(request: Request) -> Container:
    return request.app.state.container


def _client_key(request: Request, user_id: Optional[int]) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"u:{user_id or 0}|ip:{client_host}"


def _conversation_owner_key(request: Request, user_id: Optional[int]) -> str:
    if user_id is not None:
        return f"user:{user_id}"
    client_host = request.client.host if request.client else "unknown"
    return f"anon:{client_host}"


def _agent_lang_from_request(request: Request) -> str:
    raw = request.headers.get("x-user-lang") or request.headers.get("accept-language") or "zh"
    primary = str(raw).split(",", 1)[0].split(";", 1)[0].strip().lower()
    if primary.startswith("en") or primary.startswith("ja"):
        return "en"
    return "zh"


@router.get("/health", response_model=HealthOut, tags=["system"])
async def health(request: Request):
    container = _container(request)
    return HealthOut(status="ok", deepseek_enabled=container.deepseek.enabled)


@router.get("/debug/deepseek", tags=["system"])
async def debug_deepseek(request: Request):
    container = _container(request)
    return container.deepseek.diagnostics()


@router.get("/csrf-token", response_model=CsrfTokenOut, tags=["security"])
async def csrf_token(request: Request, response: Response):
    container = _container(request)
    user_id = None
    try:
        user_id = require_user_id(request, container.settings)
    except HTTPException:
        user_id = None
    token = issue_csrf_token(container.settings, user_id)
    response.set_cookie("agent_csrf", token, httponly=False, samesite="strict", secure=container.settings.enforce_https)
    return CsrfTokenOut(csrf_token=token, expires_in=7200)


@router.post("/chat", response_model=ChatResponse, tags=["assistant"])
async def chat(request: Request, payload: ChatRequest):
    container = _container(request)
    safe_message = validate_safe_text(payload.message)
    agent_lang = _agent_lang_from_request(request)
    user_id = None
    try:
        user_id = require_user_id(request, container.settings)
    except HTTPException:
        user_id = None

    await container.rate_limiter.check(_client_key(request, user_id), container.settings.chat_rate_limit, container.settings.rate_window_seconds)

    container.runtime_logger.info("chat_request deepseek=%s model=%s message=%s", container.deepseek.enabled, container.settings.deepseek_model, safe_message[:80])

    conversation_id = container.conversations.get_or_create_id(payload.conversation_id)
    try:
        container.conversations.bind_owner(conversation_id, _conversation_owner_key(request, user_id))
    except PermissionError:
        raise HTTPException(status_code=403, detail="会话不属于当前用户")
    container.conversations.append(conversation_id, "user", safe_message)

    history = [{"role": role, "content": content} for role, content, _ in container.conversations.history(conversation_id)[:-1]]
    skill_ctx = SkillContext(deepseek=container.deepseek, user_id=user_id, agent_lang=agent_lang)

    with container.read_sessionmaker() as db:
        result = await container.skills.book_lookup.run(skill_ctx, db, safe_message, history)

    container.conversations.append(conversation_id, "assistant", result["reply"])
    history_out = []
    for role, content, created_at in container.conversations.history(conversation_id):
        typed_role: Literal["user", "assistant"] = "assistant" if role == "assistant" else "user"
        history_out.append(ChatMessageOut(role=typed_role, content=content, created_at=created_at))
    return ChatResponse(
        conversation_id=conversation_id,
        reply=result["reply"],
        references=result["references"],
        history=history_out,
        action_suggestion=result.get("action_suggestion"),
    )


@router.get("/cart", response_model=CartListOut, tags=["cart"])
async def cart_list(request: Request):
    container = _container(request)
    user_id = require_user_id(request, container.settings)
    await container.rate_limiter.check(_client_key(request, user_id), container.settings.cart_rate_limit, container.settings.rate_window_seconds)
    with container.read_sessionmaker() as db:
        items = await run_in_threadpool(cart_repo.list_items, db, user_id)
    return CartListOut(
        items=[
            CartItemOut(
                item_id=item.id,
                sku_id=item.sku_id,
                product_id=item.sku.product.id,
                product_title=item.sku.product.title,
                option_summary=item.sku.option_values,
                quantity=item.quantity,
                is_available=item.sku.is_available,
                stock_quantity=item.sku.stock_quantity,
            )
            for item in items
        ]
    )


async def _build_confirmation(request: Request, action: str, product_title: str, quantity: Optional[int], option_summary: Optional[str], token_payload: Dict[str, Any], preview: OperationPreview) -> CartActionResponse:
    container = _container(request)
    user_id = require_user_id(request, container.settings)
    agent_lang = _agent_lang_from_request(request)
    prompt = await container.skills.cart_guard.run(SkillContext(deepseek=container.deepseek, user_id=user_id, agent_lang=agent_lang), action, product_title, quantity, option_summary)
    token = issue_confirmation_token(container.settings, user_id, action, token_payload)
    return CartActionResponse(confirmation_message=prompt, confirmation_token=token, preview=preview)


@router.post("/cart/add", response_model=Union[CartActionResponse, CartMutationOut], tags=["cart"])
async def cart_add(request: Request, payload: AddCartRequest):
    container = _container(request)
    user_id = require_user_id(request, container.settings)
    verify_csrf(request, container.settings, user_id)
    await container.rate_limiter.check(_client_key(request, user_id), container.settings.cart_rate_limit, container.settings.rate_window_seconds)

    with container.read_sessionmaker() as db:
        preview_data = await run_in_threadpool(catalog_repo.get_sku_preview, db, payload.sku_id)
    if not preview_data:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    if preview_data["is_available"] is False:
        raise HTTPException(status_code=400, detail="SKU 不可售")
    if preview_data["stock_quantity"] is not None and payload.quantity > preview_data["stock_quantity"]:
        raise HTTPException(status_code=400, detail="库存不足")

    token_payload = {"sku_id": payload.sku_id, "quantity": payload.quantity}
    preview = OperationPreview(sku_id=payload.sku_id, product_title=preview_data["product_title"], option_summary=preview_data.get("option_summary"), quantity=payload.quantity)
    if not payload.confirmed:
        return await _build_confirmation(request, "add", preview_data["product_title"], payload.quantity, preview_data.get("option_summary"), token_payload, preview)

    if not payload.confirmation_token:
        raise HTTPException(status_code=400, detail="缺少确认令牌")
    verify_confirmation_token(container.settings, payload.confirmation_token, user_id, "add", token_payload)

    async with get_lock(container, f"cart:add:{user_id}:{payload.sku_id}"):
        with container.write_sessionmaker() as db:
            message = await run_in_threadpool(cart_repo.add_item, db, user_id, payload.sku_id, payload.quantity)
    container.audit_logger.info("user_id=%s action=cart_add sku_id=%s quantity=%s", user_id, payload.sku_id, payload.quantity)
    return CartMutationOut(success=True, message=message)


@router.put("/cart/update", response_model=Union[CartActionResponse, CartMutationOut], tags=["cart"])
async def cart_update(request: Request, payload: UpdateCartRequest):
    container = _container(request)
    user_id = require_user_id(request, container.settings)
    verify_csrf(request, container.settings, user_id)
    await container.rate_limiter.check(_client_key(request, user_id), container.settings.cart_rate_limit, container.settings.rate_window_seconds)

    with container.write_sessionmaker() as db:
        item = await run_in_threadpool(cart_repo.get_item, db, user_id, payload.item_id)
        if not item:
            raise HTTPException(status_code=404, detail="购物车项不存在")
        product_title = item.sku.product.title
        option_summary = item.sku.option_values

    token_payload = {"item_id": payload.item_id, "quantity": payload.quantity}
    preview = OperationPreview(cart_item_id=payload.item_id, sku_id=item.sku_id, product_title=product_title, option_summary=option_summary, quantity=payload.quantity)
    if not payload.confirmed:
        return await _build_confirmation(request, "update", product_title, payload.quantity, option_summary, token_payload, preview)

    if not payload.confirmation_token:
        raise HTTPException(status_code=400, detail="缺少确认令牌")
    verify_confirmation_token(container.settings, payload.confirmation_token, user_id, "update", token_payload)

    async with get_lock(container, f"cart:update:{user_id}:{payload.item_id}"):
        with container.write_sessionmaker() as db:
            message = await run_in_threadpool(cart_repo.update_item, db, user_id, payload.item_id, payload.quantity)
    container.audit_logger.info("user_id=%s action=cart_update item_id=%s quantity=%s", user_id, payload.item_id, payload.quantity)
    return CartMutationOut(success=True, message=message)


@router.delete("/cart/remove", response_model=Union[CartActionResponse, CartMutationOut], tags=["cart"])
async def cart_remove(request: Request, payload: RemoveCartRequest = Body(...)):
    container = _container(request)
    user_id = require_user_id(request, container.settings)
    verify_csrf(request, container.settings, user_id)
    await container.rate_limiter.check(_client_key(request, user_id), container.settings.cart_rate_limit, container.settings.rate_window_seconds)

    with container.write_sessionmaker() as db:
        item = await run_in_threadpool(cart_repo.get_item, db, user_id, payload.item_id)
        if not item:
            raise HTTPException(status_code=404, detail="购物车项不存在")
        product_title = item.sku.product.title
        option_summary = item.sku.option_values

    token_payload = {"item_id": payload.item_id}
    preview = OperationPreview(cart_item_id=payload.item_id, sku_id=item.sku_id, product_title=product_title, option_summary=option_summary, quantity=item.quantity)
    if not payload.confirmed:
        return await _build_confirmation(request, "remove", product_title, item.quantity, option_summary, token_payload, preview)

    if not payload.confirmation_token:
        raise HTTPException(status_code=400, detail="缺少确认令牌")
    verify_confirmation_token(container.settings, payload.confirmation_token, user_id, "remove", token_payload)

    async with get_lock(container, f"cart:remove:{user_id}:{payload.item_id}"):
        with container.write_sessionmaker() as db:
            message = await run_in_threadpool(cart_repo.remove_item, db, user_id, payload.item_id)
    container.audit_logger.info("user_id=%s action=cart_remove item_id=%s", user_id, payload.item_id)
    return CartMutationOut(success=True, message=message)
