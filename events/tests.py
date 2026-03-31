from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from .models import Event, Photo, UploadChannel


def _minimal_jpeg_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (4, 4), color=(200, 100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


class GalleryUploadDownloadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.event = Event.objects.create(
            name="Test Wedding",
            slug="test-wedding",
            is_active=True,
        )
        self.event.refresh_from_db()
        self.gallery_uid = self.event.gallery_uid

    def test_event_gallery_renders(self):
        url = reverse("events:event-gallery", kwargs={"slug": self.event.slug})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Test Wedding")

    def test_customer_gallery_renders_with_uid(self):
        url = reverse(
            "events:customer-gallery",
            kwargs={"slug": self.event.slug, "uid": self.gallery_uid},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Test Wedding")

    def test_customer_gallery_404_wrong_uid(self):
        url = reverse(
            "events:customer-gallery",
            kwargs={"slug": self.event.slug, "uid": "deadbeef"},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_customer_gallery_download_empty_redirects(self):
        url = reverse(
            "events:customer-gallery-download",
            kwargs={"slug": self.event.slug, "uid": self.gallery_uid},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302)
        self.assertIn("/customer-gallery/", r.url)

    def test_customer_gallery_download_zip_with_photo(self):
        img = SimpleUploadedFile(
            "shot.jpg",
            _minimal_jpeg_bytes(),
            content_type="image/jpeg",
        )
        photo = Photo.objects.create(event=self.event, image=img)
        self.assertTrue(photo.image)

        url = reverse(
            "events:customer-gallery-download",
            kwargs={"slug": self.event.slug, "uid": self.gallery_uid},
        )
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/zip")
        self.assertIn("attachment", r["Content-Disposition"])

    def test_legacy_event_upload_get(self):
        url = reverse("events:event-upload", kwargs={"slug": self.event.slug})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)

    def test_channel_upload_requires_uid(self):
        ch = UploadChannel.objects.create(
            label="Venue",
            slug="grand-hall",
            current_event=self.event,
        )
        url = reverse("events:channel-upload", kwargs={"channel_slug": ch.slug})
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_channel_upload_get_with_valid_uid(self):
        ch = UploadChannel.objects.create(
            label="Venue",
            slug="grand-hall",
            current_event=self.event,
        )
        ch.refresh_from_db()
        url = reverse("events:channel-upload", kwargs={"channel_slug": ch.slug})
        r = self.client.get(f"{url}?uid={ch.upload_uid}")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Test Wedding")

    def test_channel_upload_unconfigured(self):
        ch = UploadChannel.objects.create(label="Venue", slug="empty-hall")
        self.assertIsNone(ch.current_event_id)
        url = reverse("events:channel-upload", kwargs={"channel_slug": ch.slug})
        r = self.client.get(f"{url}?uid={ch.upload_uid}")
        self.assertEqual(r.status_code, 404)

    def test_legacy_upload_post_creates_photo_and_redirects_to_step2(self):
        url = reverse("events:event-upload", kwargs={"slug": self.event.slug})
        img = SimpleUploadedFile(
            "shot.jpg",
            _minimal_jpeg_bytes(),
            content_type="image/jpeg",
        )
        r = self.client.post(url, {"image": img}, follow=False)
        self.assertEqual(r.status_code, 302)
        self.assertIn("step=2", r["Location"])
        self.assertIn("photo_id=", r["Location"])
        self.assertEqual(Photo.objects.filter(event=self.event).count(), 1)

    def test_channel_upload_post_creates_photo(self):
        ch = UploadChannel.objects.create(
            label="Venue",
            slug="photo-hall",
            current_event=self.event,
        )
        ch.refresh_from_db()
        url = reverse("events:channel-upload", kwargs={"channel_slug": ch.slug})
        full = f"{url}?uid={ch.upload_uid}"
        img = SimpleUploadedFile(
            "p.jpg",
            _minimal_jpeg_bytes(),
            content_type="image/jpeg",
        )
        r = self.client.post(full, {"image": img})
        self.assertEqual(r.status_code, 302)
        self.assertIn(ch.slug, r["Location"])
        self.assertIn("step=2", r["Location"])
        self.assertEqual(Photo.objects.filter(event=self.event).count(), 1)

    def test_upload_success_pages(self):
        u1 = reverse("events:event-upload-success", kwargs={"slug": self.event.slug})
        r1 = self.client.get(u1)
        self.assertEqual(r1.status_code, 200)

        ch = UploadChannel.objects.create(
            label="V",
            slug="thanks-hall",
            current_event=self.event,
        )
        ch.refresh_from_db()
        u2 = reverse("events:channel-upload-success", kwargs={"channel_slug": ch.slug})
        r2 = self.client.get(f"{u2}?uid={ch.upload_uid}")
        self.assertEqual(r2.status_code, 200)
