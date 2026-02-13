from django import forms
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import Event, Photo
from .validators import validate_photo_image


class DateTimeLocalInput(forms.DateTimeInput):
    """Custom widget for datetime-local input."""
    input_type = 'datetime-local'
    
    def format_value(self, value):
        """Format datetime value for datetime-local input."""
        if value is None:
            return ''
        if isinstance(value, str):
            return value
        # Convert to local timezone and format as YYYY-MM-DDTHH:MM
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime('%Y-%m-%dT%H:%M')


class EventForm(forms.ModelForm):
    """Form for creating and editing events."""
    
    class Meta:
        model = Event
        fields = [
            'name',
            'slug',
            'is_active',
            'start_time',
            'end_time',
            'couple_names',
            'upload_page_subtitle',
            'bg_color_1',
            'bg_color_2',
            'bg_color_3',
            'primary_color',
            'accent_color_1',
            'accent_color_2',
            'text_primary_color',
            'text_muted_color',
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., John & Jane Wedding',
            }),
            'slug': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., john-jane-wedding',
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
            }),
            'start_time': DateTimeLocalInput(attrs={
                'class': 'form-control',
            }),
            'end_time': DateTimeLocalInput(attrs={
                'class': 'form-control',
            }),
            'couple_names': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., John & Jane',
            }),
            'upload_page_subtitle': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Ossz meg egy különleges pillanatot az ifjú párral.',
                'rows': 3,
            }),
            'bg_color_1': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
            'bg_color_2': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
            'bg_color_3': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
            'primary_color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
            'accent_color_1': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
            'accent_color_2': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
            'text_primary_color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
            'text_muted_color': forms.TextInput(attrs={
                'type': 'color',
                'class': 'form-control form-control-color',
            }),
        }
        help_texts = {
            'slug': 'URL-friendly identifier for the event (auto-generated from name if left blank)',
            'start_time': 'When the event starts (optional)',
            'end_time': 'When the event ends (optional)',
            'couple_names': 'Names to display on the upload page',
            'upload_page_subtitle': 'Subtitle message displayed on the upload page (e.g., "Ossz meg egy különleges pillanatot az ifjú párral.")',
            'bg_color_1': 'Background gradient color 1',
            'bg_color_2': 'Background gradient color 2',
            'bg_color_3': 'Background gradient color 3',
            'primary_color': 'Primary color for UI elements',
            'accent_color_1': 'Accent gradient color 1',
            'accent_color_2': 'Accent gradient color 2',
            'text_primary_color': 'Primary text color',
            'text_muted_color': 'Muted/secondary text color',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make slug not required if editing
        if self.instance and self.instance.pk:
            self.fields['slug'].required = False
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        # Auto-generate slug from name if not provided
        if not instance.slug and instance.name:
            from django.utils.text import slugify
            instance.slug = slugify(instance.name)
            # Ensure uniqueness
            base_slug = instance.slug
            counter = 1
            while Event.objects.filter(slug=instance.slug).exclude(pk=instance.pk if instance.pk else None).exists():
                instance.slug = f"{base_slug}-{counter}"
                counter += 1
        if commit:
            instance.save()
        return instance


class PhotoForm(forms.ModelForm):
    """Form for manually adding photos in admin."""
    
    class Meta:
        model = Photo
        fields = ['image', 'comment']
        widgets = {
            'image': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*',
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Opcionális megjegyzés...',
            }),
        }
    
    def clean_image(self):
        image = self.cleaned_data.get("image")
        # Only validate if image is provided (for new photos)
        if image:
            validate_photo_image(image)
        return image


# Create inline formset for photos
PhotoFormSet = inlineformset_factory(
    Event,
    Photo,
    form=PhotoForm,
    extra=0,  # Don't show empty forms by default - user will add them via button
    can_delete=True,
    fields=['image', 'comment']
)
