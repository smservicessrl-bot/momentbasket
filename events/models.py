import os
import secrets
import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from .validators import validate_photo_image


def event_photo_upload_to(instance, filename: str) -> str:
    """
    Store uploaded images grouped by event slug.
    Example: photos/my-event/unique-image-name.jpg
    """
    base, ext = os.path.splitext(filename)
    ext = ext.lower()
    sanitized_name = base.replace(" ", "_")
    event_slug = instance.event.slug if instance.event_id else "unsorted"
    return str(Path("photos") / event_slug / f"{sanitized_name}{ext}")


class Event(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    start_time = models.DateTimeField(blank=True, null=True)
    end_time = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    
    # Personalization fields
    couple_names = models.CharField(max_length=200, blank=True, help_text="E.g., 'John & Jane', 'The Smiths', or any format")
    upload_page_subtitle = models.TextField(blank=True, help_text="Subtitle message displayed on the upload page (e.g., 'Ossz meg egy különleges pillanatot az ifjú párral.')")
    bg_color_1 = models.CharField(max_length=7, blank=True, help_text="Background gradient color 1 (hex code, e.g., #ffe6f7)")
    bg_color_2 = models.CharField(max_length=7, blank=True, help_text="Background gradient color 2 (hex code, e.g., #d3f4ff)")
    bg_color_3 = models.CharField(max_length=7, blank=True, help_text="Background gradient color 3 (hex code, e.g., #ffe7d2)")
    primary_color = models.CharField(max_length=7, blank=True, help_text="Primary color for text (hex code, e.g., #2b2d42)")
    accent_color_1 = models.CharField(max_length=7, blank=True, help_text="Accent gradient color 1 (hex code, e.g., #7f5cff)")
    accent_color_2 = models.CharField(max_length=7, blank=True, help_text="Accent gradient color 2 (hex code, e.g., #ff89b3)")
    text_primary_color = models.CharField(max_length=7, blank=True, help_text="Primary text color (hex code, e.g., #2b2d42)")
    text_muted_color = models.CharField(max_length=7, blank=True, help_text="Muted text color (hex code, e.g., #6c7286)")
    gallery_uid = models.CharField(max_length=8, blank=True, db_index=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse("events:event-upload", kwargs={"slug": self.slug})
    
    def get_theme_colors(self) -> dict:
        """
        Returns a dictionary of theme colors, using defaults if custom colors are not set.
        Defaults match the main website/demo palette (Momentbasket brand).
        """
        return {
            "bg_color_1": self.bg_color_1 or "#f9e0ff",
            "bg_color_2": self.bg_color_2 or "#c8f5ff",
            "bg_color_3": self.bg_color_3 or "#ffe4d6",
            "primary_color": self.primary_color or "#2b2d42",
            "accent_color_1": self.accent_color_1 or "#7254ff",
            "accent_color_2": self.accent_color_2 or "#ff7ca3",
            "text_primary_color": self.text_primary_color or "#2b2d42",
            "text_muted_color": self.text_muted_color or "#6c7286",
        }

    def save(self, *args, **kwargs):
        if not self.gallery_uid:
            self.gallery_uid = uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)


class UploadChannel(models.Model):
    """
    Stable upload entry (QR / link) for a venue, photographer, or designer.
    The public URL uses `slug` and `upload_uid`, not the event name.
    Point `current_event` at whichever event should receive uploads from this link.
    """

    slug = models.SlugField(max_length=100, unique=True)
    label = models.CharField(
        max_length=255,
        help_text="Venue, photographer, or designer (admin only; not used in the public upload URL).",
    )
    upload_uid = models.CharField(max_length=8, unique=True, db_index=True, editable=False)
    current_event = models.ForeignKey(
        Event,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="upload_channels_as_current",
    )

    class Meta:
        ordering = ("label",)

    def __str__(self) -> str:
        return f"{self.label} ({self.slug})"

    def save(self, *args, **kwargs):
        if not self.upload_uid:
            self.upload_uid = f"{secrets.randbelow(100_000_000):08d}"
        demo_slug = str(getattr(settings, "DEMO_CHANNEL_SLUG", ""))
        if demo_slug and self.slug == demo_slug:
            self.upload_uid = str(getattr(settings, "DEMO_EVENT_FIXED_UID", "12345678"))
        super().save(*args, **kwargs)


class Photo(models.Model):
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(
        upload_to=event_photo_upload_to,
        validators=[validate_photo_image],
    )
    comment = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploader_ip = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        ordering = ("-uploaded_at",)

    def __str__(self) -> str:
        return f"Photo for {self.event.name} @ {self.uploaded_at:%Y-%m-%d %H:%M:%S}"
