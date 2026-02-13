from pathlib import Path

from django.conf import settings
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Event, Photo
from .utils import generate_event_qr_code, get_event_qr_paths
from .widgets import ColorPickerWidget


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "start_time", "end_time")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    readonly_fields = ("qr_code_preview",)
    actions = ("generate_qr_codes",)
    
    # Color fields that should use the color picker widget
    COLOR_FIELDS = [
        'bg_color_1', 'bg_color_2', 'bg_color_3',
        'primary_color', 'accent_color_1', 'accent_color_2',
        'text_primary_color', 'text_muted_color',
    ]
    
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        """
        Override to use ColorPickerWidget for color fields.
        """
        if db_field.name in self.COLOR_FIELDS:
            kwargs['widget'] = ColorPickerWidget()
        return super().formfield_for_dbfield(db_field, request, **kwargs)
    
    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "slug", "is_active")
        }),
        ("Personalization", {
            "fields": (
                "couple_names",
                "upload_page_subtitle",
                ("bg_color_1", "bg_color_2", "bg_color_3"),
                ("primary_color", "accent_color_1", "accent_color_2"),
                ("text_primary_color", "text_muted_color"),
            ),
            "description": "Customize the appearance of the upload page. Leave colors blank to use default wedding theme. Use hex color codes (e.g., #ffe6f7)."
        }),
        ("Timing", {
            "fields": ("start_time", "end_time")
        }),
        ("QR Code", {
            "fields": ("qr_code_preview",)
        }),
    )

    def qr_code_preview(self, obj):
        if not obj or not obj.slug:
            return "Save the event to generate a QR code."

        _, qr_url = get_event_qr_paths(obj.slug)
        qr_file = Path(settings.MEDIA_ROOT) / "qrcodes" / f"{obj.slug}.png"

        if not qr_file.exists():
            return format_html(
                "No QR code generated yet. Use the “Generate QR code for selected events” admin action."
            )

        upload_url = f"{settings.EVENT_BASE_URL.rstrip('/')}{obj.get_absolute_url()}"

        return format_html(
            '<div style="display:flex; flex-direction:column; gap:0.75rem;">'
            '<img src="{}" alt="QR code" style="max-width:220px; border:1px solid #ddd; padding:6px; border-radius:8px;">'
            '<a href="{}" target="_blank" rel="noopener">Download QR code</a>'
            '<div style="font-size:0.9rem; color:#555;">'
            '<div>Guest upload link:</div>'
            '<code style="display:inline-block; padding:4px 6px; margin-top:4px; background:#f7f7f7; border-radius:4px;">{}</code>'
            '</div>'
            "</div>",
            qr_url,
            qr_url,
            upload_url,
        )

    qr_code_preview.short_description = "Event QR code"

    def generate_qr_codes(self, request, queryset):
        generated = 0
        skipped = 0
        for event in queryset:
            try:
                generate_event_qr_code(event)
                generated += 1
            except Exception as exc:  # pragma: no cover - defensive
                skipped += 1
                self.message_user(
                    request,
                    f"Failed to generate QR for '{event}': {exc}",
                    level=messages.ERROR,
                )
        if generated:
            self.message_user(
                request,
                f"Generated QR codes for {generated} event(s).",
                level=messages.SUCCESS,
            )
        if skipped and not generated:
            self.message_user(request, "No QR codes generated.", level=messages.WARNING)

    generate_qr_codes.short_description = "Generate QR code for selected events"


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("event", "uploaded_at", "short_comment", "thumbnail")
    list_filter = ("event", "uploaded_at")
    search_fields = ("event__name", "comment")
    readonly_fields = ("uploaded_at", "uploader_ip", "preview")
    fields = (
        "event",
        "image",
        "preview",
        "comment",
        "uploaded_at",
        "uploader_ip",
    )

    def short_comment(self, obj):
        if not obj.comment:
            return ""
        return (obj.comment[:40] + "…") if len(obj.comment) > 40 else obj.comment

    short_comment.short_description = "Comment"

    def thumbnail(self, obj):
        if not obj.image:
            return "—"
        return format_html(
            '<img src="{}" style="max-height: 60px; max-width: 60px; border-radius: 6px;" alt="thumbnail" />',
            obj.image.url,
        )

    thumbnail.short_description = "Preview"
    thumbnail.allow_tags = True

    def preview(self, obj):
        if not obj.image:
            return "No image uploaded."
        return format_html(
            '<img src="{}" style="max-width: 320px; border-radius: 12px;" alt="preview" />',
            obj.image.url,
        )

    preview.short_description = "Image preview"
