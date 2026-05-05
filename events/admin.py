import csv
import json
import os
import re
import zipfile
from io import StringIO
from pathlib import PurePosixPath
from django.conf import settings
from django.contrib import admin, messages
from django.core.files.base import ContentFile
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html

from .models import Event, Photo, UploadChannel
from .utils import generate_event_qr_code, qr_preview_payload_for_event
from .validators import DEFAULT_ALLOWED_EXTENSIONS
from .widgets import ColorPickerWidget


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "start_time", "end_time")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)
    readonly_fields = (
        "qr_code_preview",
        "customer_gallery_url",
        "download_event_data_button",
        "import_gallery_button",
    )
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
        ("Customer Gallery", {
            "fields": ("customer_gallery_url",)
        }),
        ("Downloads", {
            "fields": ("download_event_data_button", "import_gallery_button")
        }),
    )

    def qr_code_preview(self, obj):
        if not obj or not obj.slug:
            return "Save the event to generate a QR code."

        payload = qr_preview_payload_for_event(obj)
        if not payload:
            return format_html(
                "No QR code yet. Either assign this event as the <strong>current event</strong> on an "
                "<a href=\"/admin/events/uploadchannel/\">Upload channel</a>, then generate the QR, "
                "or use the legacy “Generate QR code for selected events” action (slug-based link)."
            )

        extra = ""
        if payload.get("kind") == "channel":
            extra = format_html(
                '<p style="font-size:0.85rem;color:#666;margin-top:0.5rem;">'
                "Reusable upload channel: <strong>{}</strong>. The same printed QR works for future events "
                "when you point the channel’s current event to a new one."
                "</p>",
                payload.get("channel_label", ""),
            )

        return format_html(
            '<div style="display:flex; flex-direction:column; gap:0.75rem;">'
            '<img src="{}" alt="QR code" style="max-width:220px; border:1px solid #ddd; padding:6px; border-radius:8px;">'
            '<a href="{}" target="_blank" rel="noopener">Download QR code</a>'
            '<div style="font-size:0.9rem; color:#555;">'
            '<div>Guest upload link:</div>'
            '<code style="display:inline-block; padding:4px 6px; margin-top:4px; background:#f7f7f7; border-radius:4px;">{}</code>'
            '</div>'
            "{}"
            "</div>",
            payload["image_url"],
            payload["download_url"],
            payload["target_url"],
            extra,
        )

    qr_code_preview.short_description = "Event QR code"

    def customer_gallery_url(self, obj):
        if not obj or not obj.slug:
            return "Save the event to generate the gallery URL."

        gallery_uid = obj.gallery_uid or ""
        gallery_path = reverse(
            "events:customer-gallery",
            kwargs={"slug": obj.slug, "uid": gallery_uid},
        )
        absolute_gallery_url = f"{settings.EVENT_BASE_URL.rstrip('/')}{gallery_path}"
        return format_html(
            '<a href="{0}" target="_blank" rel="noopener">{0}</a>',
            absolute_gallery_url,
        )

    customer_gallery_url.short_description = "Customer gallery URL"

    def download_event_data_button(self, obj):
        if not obj or not obj.pk:
            return "Save the event before downloading photos and comments."

        return format_html(
            '<a class="button" href="{}">Download all photos & comments</a>',
            reverse("events:admin-download-event-data", args=[obj.pk]),
        )

    download_event_data_button.short_description = "Event export"

    def import_gallery_button(self, obj):
        if not obj or not obj.pk:
            return "Save the event before importing an offline gallery ZIP."

        return format_html(
            '<a class="button" href="{}">Import offline gallery ZIP</a>',
            reverse("admin:events_event_import_gallery", args=[obj.pk]),
        )

    import_gallery_button.short_description = "Offline import"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/import-gallery/",
                self.admin_site.admin_view(self.import_gallery_view),
                name="events_event_import_gallery",
            ),
        ]
        return custom_urls + urls

    @staticmethod
    def _extract_importable_photo_entries(
        archive: zipfile.ZipFile,
    ) -> list[tuple[str, str, int | None]]:
        """
        Return photo entries from any nested .../photos/ path.
        Tuple values are (member_name, original_filename_for_comment_lookup, export_index).
        """
        allowed_exts = {ext.lower() for ext in DEFAULT_ALLOWED_EXTENSIONS}
        entries: list[tuple[str, str, int | None]] = []

        for name in archive.namelist():
            if name.endswith("/"):
                continue

            parts = PurePosixPath(name).parts
            lowered_parts = [part.lower() for part in parts]
            has_photos_segment = "photos" in lowered_parts

            if has_photos_segment:
                photos_idx = lowered_parts.index("photos")
                if photos_idx == len(parts) - 1:
                    continue

            member_filename = parts[-1]
            # Skip hidden/system helper files often added by OS zip tools.
            if member_filename.startswith(".") or member_filename.startswith("._"):
                continue

            _, ext = os.path.splitext(member_filename.lower())
            if ext not in allowed_exts:
                continue

            match = re.match(r"^(\d+)_(.+)$", member_filename)
            if match:
                export_index = int(match.group(1))
                filename_for_comment = match.group(2)
            else:
                export_index = None
                filename_for_comment = member_filename
            entries.append((name, filename_for_comment, export_index))

        return entries

    @staticmethod
    def _normalize_name(name: str) -> str:
        return os.path.basename((name or "").strip()).lower()

    @staticmethod
    def _find_comments_csv_member(archive: zipfile.ZipFile) -> str | None:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            if os.path.basename(name).lower() == "comments.csv":
                return name
        return None

    @staticmethod
    def _find_metadata_member(archive: zipfile.ZipFile) -> str | None:
        for name in archive.namelist():
            if name.endswith("/"):
                continue
            if os.path.basename(name).lower() == "metadata.json":
                return name
        return None

    def import_gallery_view(self, request, object_id):
        event = self.get_object(request, object_id)
        if event is None:
            self.message_user(request, "Event not found.", level=messages.ERROR)
            return HttpResponseRedirect(reverse("admin:events_event_changelist"))

        if request.method == "POST":
            gallery_zip = request.FILES.get("gallery_zip")
            if not gallery_zip:
                self.message_user(request, "Please choose a ZIP file to import.", level=messages.ERROR)
                return HttpResponseRedirect(
                    reverse("admin:events_event_import_gallery", args=[event.pk])
                )

            imported_count = 0
            skipped_count = 0

            try:
                with zipfile.ZipFile(gallery_zip) as archive:
                    comments_by_filename = {}
                    comments_by_number = {}
                    comments_member = self._find_comments_csv_member(archive)
                    if comments_member:
                        comments_csv = archive.read(comments_member).decode("utf-8-sig", errors="replace")
                        delimiter = ","
                        try:
                            delimiter = csv.Sniffer().sniff(comments_csv[:4096], delimiters=",;|\t").delimiter
                        except Exception:
                            pass
                        reader = csv.DictReader(StringIO(comments_csv), delimiter=delimiter)
                        for row in reader:
                            row = {str(k or "").strip().lower(): v for k, v in row.items()}
                            filename = (
                                (row.get("filename") or row.get("file") or row.get("image") or "").strip()
                            )
                            comment = (row.get("comment") or row.get("caption") or "").strip()
                            number_raw = (row.get("photo number") or row.get("number") or "").strip()
                            if filename:
                                comments_by_filename[self._normalize_name(filename)] = comment
                            if number_raw.isdigit():
                                comments_by_number[int(number_raw)] = comment

                    metadata_member = self._find_metadata_member(archive)
                    if metadata_member:
                        try:
                            metadata = json.loads(
                                archive.read(metadata_member).decode("utf-8", errors="replace")
                            )
                            for item in metadata.get("photos", []):
                                filename = self._normalize_name(str(item.get("filename") or ""))
                                comment = str(item.get("comment") or "").strip()
                                number = item.get("number")
                                if filename and comment and not comments_by_filename.get(filename):
                                    comments_by_filename[filename] = comment
                                if isinstance(number, int) and comment and not comments_by_number.get(number):
                                    comments_by_number[number] = comment
                        except Exception:
                            pass

                    photo_entries = self._extract_importable_photo_entries(archive)
                    comments_attached = 0
                    for member_name, filename_for_comment, export_index in photo_entries:
                        try:
                            file_bytes = archive.read(member_name)
                            normalized_name = self._normalize_name(filename_for_comment)
                            comment = comments_by_filename.get(normalized_name, "")
                            if not comment and export_index is not None:
                                comment = comments_by_number.get(export_index, "")

                            photo = Photo(event=event, comment=comment)
                            photo.image.save(
                                filename_for_comment,
                                ContentFile(file_bytes),
                                save=False,
                            )
                            photo.save()
                            imported_count += 1
                            if comment:
                                comments_attached += 1
                        except Exception:
                            skipped_count += 1
                            continue
            except zipfile.BadZipFile:
                self.message_user(request, "Invalid ZIP file.", level=messages.ERROR)
            except Exception as exc:
                self.message_user(request, f"Import failed: {exc}", level=messages.ERROR)
            else:
                if imported_count:
                    message = (
                        f"Imported {imported_count} photo(s) into '{event.name}'. "
                        f"Attached comments to {comments_attached} photo(s)."
                    )
                    if skipped_count:
                        message += f" Skipped {skipped_count} file(s)."
                    self.message_user(request, message, level=messages.SUCCESS)
                else:
                    self.message_user(request, "No photos were imported from the ZIP file.", level=messages.WARNING)

            return HttpResponseRedirect(reverse("admin:events_event_change", args=[event.pk]))

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "original": event,
            "event": event,
            "title": f"Import gallery for {event.name}",
        }
        return TemplateResponse(request, "admin/events/event/import_gallery.html", context)

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


@admin.register(UploadChannel)
class UploadChannelAdmin(admin.ModelAdmin):
    list_display = ("label", "slug", "current_event", "upload_uid")
    list_filter = ("current_event",)
    search_fields = ("label", "slug")
    prepopulated_fields = {"slug": ("label",)}
    readonly_fields = ("upload_uid",)
    ordering = ("label",)


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
