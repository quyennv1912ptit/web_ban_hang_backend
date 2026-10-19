import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import Engine, update
from sqlmodel import Session, select

from web_ban_hang_backend.core.model_state import load_models
from web_ban_hang_backend.models.product import TEXT_EMBED_DIM, Product
from web_ban_hang_backend.models.product_image import IMAGE_EMBED_DIM, ProductImage
from web_ban_hang_backend.services.embedding import embed_image, embed_text
from web_ban_hang_backend.services.image_utils import decode_image_bytes

logger = logging.getLogger(__name__)

TEXT_EMBEDDING_MODEL = f"BGE-m3@{TEXT_EMBED_DIM}"
IMAGE_EMBEDDING_MODEL = f"jina-clip-v2@{IMAGE_EMBED_DIM}"

PENDING = "pending"  # chờ: model chưa sẵn sàng, worker sẽ tự thử lại
INDEXED = "indexed"  # xong
FAILED = "failed"    # lỗi khi encode, cần admin bấm retry


def build_embedding_text(name: str, desc: str | None, attr: dict[str, Any]) -> str:
    parts = [f"Tên: {name}"]
    if desc:
        parts.append(f"Mô tả: {desc}")
    for key in sorted(attr):
        val = attr[key]
        if val in (None, "", [], {}):
            continue
        if isinstance(val, (list, tuple)):
            val = ", ".join(str(v) for v in val)
        parts.append(f"{key}: {val}")
    return "\n".join(parts)


def refresh_text_embedding(product: Product, model_state) -> None:
    """Cập nhật embedding nếu nội dung đổi và luôn ghi lại embedding_status."""
    text = build_embedding_text(product.name, product.description, product.attributes)
    new_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    if (
        product.semantic_embedding is not None
        and product.embedding_text_hash == new_hash
        and product.embedding_model == TEXT_EMBEDDING_MODEL
    ):
        product.embedding_status = INDEXED
        product.embedding_error = None
        return

    if model_state is None or not model_state.ready:
        product.embedding_status = PENDING
        return

    try:
        vector = embed_text(model_state, text)
        if len(vector) != TEXT_EMBED_DIM:
            raise ValueError(f"Vector {len(vector)} chiều, cột trong DB cần {TEXT_EMBED_DIM} chiều")
    except Exception as exc:
        logger.exception("Không tạo được text embedding cho sản phẩm %s", product.slug)
        product.embedding_status = FAILED
        product.embedding_error = str(exc)[:500]
        return

    product.semantic_embedding = vector
    product.embedding_model = TEXT_EMBEDDING_MODEL
    product.embedding_text_hash = new_hash
    product.embedding_updated_at = datetime.now(timezone.utc)
    product.embedding_status = INDEXED
    product.embedding_error = None


def backfill_products(engine: Engine, model_state, batch_size: int = 20) -> int:
    """Encode bù một lô sản phẩm pending. Trả về số bản ghi đã xử lý."""
    if model_state is None or not model_state.ready:
        return 0
    with Session(engine) as session:
        products = session.exec(
            select(Product)
            .where(Product.embedding_status == PENDING)
            .order_by(Product.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        for product in products:
            refresh_text_embedding(product, model_state)
            session.add(product)
        session.commit()
        return len(products)


def backfill_images(engine: Engine, model_state, batch_size: int = 10) -> int:
    """Tải lại ảnh từ cloud rồi encode bù cho các ảnh pending."""
    if model_state is None or not model_state.ready:
        return 0
    with Session(engine) as session:
        rows = session.exec(
            select(ProductImage)
            .where(ProductImage.embedding_status == PENDING)
            .order_by(ProductImage.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            try:
                resp = httpx.get(row.image_url, timeout=15, follow_redirects=True)
                resp.raise_for_status()
                vector = embed_image(model_state, decode_image_bytes(resp.content))
                if len(vector) != IMAGE_EMBED_DIM:
                    raise ValueError(f"Vector {len(vector)} chiều, cột DB cần {IMAGE_EMBED_DIM}")
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                reason = exc.response.reason_phrase
                logger.warning(
                    "Encode bù ảnh %s thất bại: tải ảnh trả HTTP %s %s",
                    row.id,
                    status_code,
                    reason,
                )
                row.embedding_status = FAILED
                row.embedding_error = f"Không tải được ảnh (HTTP {status_code} {reason})"[:500]
            except Exception as exc:
                logger.exception("Encode bù ảnh %s thất bại", row.id)
                row.embedding_status = FAILED
                row.embedding_error = str(exc)[:500]
            else:
                row.multimodal_embedding = vector
                row.embedding_model = IMAGE_EMBEDDING_MODEL
                row.embedding_status = INDEXED
                row.embedding_error = None
                row.indexed_at = datetime.now(timezone.utc)
            session.add(row)
        session.commit()
        return len(rows)


def retry_failed(session: Session) -> dict[str, int]:
    """Đưa các bản ghi failed về pending để worker xử lý lại."""
    result = {}
    for name, model in (("products", Product), ("images", ProductImage)):
        res = session.execute(
            update(model)
            .where(model.embedding_status == FAILED)
            .values(embedding_status=PENDING, embedding_error=None)
        )
        result[name] = res.rowcount
    session.commit()
    return result


async def embedding_worker(
    app: Any,
    engine: Engine,
    interval: float = 30.0,
    model_retry_interval: float = 120.0,
) -> None:
    """
    - Nếu model đang là None (lúc khởi động nạp lỗi) thì thử nạp lại.
    - Có model thì quét bản ghi pending: còn việc làm tiếp ngay, hết việc thì nghỉ.
    """
    while True:
        delay = interval
        try:
            if app.state.model_state is None:
                logger.info("Thử nạp lại model tìm kiếm")
                app.state.model_state = await asyncio.to_thread(load_models)
                logger.info("Đã nạp lại model thành công")

            model_state = app.state.model_state
            processed = await asyncio.to_thread(backfill_products, engine, model_state)
            processed += await asyncio.to_thread(backfill_images, engine, model_state)
            if processed:
                delay = 2.0
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Embedding worker gặp lỗi, sẽ thử lại ở lượt sau")
            if app.state.model_state is None:
                delay = model_retry_interval
        await asyncio.sleep(delay)
