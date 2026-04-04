from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_db
from ..deps import get_current_user, get_current_user_optional

router = APIRouter(prefix="/api/products", tags=["reviews"])


def _resolve_product(db: Session, product_id: int) -> models.Product:
    product = db.query(models.Product).filter(models.Product.id == product_id, models.Product.is_active == True).first()  # noqa: E712
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    return product


def _eligible_order_ids(db: Session, user_id: int, product_id: int) -> List[str]:
    rows = (
        db.query(models.Order.order_id)
        .join(models.OrderItem, models.OrderItem.order_id == models.Order.order_id)
        .join(models.ProductSKU, models.ProductSKU.id == models.OrderItem.sku_id)
        .filter(
            models.Order.user_id == user_id,
            models.Order.status == "completed",
            models.ProductSKU.product_id == product_id,
        )
        .distinct()
        .all()
    )
    return [str(order_id) for (order_id,) in rows]


def _rating_quota(db: Session, user_id: int, product_id: int) -> Tuple[int, List[str]]:
    eligible_order_ids = _eligible_order_ids(db, user_id, product_id)
    if not eligible_order_ids:
        return 0, []
    used = (
        db.query(models.ProductRating.order_id)
        .filter(
            models.ProductRating.user_id == user_id,
            models.ProductRating.product_id == product_id,
            models.ProductRating.order_id.in_(eligible_order_ids),
        )
        .distinct()
        .all()
    )
    used_ids = {str(order_id) for (order_id,) in used}
    available_ids = [order_id for order_id in eligible_order_ids if order_id not in used_ids]
    return len(available_ids), available_ids


def _can_comment(db: Session, user_id: int, product_id: int) -> bool:
    return bool(_eligible_order_ids(db, user_id, product_id))


def _comment_sort_clause(sort: str):
    if sort == "time":
        return [models.ProductComment.created_at.desc(), models.ProductComment.id.desc()]

    like_count = func.count(models.ProductCommentLike.id)
    return [like_count.desc(), models.ProductComment.created_at.desc(), models.ProductComment.id.desc()]


def _load_comment_likes(db: Session, comment_ids: List[int], current_user_id: Optional[int]) -> Tuple[Dict[int, int], set[int]]:
    if not comment_ids:
        return {}, set()

    like_rows = (
        db.query(models.ProductCommentLike.comment_id, func.count(models.ProductCommentLike.id))
        .filter(models.ProductCommentLike.comment_id.in_(comment_ids))
        .group_by(models.ProductCommentLike.comment_id)
        .all()
    )
    like_map = {int(comment_id): int(count) for comment_id, count in like_rows}

    liked_by_me: set[int] = set()
    if current_user_id is not None:
        rows = (
            db.query(models.ProductCommentLike.comment_id)
            .filter(
                models.ProductCommentLike.user_id == current_user_id,
                models.ProductCommentLike.comment_id.in_(comment_ids),
            )
            .all()
        )
        liked_by_me = {int(comment_id) for (comment_id,) in rows}

    return like_map, liked_by_me


def _serialize_comments(db: Session, product_id: int, sort: str, current_user_id: Optional[int]) -> List[schemas.ProductCommentOut]:
    root_query = (
        db.query(models.ProductComment)
        .filter(models.ProductComment.product_id == product_id, models.ProductComment.parent_id.is_(None))
        .outerjoin(models.ProductCommentLike, models.ProductCommentLike.comment_id == models.ProductComment.id)
        .group_by(models.ProductComment.id)
        .order_by(*_comment_sort_clause(sort))
    )
    roots = root_query.all()
    root_ids = [comment.id for comment in roots]

    reply_query = (
        db.query(models.ProductComment)
        .filter(models.ProductComment.parent_id.in_(root_ids) if root_ids else False)
        .order_by(models.ProductComment.created_at.asc(), models.ProductComment.id.asc())
    )
    replies = reply_query.all() if root_ids else []

    all_comment_ids = root_ids + [reply.id for reply in replies]
    like_map, liked_by_me = _load_comment_likes(db, all_comment_ids, current_user_id)

    replies_by_parent: Dict[int, List[schemas.ProductCommentReplyOut]] = {}
    for reply in replies:
        replies_by_parent.setdefault(int(reply.parent_id or 0), []).append(
            schemas.ProductCommentReplyOut(
                id=reply.id,
                user_id=reply.user_id,
                user_name=reply.user.full_name,
                product_id=reply.product_id,
                parent_id=int(reply.parent_id or 0),
                content=reply.content,
                created_at=reply.created_at,
                updated_at=reply.updated_at,
                like_count=like_map.get(reply.id, 0),
                liked_by_me=reply.id in liked_by_me,
            )
        )

    return [
        schemas.ProductCommentOut(
            id=comment.id,
            user_id=comment.user_id,
            user_name=comment.user.full_name,
            product_id=comment.product_id,
            parent_id=comment.parent_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            like_count=like_map.get(comment.id, 0),
            liked_by_me=comment.id in liked_by_me,
            replies=replies_by_parent.get(comment.id, []),
        )
        for comment in roots
    ]


def _serialize_summary(db: Session, product_id: int, current_user: Optional[models.User]) -> schemas.ProductReviewSummaryOut:
    rating_rows = db.query(models.ProductRating.rating).filter(models.ProductRating.product_id == product_id).all()
    ratings = [int(rating) for (rating,) in rating_rows]
    average = round(sum(ratings) / len(ratings), 2) if ratings else 0
    comment_count = db.query(func.count(models.ProductComment.id)).filter(models.ProductComment.product_id == product_id, models.ProductComment.parent_id.is_(None)).scalar() or 0

    quota = 0
    can_comment = False
    available_order_ids: List[str] = []
    if current_user:
        quota, available_order_ids = _rating_quota(db, current_user.id, product_id)
        can_comment = _can_comment(db, current_user.id, product_id)

    return schemas.ProductReviewSummaryOut(
        average_rating=float(average),
        rating_count=len(ratings),
        comment_count=int(comment_count),
        my_rating_quota=quota,
        can_comment=can_comment,
        available_rating_orders=available_order_ids,
    )


@router.get("/{product_id}/reviews", response_model=schemas.ProductReviewPageOut)
def list_reviews(
    product_id: int,
    sort: str = Query("likes", pattern="^(likes|time)$"),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_current_user_optional),
):
    _resolve_product(db, product_id)
    return schemas.ProductReviewPageOut(
        summary=_serialize_summary(db, product_id, current_user),
        ratings=[
            schemas.ProductRatingOut(
                id=row.id,
                user_id=row.user_id,
                product_id=row.product_id,
                order_id=row.order_id,
                rating=row.rating,
                created_at=row.created_at,
            )
            for row in db.query(models.ProductRating)
            .filter(models.ProductRating.product_id == product_id)
            .order_by(models.ProductRating.created_at.desc(), models.ProductRating.id.desc())
            .all()
        ],
        comments=_serialize_comments(db, product_id, sort, current_user.id if current_user else None),
    )


@router.post("/{product_id}/ratings", response_model=schemas.ProductRatingOut)
def create_rating(
    product_id: int,
    payload: schemas.RatingCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _resolve_product(db, product_id)
    if payload.rating < 1 or payload.rating > 5:
        raise HTTPException(status_code=400, detail="评分需在 1-5 之间")

    quota, eligible_order_ids = _rating_quota(db, current_user.id, product_id)
    if quota < 1:
        raise HTTPException(status_code=400, detail="该商品暂无可用评分次数")
    if payload.order_id not in eligible_order_ids:
        raise HTTPException(status_code=400, detail="该订单不可用于当前商品评分")

    existed = (
        db.query(models.ProductRating)
        .filter(
            models.ProductRating.user_id == current_user.id,
            models.ProductRating.product_id == product_id,
            models.ProductRating.order_id == payload.order_id,
        )
        .first()
    )
    if existed:
        raise HTTPException(status_code=400, detail="该订单已对该商品评分")

    rating = models.ProductRating(
        user_id=current_user.id,
        product_id=product_id,
        order_id=payload.order_id,
        rating=payload.rating,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


@router.post("/{product_id}/comments", response_model=schemas.ProductCommentOut)
def create_comment(
    product_id: int,
    payload: schemas.CommentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _resolve_product(db, product_id)
    if not _can_comment(db, current_user.id, product_id):
        raise HTTPException(status_code=400, detail="仅限已确认收货用户评论")

    comment = models.ProductComment(
        user_id=current_user.id,
        product_id=product_id,
        content=payload.content.strip(),
    )
    if not comment.content:
        raise HTTPException(status_code=400, detail="评论内容不能为空")
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return schemas.ProductCommentOut(
        id=comment.id,
        user_id=comment.user_id,
        user_name=current_user.full_name,
        product_id=comment.product_id,
        parent_id=None,
        content=comment.content,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
        like_count=0,
        liked_by_me=False,
        replies=[],
    )


@router.post("/{product_id}/comments/{comment_id}/replies", response_model=schemas.ProductCommentReplyOut)
def reply_comment(
    product_id: int,
    comment_id: int,
    payload: schemas.CommentReplyCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _resolve_product(db, product_id)
    if not _can_comment(db, current_user.id, product_id):
        raise HTTPException(status_code=400, detail="仅限已确认收货用户回复评论")

    parent = (
        db.query(models.ProductComment)
        .filter(models.ProductComment.id == comment_id, models.ProductComment.product_id == product_id)
        .first()
    )
    if not parent:
        raise HTTPException(status_code=404, detail="评论不存在")
    if parent.parent_id is not None:
        raise HTTPException(status_code=400, detail="仅支持回复顶层评论")

    reply = models.ProductComment(
        user_id=current_user.id,
        product_id=product_id,
        parent_id=parent.id,
        content=payload.content.strip(),
    )
    if not reply.content:
        raise HTTPException(status_code=400, detail="回复内容不能为空")
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return schemas.ProductCommentReplyOut(
        id=reply.id,
        user_id=reply.user_id,
        user_name=current_user.full_name,
        product_id=reply.product_id,
        parent_id=parent.id,
        content=reply.content,
        created_at=reply.created_at,
        updated_at=reply.updated_at,
        like_count=0,
        liked_by_me=False,
    )


@router.post("/{product_id}/comments/{comment_id}/like", response_model=schemas.Msg)
def like_comment(
    product_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    _resolve_product(db, product_id)
    comment = (
        db.query(models.ProductComment)
        .filter(models.ProductComment.id == comment_id, models.ProductComment.product_id == product_id)
        .first()
    )
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")

    existed = (
        db.query(models.ProductCommentLike)
        .filter(
            models.ProductCommentLike.user_id == current_user.id,
            models.ProductCommentLike.comment_id == comment_id,
        )
        .first()
    )
    if existed:
        raise HTTPException(status_code=400, detail="该评论已点赞")

    db.add(models.ProductCommentLike(user_id=current_user.id, comment_id=comment_id))
    db.commit()
    return schemas.Msg(message="点赞成功")
