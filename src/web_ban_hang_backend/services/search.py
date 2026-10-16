import logging
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from PIL import Image
from sqlmodel import select, func

from web_ban_hang_backend.models.product import Product
from web_ban_hang_backend.models.product_image import ProductImage
from web_ban_hang_backend.services.embedding import embed_clip_text, embed_image, embed_text

logger = logging.getLogger(__name__)


def rrf(rankings: List[List[UUID]], k: int = 60) -> List[UUID]:
    scores: dict[UUID, float] = {}

    for ranking in rankings:
        seen: set[UUID] = set()

        for rank, pid in enumerate(ranking, start=1):
            if pid in seen:
                continue

            seen.add(pid)
            scores[pid] = scores.get(pid, 0.0) + 1.0 / (k + rank)

    return sorted(
        scores,
        key=lambda pid: scores[pid],
        reverse=True,
    )


def execute_hybrid_search(
    session,
    model_state,
    q: Optional[str],
    image: Optional[Image.Image],
    category_id: Optional[int],
    min_price: Optional[Decimal],
    max_price: Optional[Decimal],
) -> List[UUID]:
    rankings: List[List[UUID]] = []

    product_filters = [Product.is_active.is_(True)]

    if category_id is not None:
        product_filters.append(Product.category_id == category_id)

    if min_price is not None:
        product_filters.append(Product.price >= min_price)

    if max_price is not None:
        product_filters.append(Product.price <= max_price)

    query = q.strip() if q else ""
    model_ready = getattr(model_state, "ready", False)

    if image is not None and model_ready:
        try:
            vec_img = embed_image(model_state, image)
        except Exception:
            logger.exception("Image search failed")
            raise

        stmt = (
            select(ProductImage.product_id)
            .join(Product)
            .where(
                *product_filters,
                ProductImage.multimodal_embedding.is_not(None),
            )
            .group_by(ProductImage.product_id)
            .order_by(
                func.min(
                    ProductImage.multimodal_embedding.cosine_distance(vec_img)
                ).asc()
            )
            .limit(50)
        )
        rankings.append(session.exec(stmt).all())

    if query:
        if model_ready:
            try:
                vec_clip_text = embed_clip_text(model_state, query)
            except Exception:
                logger.exception("Multimodal text search failed")
            else:
                stmt = (
                    select(ProductImage.product_id)
                    .join(Product)
                    .where(
                        *product_filters,
                        ProductImage.multimodal_embedding.is_not(None),
                    )
                    .group_by(ProductImage.product_id)
                    .order_by(
                        func.min(
                            ProductImage.multimodal_embedding.cosine_distance(
                                vec_clip_text
                            )
                        ).asc()
                    )
                    .limit(50)
                )
                rankings.append(session.exec(stmt).all())

            try:
                vec_bge_text = embed_text(model_state, query)
            except Exception:
                logger.exception("Semantic text search failed")
            else:
                stmt = (
                    select(Product.id)
                    .where(
                        *product_filters,
                        Product.semantic_embedding.is_not(None),
                    )
                    .order_by(
                        Product.semantic_embedding.cosine_distance(vec_bge_text).asc()
                    )
                    .limit(50)
                )
                rankings.append(session.exec(stmt).all())

        ts_query = func.websearch_to_tsquery(query)
        stmt = (
            select(Product.id)
            .where(
                *product_filters,
                Product.search_vector.op("@@")(ts_query),
            )
            .order_by(
                func.ts_rank_cd(Product.search_vector, ts_query).desc()
            )
            .limit(50)
        )
        rankings.append(session.exec(stmt).all())

    fused_product_ids = rrf(rankings)

    return fused_product_ids[:100]
