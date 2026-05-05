import csv
import json
import os
import re
import zipfile
from io import BytesIO, StringIO
from pathlib import Path, PurePosixPath

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView, LogoutView
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .admin_forms import EventForm, GalleryImportForm, PhotoFormSet
from .models import Event, Photo, UploadChannel
from .utils import generate_event_qr_code
from .validators import DEFAULT_ALLOWED_EXTENSIONS


def is_staff_user(user):
    """Check if user is staff or superuser."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


def _extract_importable_photo_entries(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    """
    Return photo entries from any nested .../photos/ path.
    Tuple values are (member_name, original_filename_for_comment_lookup).
    """
    allowed_exts = {ext.lower() for ext in DEFAULT_ALLOWED_EXTENSIONS}
    entries: list[tuple[str, str]] = []

    for name in archive.namelist():
        if name.endswith("/"):
            continue

        parts = PurePosixPath(name).parts
        try:
            photos_idx = parts.index("photos")
        except ValueError:
            continue

        if photos_idx == len(parts) - 1:
            continue

        member_filename = parts[-1]
        # Skip hidden/system helper files often added by OS zip tools.
        if member_filename.startswith(".") or member_filename.startswith("._"):
            continue

        _, ext = os.path.splitext(member_filename.lower())
        if ext not in allowed_exts:
            continue

        # Exported archives may prefix files as: 0001_original.jpg.
        # Strip only that numeric prefix pattern (do not strip normal underscores).
        match = re.match(r"^\d+_(.+)$", member_filename)
        filename_for_comment = match.group(1) if match else member_filename
        entries.append((name, filename_for_comment))

    return entries


def _normalize_comment_filename(value: str) -> str:
    """Normalize filename keys so CSV and ZIP names can be matched reliably."""
    return os.path.basename((value or "").strip()).lower()


@login_required
@user_passes_test(is_staff_user)
def admin_dashboard(request):
    """Admin dashboard with statistics."""
    now = timezone.now()
    
    # Statistics
    total_events = Event.objects.count()
    active_events = Event.objects.filter(is_active=True).count()
    total_photos = Photo.objects.count()
    
    # Recent events
    recent_events = Event.objects.order_by('-id')[:5]
    
    # Events by status
    upcoming_events = Event.objects.filter(
        Q(start_time__gt=now) | Q(start_time__isnull=True),
        is_active=True
    ).count()
    
    running_events = Event.objects.filter(
        Q(start_time__lte=now) & (Q(end_time__gte=now) | Q(end_time__isnull=True)),
        is_active=True
    ).count()
    
    past_events = Event.objects.filter(
        end_time__lt=now,
        is_active=True
    ).count()
    
    # Events with photo counts
    events_with_stats = Event.objects.annotate(
        photo_count=Count('photos')
    ).order_by('-id')[:10]
    
    # Recent photos
    recent_photos = Photo.objects.select_related('event').order_by('-uploaded_at')[:10]
    
    context = {
        'total_events': total_events,
        'active_events': active_events,
        'total_photos': total_photos,
        'upcoming_events': upcoming_events,
        'running_events': running_events,
        'past_events': past_events,
        'recent_events': recent_events,
        'events_with_stats': events_with_stats,
        'recent_photos': recent_photos,
    }
    
    return render(request, 'events/admin/dashboard.html', context)


@login_required
@user_passes_test(is_staff_user)
def admin_event_list(request):
    """List all events with management options."""
    events = Event.objects.annotate(
        photo_count=Count('photos')
    ).order_by('-id')
    
    # Filter by status if provided
    status_filter = request.GET.get('status')
    if status_filter == 'active':
        events = events.filter(is_active=True)
    elif status_filter == 'inactive':
        events = events.filter(is_active=False)
    
    context = {
        'events': events,
        'status_filter': status_filter,
    }
    
    return render(request, 'events/admin/event_list.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["GET", "POST"])
def admin_gallery_import(request):
    """Import an offline-exported gallery ZIP into an existing event."""
    if request.method == "POST":
        form = GalleryImportForm(request.POST, request.FILES)
        if form.is_valid():
            event = form.cleaned_data["event"]
            uploaded_zip = form.cleaned_data["gallery_zip"]

            imported_count = 0
            skipped_count = 0

            try:
                with zipfile.ZipFile(uploaded_zip) as archive:
                    comments_by_filename = {}
                    if "comments.csv" in archive.namelist():
                        comments_csv = archive.read("comments.csv").decode("utf-8", errors="replace")
                        reader = csv.DictReader(StringIO(comments_csv))
                        for row in reader:
                            # Accept a few practical header variants to be resilient.
                            filename = (
                                row.get("Filename")
                                or row.get("filename")
                                or row.get("File")
                                or row.get("file")
                                or row.get("Image")
                                or row.get("image")
                                or ""
                            ).strip()
                            if filename:
                                comments_by_filename[_normalize_comment_filename(filename)] = (
                                    row.get("Comment")
                                    or row.get("comment")
                                    or ""
                                ).strip()

                    photo_entries = _extract_importable_photo_entries(archive)
                    for member_name, filename_for_comment in photo_entries:
                        try:
                            file_bytes = archive.read(member_name)
                            normalized_name = _normalize_comment_filename(filename_for_comment)
                            comment = comments_by_filename.get(normalized_name, "")

                            photo = Photo(event=event, comment=comment)
                            photo.image.save(filename_for_comment, ContentFile(file_bytes), save=False)
                            photo.save()
                            imported_count += 1
                        except Exception:
                            skipped_count += 1
                            continue
            except zipfile.BadZipFile:
                messages.error(request, "Invalid ZIP file. Please upload a valid exported gallery ZIP.")
            except Exception as exc:
                messages.error(request, f"Failed to import gallery: {exc}")
            else:
                if imported_count:
                    messages.success(
                        request,
                        f"Imported {imported_count} photo(s) into '{event.name}'."
                        + (f" Skipped {skipped_count} file(s)." if skipped_count else ""),
                    )
                else:
                    messages.warning(request, "No photos were imported from the ZIP file.")
                return redirect("events:admin-event-detail", event_id=event.id)
    else:
        initial_event_id = request.GET.get("event")
        initial = {}
        if initial_event_id and initial_event_id.isdigit():
            initial["event"] = int(initial_event_id)
        form = GalleryImportForm(initial=initial)

    return render(request, "events/admin/gallery_import.html", {"form": form})


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["GET", "POST"])
def admin_event_create(request):
    """Create a new event."""
    if request.method == 'POST':
        form = EventForm(request.POST)
        if form.is_valid():
            event = form.save()
            # Now create formset with the saved event instance
            formset = PhotoFormSet(request.POST, request.FILES, instance=event)
            if formset.is_valid():
                formset.save()
                messages.success(request, f'Event "{event.name}" created successfully.')
                return redirect('events:admin-event-detail', event_id=event.id)
            else:
                # If formset is invalid, we still need to show errors
                # But event is already saved, so redirect to edit page
                messages.warning(request, 'Event created but some photos could not be saved. Please check the errors.')
                return redirect('events:admin-event-edit', event_id=event.id)
        else:
            # Form is invalid, create empty formset for display
            formset = PhotoFormSet(instance=None)
    else:
        form = EventForm()
        formset = None  # Don't show formset for new events
    
    return render(request, 'events/admin/event_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Create New Event',
        'action': 'Create',
    })


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["GET", "POST"])
def admin_event_edit(request, event_id):
    """Edit an existing event."""
    event = get_object_or_404(Event, id=event_id)
    
    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        formset = PhotoFormSet(request.POST, request.FILES, instance=event)
        if form.is_valid() and formset.is_valid():
            event = form.save()
            formset.save()
            messages.success(request, f'Event "{event.name}" updated successfully.')
            return redirect('events:admin-event-detail', event_id=event.id)
    else:
        form = EventForm(instance=event)
        formset = PhotoFormSet(instance=event)
    
    return render(request, 'events/admin/event_form.html', {
        'form': form,
        'formset': formset,
        'event': event,
        'title': f'Edit Event: {event.name}',
        'action': 'Update',
    })


@login_required
@user_passes_test(is_staff_user)
def admin_event_detail(request, event_id):
    """View event details and manage it."""
    event = get_object_or_404(Event, id=event_id)
    
    photos = event.photos.order_by('-uploaded_at')
    photo_count = photos.count()
    
    # Statistics
    photos_with_comments = photos.exclude(comment='').count()
    
    context = {
        'event': event,
        'photos': photos[:50],  # Show first 50
        'photo_count': photo_count,
        'photos_with_comments': photos_with_comments,
        'upload_channels': UploadChannel.objects.filter(current_event=event).order_by('label'),
    }
    
    return render(request, 'events/admin/event_detail.html', context)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def admin_event_delete(request, event_id):
    """Delete an event."""
    event = get_object_or_404(Event, id=event_id)
    event_name = event.name
    
    if request.method == 'POST':
        event.delete()
        messages.success(request, f'Event "{event_name}" deleted successfully.')
        return redirect('events:admin-event-list')
    
    return redirect('events:admin-event-detail', event_id=event_id)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def admin_event_toggle_active(request, event_id):
    """Toggle event active status."""
    event = get_object_or_404(Event, id=event_id)
    event.is_active = not event.is_active
    event.save()
    
    status = 'activated' if event.is_active else 'deactivated'
    messages.success(request, f'Event "{event.name}" {status}.')
    
    return redirect('events:admin-event-detail', event_id=event_id)


@login_required
@user_passes_test(is_staff_user)
@require_http_methods(["POST"])
def admin_event_generate_qr(request, event_id):
    """Generate QR code for an event."""
    event = get_object_or_404(Event, id=event_id)
    
    try:
        generate_event_qr_code(event)
        channels = UploadChannel.objects.filter(current_event=event)
        if channels.exists():
            slugs = ", ".join(c.slug for c in channels)
            messages.success(
                request,
                f'QR code(s) generated for upload channel(s): {slugs}. '
                f'Event name "{event.name}" appears on the upload and gallery pages only.',
            )
        else:
            messages.success(
                request,
                f'Legacy QR code generated for "{event.name}" (slug-based upload URL). '
                "Assign an upload channel’s current event to this event for a reusable venue/photographer QR.",
            )
    except Exception as e:
        messages.error(request, f'Failed to generate QR code: {str(e)}')
    
    return redirect('events:admin-event-detail', event_id=event_id)


@login_required
@user_passes_test(is_staff_user)
def admin_download_event_data(request, event_id):
    """Download all photos and comments for an event as ZIP + CSV."""
    event = get_object_or_404(Event, id=event_id)
    photos = event.photos.order_by('uploaded_at')
    
    if not photos.exists():
        messages.warning(request, 'No photos to download for this event.')
        return redirect('events:admin-event-detail', event_id=event_id)
    
    # Create ZIP file in memory
    zip_buffer = BytesIO()
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Add all photos
        for idx, photo in enumerate(photos, 1):
            if photo.image and default_storage.exists(photo.image.name):
                try:
                    with default_storage.open(photo.image.name, 'rb') as img_file:
                        # Get original filename or create one
                        original_filename = os.path.basename(photo.image.name)
                        # Ensure unique filename
                        zip_filename = f"photos/{idx:04d}_{original_filename}"
                        zip_file.writestr(zip_filename, img_file.read())
                except Exception as e:
                    # Skip files that can't be read
                    continue
        
        # Create CSV with comments
        csv_buffer = StringIO()
        csv_writer = csv.writer(csv_buffer)
        csv_writer.writerow(['Photo Number', 'Filename', 'Comment', 'Uploaded At', 'Uploader IP'])
        
        for idx, photo in enumerate(photos, 1):
            original_filename = os.path.basename(photo.image.name) if photo.image else f"photo_{idx}.jpg"
            csv_writer.writerow([
                idx,
                original_filename,
                photo.comment or '',
                photo.uploaded_at.strftime('%Y-%m-%d %H:%M:%S') if photo.uploaded_at else '',
                str(photo.uploader_ip) if photo.uploader_ip else '',
            ])
        
        csv_buffer.seek(0)
        zip_file.writestr('comments.csv', csv_buffer.getvalue().encode('utf-8'))
        
        # Create JSON with metadata
        json_data = {
            'event': {
                'name': event.name,
                'slug': event.slug,
                'start_time': event.start_time.isoformat() if event.start_time else None,
                'end_time': event.end_time.isoformat() if event.end_time else None,
            },
            'photos': [
                {
                    'number': idx,
                    'filename': os.path.basename(photo.image.name) if photo.image else f"photo_{idx}.jpg",
                    'comment': photo.comment or '',
                    'uploaded_at': photo.uploaded_at.isoformat() if photo.uploaded_at else None,
                    'uploader_ip': str(photo.uploader_ip) if photo.uploader_ip else None,
                }
                for idx, photo in enumerate(photos, 1)
            ],
            'total_photos': photos.count(),
            'exported_at': timezone.now().isoformat(),
        }
        
        json_buffer = BytesIO()
        json_buffer.write(json.dumps(json_data, indent=2).encode('utf-8'))
        json_buffer.seek(0)
        zip_file.writestr('metadata.json', json_buffer.getvalue())
    
    zip_buffer.seek(0)
    
    # Create response
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    safe_filename = event.slug.replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="{safe_filename}_event_data.zip"'
    
    return response


class AdminLoginView(LoginView):
    """Custom admin login view."""
    template_name = 'events/admin/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        return '/'


class AdminLogoutView(LogoutView):
    """Custom admin logout view."""
    next_page = '/admin-panel/login/'
