from __future__ import annotations

import json
import secrets
from pathlib import Path

from django.conf import settings
from django.urls import reverse

from .models import Event, UploadChannel


def channel_uid_is_valid(channel: UploadChannel, uid: str | None) -> bool:
    if not uid:
        return False
    if uid == channel.upload_uid:
        return True
    demo_channel_slug = str(getattr(settings, "DEMO_CHANNEL_SLUG", ""))
    demo_uid = str(getattr(settings, "DEMO_EVENT_FIXED_UID", "12345678"))
    if demo_channel_slug and channel.slug == demo_channel_slug and uid == demo_uid:
        return True
    return False


def get_event_qr_paths(event_slug: str) -> tuple[Path, str]:
    relative_path = Path("qrcodes") / f"{event_slug}.png"
    media_file = Path(settings.MEDIA_ROOT) / relative_path
    media_url = f"{settings.MEDIA_URL}{relative_path.as_posix()}"
    return media_file, media_url


def get_upload_channel_qr_paths(channel_slug: str) -> tuple[Path, str]:
    relative_path = Path("qrcodes") / f"ch_{channel_slug}.png"
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


def get_upload_channel_qr_metadata_path(channel_slug: str) -> Path:
    relative_path = Path("qrcodes") / f"ch_{channel_slug}.json"
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


def read_upload_channel_qr_metadata(channel_slug: str) -> dict[str, str] | None:
    metadata_path = get_upload_channel_qr_metadata_path(channel_slug)
    try:
        raw = metadata_path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            if "uid" in data and "target_url" in data:
                return {"uid": str(data["uid"]), "target_url": str(data["target_url"])}
    except FileNotFoundError:
        return None
    except Exception:
        return None

    return None


def _normalize_qr_base_url(base_url: str | None) -> str:
    base_url = (base_url or settings.EVENT_BASE_URL).rstrip("/")
    if not base_url:
        raise ValueError("EVENT_BASE_URL must be configured.")

    base_url_lower = base_url.lower()
    is_localhostish = base_url_lower.startswith("http://localhost") or base_url_lower.startswith(
        "http://127.0.0.1"
    ) or base_url_lower.startswith("https://localhost") or base_url_lower.startswith("http://0.0.0.0")

    if is_localhostish and not settings.MOMENTBASKET_QR_USE_LOCALHOST:
        base_url = "https://momentbasket.ro"

    return base_url


def generate_upload_channel_qr_code(
    channel: UploadChannel,
    base_url: str | None = None,
) -> Path:
    """Write QR image + metadata for a reusable upload channel (venue / photographer / designer)."""
    try:
        import qrcode
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "qrcode library is not installed. Install it with 'pip install qrcode[pil]'."
        ) from exc

    base_url = _normalize_qr_base_url(base_url)
    qr_uid = channel.upload_uid

    upload_path = reverse("events:channel-upload", kwargs={"channel_slug": channel.slug})
    qr_target_url = f"{base_url}{upload_path}?uid={qr_uid}"

    qr_image_path, _ = get_upload_channel_qr_paths(channel.slug)
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

    metadata_path = get_upload_channel_qr_metadata_path(channel.slug)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps({"uid": qr_uid, "target_url": qr_target_url}, ensure_ascii=False),
        encoding="utf-8",
    )
    return qr_image_path


def generate_event_qr_code(event: Event, base_url: str | None = None) -> Path | None:
    """
    If this event is the `current_event` of any UploadChannel, regenerate QR file(s)
    for those channels (stable URL, reusable across events).

    Otherwise generate the legacy per-event-slug QR (random uid each time).
    """
    channels = UploadChannel.objects.filter(current_event=event)
    if channels.exists():
        last: Path | None = None
        for channel in channels:
            last = generate_upload_channel_qr_code(channel, base_url=base_url)
        return last

    try:
        import qrcode
    except ImportError as exc:  # pragma: no cover - import guard
        raise RuntimeError(
            "qrcode library is not installed. Install it with 'pip install qrcode[pil]'."
        ) from exc

    base_url = _normalize_qr_base_url(base_url)

    upload_path = reverse("events:event-upload", kwargs={"slug": event.slug})
    demo_event_slug = str(getattr(settings, "DEMO_EVENT_SLUG", "bemutato-esemeny"))
    demo_event_fixed_uid = str(getattr(settings, "DEMO_EVENT_FIXED_UID", "12345678"))
    if event.slug == demo_event_slug:
        qr_uid = demo_event_fixed_uid
    else:
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

    metadata_path = get_event_qr_metadata_path(event.slug)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps({"uid": qr_uid, "target_url": qr_target_url}, ensure_ascii=False),
        encoding="utf-8",
    )
    return qr_image_path


def qr_preview_payload_for_event(event: Event) -> dict | None:
    """
    Prefer channel-based QR when this event is a channel's current_event; else legacy file on disk.
    Returns dict: kind, image_url, download_url, target_url, channel_label (optional).
    """
    channel = (
        UploadChannel.objects.filter(current_event=event).order_by("label").first()
    )
    if channel:
        _, qr_url = get_upload_channel_qr_paths(channel.slug)
        qr_file = Path(settings.MEDIA_ROOT) / "qrcodes" / f"ch_{channel.slug}.png"
        if not qr_file.exists():
            return None
        metadata = read_upload_channel_qr_metadata(channel.slug) or {}
        upload_url = metadata.get("target_url") or ""
        return {
            "kind": "channel",
            "image_url": qr_url,
            "download_url": qr_url,
            "target_url": upload_url,
            "channel_label": channel.label,
            "channel_slug": channel.slug,
        }

    if not event.slug:
        return None
    _, qr_url = get_event_qr_paths(event.slug)
    qr_file = Path(settings.MEDIA_ROOT) / "qrcodes" / f"{event.slug}.png"
    if not qr_file.exists():
        return None
    metadata = read_event_qr_metadata(event.slug) or {}
    upload_url = metadata.get("target_url") or f"{settings.EVENT_BASE_URL.rstrip('/')}{event.get_absolute_url()}"
    return {
        "kind": "legacy",
        "image_url": qr_url,
        "download_url": qr_url,
        "target_url": upload_url,
    }


#
# Base URL for QR code generation comes from `settings.EVENT_BASE_URL`.
# To use localhost on Raspberry/offline deployments, set `EVENT_BASE_URL`
# accordingly in the Raspberry environment.
