from django import forms

from .models import Photo
from .validators import validate_photo_image


class PhotoUploadForm(forms.ModelForm):
    class Meta:
        model = Photo
        fields = ["image", "comment"]
        widgets = {
            "comment": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Írj egy opcionális üzenetet a fényképhez...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["image"].widget.attrs.update(
            {
                "accept": "image/*",
                "capture": "environment",
            }
        )

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if not image:
            raise forms.ValidationError("Kérjük, válassz ki egy fényképet a feltöltéshez.")

        validate_photo_image(image)

        return image

