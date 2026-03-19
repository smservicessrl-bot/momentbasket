import csv
import json
import os
import zipfile
from io import BytesIO, StringIO

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import PhotoCommentForm, PhotoUploadForm
from .models import Event, Photo


def landing_page(request: HttpRequest) -> HttpResponse:
    """Marketing landing page for Momentbasket — same content as demo page."""
    sample_event = Event.objects.filter(is_active=True).first()
    return render(
        request,
        "events/demo.html",
        {"sample_event": sample_event},
    )


def get_client_ip(request: HttpRequest) -> str | None:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def event_upload(request: HttpRequest, slug: str) -> HttpResponse:
    try:
        event = Event.objects.get(slug=slug, is_active=True)
    except Event.DoesNotExist:
        # Check if event exists but is inactive
        try:
            event = Event.objects.get(slug=slug)
            # Event exists but is inactive
            return render(request, "events/event_inactive.html", {"event": event})
        except Event.DoesNotExist:
            # Event doesn't exist at all
            raise Http404("Event not found.") from None

    step = request.GET.get("step") or request.POST.get("step")
    photo_id = request.GET.get("photo_id") or request.POST.get("photo_id")
    uid = request.GET.get("uid") or request.POST.get("uid")

    if request.method == "POST":
        # Step 2: comment save (image already exists).
        if photo_id:
            try:
                photo = Photo.objects.get(id=photo_id, event=event)
            except Photo.DoesNotExist:
                raise Http404("Uploaded photo not found.") from None

            form = PhotoCommentForm(request.POST, instance=photo)
            if form.is_valid():
                try:
                    form.save()
                    upload_success_url = reverse(
                        "events:event-upload-success",
                        kwargs={"slug": event.slug},
                    )
                    if uid:
                        upload_success_url = f"{upload_success_url}?uid={uid}"
                    return redirect(upload_success_url)
                except ValidationError as exc:
                    form.add_error(None, exc)
                except Exception:
                    messages.error(
                        request,
                        "Hiba történt a megjegyzés mentése során. Kérjük, próbáld újra.",
                    )
        else:
            # Step 1: image upload.
            form = PhotoUploadForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    photo = form.save(commit=False)
                    photo.event = event
                    photo.uploader_ip = get_client_ip(request)
                    photo.save()
                except ValidationError as exc:
                    form.add_error(None, exc)
                except Exception:
                    messages.error(
                        request,
                        "Hiba történt a fénykép mentése során. Kérjük, próbáld újra.",
                    )
                else:
                    upload_url = reverse("events:event-upload", kwargs={"slug": event.slug})
                    redirect_url = f"{upload_url}?step=2&photo_id={photo.id}"
                    if uid:
                        redirect_url += f"&uid={uid}"
                    return redirect(redirect_url)
    else:
        # GET: choose step UI.
        if photo_id and step in (None, "2"):
            try:
                photo = Photo.objects.get(id=photo_id, event=event)
            except Photo.DoesNotExist:
                raise Http404("Uploaded photo not found.") from None
            form = PhotoCommentForm(instance=photo)
        else:
            form = PhotoUploadForm()

    context = {"event": event, "form": form, "uid": uid}
    # If step 2 has a photo_id, we may need the preview even after validation errors.
    if photo_id and "photo" in locals():
        context["photo"] = photo
    return render(request, "events/upload.html", context)


def upload_success(request: HttpRequest, slug: str) -> HttpResponse:
    try:
        event = Event.objects.get(slug=slug)
    except Event.DoesNotExist as exc:
        raise Http404("Event not found.") from exc

    return render(
        request,
        "events/upload_success.html",
        {
            "event": event,
            "uid": request.GET.get("uid"),
        },
    )


def event_gallery(request: HttpRequest, slug: str) -> HttpResponse:
    try:
        event = Event.objects.get(slug=slug)
    except Event.DoesNotExist as exc:
        raise Http404("Event not found.") from exc

    # Check if event is inactive - still show gallery but with a message
    # (Gallery can be viewed even if event is inactive)
    photos = event.photos.select_related("event").order_by("-uploaded_at")

    return render(
        request,
        "events/gallery.html",
        {
            "event": event,
            "photos": photos,
        },
    )


def event_gallery_download(request: HttpRequest, slug: str) -> HttpResponse:
    """Public download of all event photos and comments as ZIP."""
    try:
        event = Event.objects.get(slug=slug)
    except Event.DoesNotExist as exc:
        raise Http404("Event not found.") from exc

    photos = event.photos.order_by("uploaded_at")
    if not photos.exists():
        messages.warning(request, "No photos are available for download yet.")
        return redirect("events:event-gallery", slug=event.slug)

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for idx, photo in enumerate(photos, 1):
            if photo.image and default_storage.exists(photo.image.name):
                try:
                    with default_storage.open(photo.image.name, "rb") as image_file:
                        original_filename = os.path.basename(photo.image.name)
                        zip_filename = f"photos/{idx:04d}_{original_filename}"
                        zip_file.writestr(zip_filename, image_file.read())
                except Exception:
                    continue

        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(["Photo Number", "Filename", "Comment", "Uploaded At", "Uploader IP"])
        for idx, photo in enumerate(photos, 1):
            original_filename = os.path.basename(photo.image.name) if photo.image else f"photo_{idx}.jpg"
            csv_writer.writerow(
                [
                    idx,
                    original_filename,
                    photo.comment or "",
                    photo.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if photo.uploaded_at else "",
                    str(photo.uploader_ip) if photo.uploader_ip else "",
                ]
            )
        zip_file.writestr("comments.csv", csv_buffer.getvalue().encode("utf-8"))

        metadata = {
            "event": {
                "name": event.name,
                "slug": event.slug,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "end_time": event.end_time.isoformat() if event.end_time else None,
            },
            "total_photos": photos.count(),
            "exported_at": timezone.now().isoformat(),
        }
        zip_file.writestr("metadata.json", json.dumps(metadata, indent=2).encode("utf-8"))

    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    safe_filename = event.slug.replace(" ", "_")
    response["Content-Disposition"] = f'attachment; filename="{safe_filename}_gallery.zip"'
    return response


def event_index(request: HttpRequest) -> HttpResponse:
    now = timezone.now()
    events = (
        Event.objects.filter(is_active=True)
        .order_by("start_time", "name")
        .select_related()
    )

    event_rows = []
    for event in events:
        is_running = False
        if event.start_time and event.end_time:
            is_running = event.start_time <= now <= event.end_time
        elif event.start_time and not event.end_time:
            is_running = event.start_time <= now
        elif not event.start_time and event.end_time:
            is_running = now <= event.end_time

        event_rows.append(
            {
                "object": event,
                "is_running": is_running,
            }
        )

    return render(
        request,
        "events/index.html",
        {
            "events": event_rows,
            "now": now,
        },
    )


def demo_page(request: HttpRequest) -> HttpResponse:
    """Professional demo page for showcasing the platform to potential customers."""
    # Get a sample event if available for demonstration
    sample_event = Event.objects.filter(is_active=True).first()
    
    return render(
        request,
        "events/demo.html",
        {
            "sample_event": sample_event,
        },
    )
