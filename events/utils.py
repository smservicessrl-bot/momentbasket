from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.urls import reverse


def get_event_qr_paths(event_slug: str) -> tuple[Path, str]:
    relative_path = Path("qrcodes") / f"{event_slug}.png"
    media_file = Path(settings.MEDIA_ROOT) / relative_path
    media_url = f"{settings.MEDIA_URL}{relative_path.as_posix()}"
    return media_file, media_url


def generate_event_qr_code(event, base_url: str | None = None) -> Path:
    try:
        import qrcode
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "qrcode library is not installed. Install it with 'pip install qrcode[pil]'."
        ) from exc

    base_url = (base_url or settings.EVENT_BASE_URL).rstrip("/")
    if not base_url:
        raise ValueError("EVENT_BASE_URL must be configured.")

    upload_path = reverse("events:event-upload", kwargs={"slug": event.slug})
    qr_target_url = f"{base_url}{upload_path}"

    qr_image_path, _ = get_event_qr_paths(event.slug)
    qr_image_path.parent.mkdir(parents=True, exist_ok=True)

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_target_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(qr_image_path)
    return qr_image_path

