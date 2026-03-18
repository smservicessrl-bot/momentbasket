from __future__ import annotations

import json
import secrets
from pathlib import Path

from django.conf import settings
from django.urls import reverse


def get_event_qr_paths(event_slug: str) -> tuple[Path, str]:
    relative_path = Path("qrcodes") / f"{event_slug}.png"
    media_file = Path(settings.MEDIA_ROOT) / relative_path
    media_url = f"{settings.MEDIA_URL}{relative_path.as_posix()}"
    return media_file, media_url


def get_event_qr_metadata_path(event_slug: str) -> Path:
    """
    Sidecar JSON file that stores the short UID and the exact target URL
    embedded into the QR code.
    """
    relative_path = Path("qrcodes") / f"{event_slug}.json"
    return Path(settings.MEDIA_ROOT) / relative_path


def read_event_qr_metadata(event_slug: str) -> dict[str, str] | None:
    metadata_path = get_event_qr_metadata_path(event_slug)
    try:
        raw = metadata_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            # Ensure keys we expect are present.
            if "uid" in data and "target_url" in data:
                return {"uid": str(data["uid"]), "target_url": str(data["target_url"])}
    except FileNotFoundError:
        return None
    except Exception:
        return None

    return None


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
    # Short UID (8 digits) to keep the embedded link compact.
    # This is generated randomly; collisions are unlikely for typical event usage.
    qr_uid = f"{secrets.randbelow(100_000_000):08d}"
    qr_target_url = f"{base_url}{upload_path}?uid={qr_uid}"

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

    # Persist UID + exact target URL for the admin preview.
    metadata_path = get_event_qr_metadata_path(event.slug)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps({"uid": qr_uid, "target_url": qr_target_url}, ensure_ascii=False),
        encoding="utf-8",
    )
    return qr_image_path


#
# Base URL for QR code generation comes from `settings.EVENT_BASE_URL`.
# To use localhost on Raspberry/offline deployments, set `EVENT_BASE_URL`
# accordingly in the Raspberry environment.

