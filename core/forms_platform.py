from django import forms

from .models import GlobalAdvertisement


INPUT_CLASSES = (
    'w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm '
    'text-slate-900 shadow-sm focus:border-blue-600 focus:outline-none '
    'focus:ring-2 focus:ring-blue-600'
)


class GlobalAdvertisementForm(forms.ModelForm):
    class Meta:
        model = GlobalAdvertisement
        fields = (
            'title', 'message', 'image', 'destination_url', 'button_label',
            'starts_at', 'ends_at', 'priority', 'is_active',
        )
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
            'starts_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'ends_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'priority': forms.NumberInput(attrs={'min': 0, 'max': 999}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name == 'is_active':
                field.widget.attrs['class'] = 'h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-600'
            else:
                field.widget.attrs['class'] = INPUT_CLASSES
        self.fields['image'].help_text = 'Optional JPG, PNG, GIF or WebP image, maximum 5 MB.'
        self.fields['destination_url'].help_text = 'Optional full link opened when the call-to-action is selected.'
        self.fields['priority'].help_text = 'Higher numbers appear first.'

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and getattr(image, 'size', 0) > 5 * 1024 * 1024:
            raise forms.ValidationError('The advertisement image must be 5 MB or smaller.')
        return image

    def clean(self):
        cleaned = super().clean()
        starts_at = cleaned.get('starts_at')
        ends_at = cleaned.get('ends_at')
        if starts_at and ends_at and ends_at <= starts_at:
            self.add_error('ends_at', 'The end time must be later than the start time.')
        image_value = cleaned.get('image')
        has_image = bool(image_value)
        if image_value is None and getattr(self.instance, 'image', None):
            has_image = bool(self.instance.image)
        if not cleaned.get('message') and not has_image:
            self.add_error('message', 'Add a message or upload an image.')
        if not cleaned.get('destination_url'):
            cleaned['button_label'] = ''
        return cleaned
