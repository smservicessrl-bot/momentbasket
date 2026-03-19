import uuid

from django.db import migrations, models


def populate_gallery_uid(apps, schema_editor):
    Event = apps.get_model("events", "Event")
    for event in Event.objects.filter(gallery_uid=""):
        event.gallery_uid = uuid.uuid4().hex[:8].upper()
        event.save(update_fields=["gallery_uid"])


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0006_create_bemutato_esemeny_demo"),
    ]

    operations = [
        migrations.AddField(
            model_name="event",
            name="gallery_uid",
            field=models.CharField(blank=True, db_index=True, max_length=8),
        ),
        migrations.RunPython(populate_gallery_uid, migrations.RunPython.noop),
    ]
