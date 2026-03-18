from django.contrib import messages
from django.core.exceptions import ValidationError
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
                    return redirect(
                        "events:event-upload-success",
                        slug=event.slug,
                    )
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
                    return redirect(f"{upload_url}?step=2&photo_id={photo.id}")
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

    context = {"event": event, "form": form}
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
