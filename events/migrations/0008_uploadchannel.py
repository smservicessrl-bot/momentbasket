import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("events", "0007_event_gallery_uid"),
    ]

    operations = [
        migrations.CreateModel(
            name="UploadChannel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=100, unique=True)),
                (
                    "label",
                    models.CharField(
                        help_text="Venue, photographer, or designer (admin only; not used in the public upload URL).",
                        max_length=255,
                    ),
                ),
                ("upload_uid", models.CharField(db_index=True, editable=False, max_length=8, unique=True)),
                (
                    "current_event",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="upload_channels_as_current",
                        to="events.event",
                    ),
                ),
            ],
            options={
                "ordering": ("label",),
            },
        ),
    ]
