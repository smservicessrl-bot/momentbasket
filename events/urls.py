from django.urls import path

from . import views
from .admin_views import (
    AdminLoginView,
    AdminLogoutView,
    admin_dashboard,
    admin_download_event_data,
    admin_event_create,
    admin_event_delete,
    admin_event_detail,
    admin_event_edit,
    admin_event_generate_qr,
    admin_event_list,
    admin_event_toggle_active,
)

app_name = "events"

urlpatterns = [
    # Root - Landing Page
    path("", views.landing_page, name="landing-page"),
    
    # Public URLs
    path("events/", views.event_index, name="event-index"),
    path("e/<slug:slug>/upload/", views.event_upload, name="event-upload"),
    path("e/<slug:slug>/thanks/", views.upload_success, name="event-upload-success"),
    path("e/<slug:slug>/gallery/", views.event_gallery, name="event-gallery"),
    
    # Admin URLs
    path("admin-panel/login/", AdminLoginView.as_view(), name="admin-login"),
    path("admin-panel/logout/", AdminLogoutView.as_view(), name="admin-logout"),
    path("admin-panel/dashboard/", admin_dashboard, name="admin-dashboard"),
    path("admin-panel/events/", admin_event_list, name="admin-event-list"),
    path("admin-panel/events/create/", admin_event_create, name="admin-event-create"),
    path("admin-panel/events/<int:event_id>/", admin_event_detail, name="admin-event-detail"),
    path("admin-panel/events/<int:event_id>/edit/", admin_event_edit, name="admin-event-edit"),
    path("admin-panel/events/<int:event_id>/delete/", admin_event_delete, name="admin-event-delete"),
    path("admin-panel/events/<int:event_id>/toggle-active/", admin_event_toggle_active, name="admin-event-toggle-active"),
    path("admin-panel/events/<int:event_id>/generate-qr/", admin_event_generate_qr, name="admin-event-generate-qr"),
    path("admin-panel/events/<int:event_id>/download/", admin_download_event_data, name="admin-download-event-data"),
]

