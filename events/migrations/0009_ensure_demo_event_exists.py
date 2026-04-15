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


def ensure_bemutato_esemeny(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    slug = "bemutato-esemeny"

    Event.objects.get_or_create(
        slug=slug,
        defaults={
            "name": "Bemutató esemény",
            "is_active": True,
            "couple_names": "",
            "upload_page_subtitle": "Ossz meg egy különleges pillanatot a bemutató eseményen.",
            **WEBSITE_THEME,
        },
    )


class Migration(migrations.Migration):
    dependencies = [
        ("events", "0008_uploadchannel"),
    ]

    operations = [
        migrations.RunPython(ensure_bemutato_esemeny, migrations.RunPython.noop),
    ]

