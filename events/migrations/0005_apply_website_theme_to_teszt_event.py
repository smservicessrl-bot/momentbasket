# Data migration: apply website/demo theme to event "teszt-event"
# so upload and gallery pages match the main site colors.

from django.db import migrations

WEBSITE_THEME = {
    "bg_color_1": "#f9e0ff",
    "bg_color_2": "#c8f5ff",
    "bg_color_3": "#ffe4d6",
    "primary_color": "#2b2d42",
    "accent_color_1": "#7254ff",
    "accent_color_2": "#ff7ca3",
    "text_primary_color": "#2b2d42",
    "text_muted_color": "#6c7286",
}


def apply_website_theme(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    Event.objects.filter(slug="teszt-event").update(**WEBSITE_THEME)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0004_add_upload_page_subtitle"),
    ]

    operations = [
        migrations.RunPython(apply_website_theme, noop),
    ]
