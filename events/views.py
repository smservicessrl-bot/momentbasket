from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import PhotoUploadForm
from .models import Event


def landing_page(request: HttpRequest) -> HttpResponse:
    """Marketing landing page for Momentbasket."""
    return render(request, "events/landing.html")


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

    if request.method == "POST":
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
                messages.success(request, "Köszönjük! A fényképed feltöltve.")
                return redirect("events:event-upload-success", slug=event.slug)
    else:
        form = PhotoUploadForm()

    context = {
        "event": event,
        "form": form,
    }
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
