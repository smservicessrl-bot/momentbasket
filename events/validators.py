from __future__ import annotations

import os
from typing import Iterable

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

DEFAULT_MAX_UPLOAD_SIZE = 15 * 1024 * 1024  # 15 MB
DEFAULT_ALLOWED_CONTENT_TYPES: Iterable[str] = (
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/heif",
    "image/heic-sequence",
    "image/heif-sequence",
)

DEFAULT_ALLOWED_EXTENSIONS: Iterable[str] = (
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".heif",
)


def validate_photo_image(value):
    max_size = getattr(settings, "PHOTO_MAX_UPLOAD_SIZE", DEFAULT_MAX_UPLOAD_SIZE)
    allowed_types = getattr(
        settings, "PHOTO_ALLOWED_CONTENT_TYPES", DEFAULT_ALLOWED_CONTENT_TYPES
    )
    allowed_exts = tuple(
        getattr(settings, "PHOTO_ALLOWED_EXTENSIONS", DEFAULT_ALLOWED_EXTENSIONS)
    )

    content_type = getattr(value, "content_type", "") or ""
    if content_type:
        normalized_content_type = content_type.split(";")[0].strip().lower()
        allowed_normalized = [ct.lower() for ct in allowed_types]
    else:
        normalized_content_type = ""
        allowed_normalized = [ct.lower() for ct in allowed_types]

    name = getattr(value, "name", "")
    extension = os.path.splitext(name)[1].lower()
    allowed_exts_lower = [ext.lower() for ext in allowed_exts]

    is_allowed_type = (
        normalized_content_type in allowed_normalized
        if normalized_content_type
        else False
    )
    is_allowed_extension = extension in allowed_exts_lower

    if not (is_allowed_type or is_allowed_extension):
        allowed_display = sorted(set(allowed_types) | set(allowed_exts))
        raise ValidationError(
            _("Unsupported image type. Please upload one of: %(types)s."),
            params={"types": ", ".join(allowed_display)},
        )

    file_size = getattr(value, "size", None)
    if file_size and file_size > int(max_size):
        readable_limit = round(max_size / (1024 * 1024), 1)
        raise ValidationError(
            _("Image file is too large (max %(size)s MB)."),
            params={"size": readable_limit},
        )

    return value

