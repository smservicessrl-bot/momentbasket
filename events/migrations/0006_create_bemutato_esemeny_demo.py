# Data migration: create a default demo event for presentations.
#
# Ensures this URL always works (no UUID required):
#   /e/bemutato-esemeny/upload/

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


def create_bemutato_esemeny(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    slug = "bemutato-esemeny"

    if Event.objects.filter(slug=slug).exists():
        return

    Event.objects.create(
        name="Bemutató esemény",
        slug=slug,
        is_active=True,
        couple_names="",
        upload_page_subtitle="Ossz meg egy különleges pillanatot a bemutató eseményen.",
        **WEBSITE_THEME,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0005_apply_website_theme_to_teszt_event"),
    ]

    operations = [
        migrations.RunPython(create_bemutato_esemeny),
    ]

