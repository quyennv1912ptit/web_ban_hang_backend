from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
ALLOWED_IMAGE_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


class ImageValidationError(ValueError):
    pass


class UnsupportedImageFormat(ImageValidationError):
    pass


class ImageTooLarge(ImageValidationError):
    pass


def decode_image_bytes(data: bytes) -> Image.Image:
    if not data:
        raise ImageValidationError("File rỗng")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLarge("Ảnh vượt quá 10 MB")

    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in ALLOWED_IMAGE_FORMATS:
                raise UnsupportedImageFormat("Chỉ chấp nhận ảnh JPEG, PNG hoặc WEBP")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ImageTooLarge("Ảnh vượt quá 40 triệu điểm ảnh")
            image.load()
            return ImageOps.exif_transpose(image).convert("RGB")
    except ImageValidationError:
        raise
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
        SyntaxError,
    ) as exc:
        raise ImageValidationError("File không phải ảnh hợp lệ hoặc bị hỏng") from exc
