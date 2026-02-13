from django import forms
from django.forms.utils import flatatt
from django.utils.safestring import mark_safe


class ColorPickerWidget(forms.TextInput):
    """
    A widget that displays both a color picker and a text input for hex color codes.
    """
    
    def __init__(self, attrs=None):
        default_attrs = {
            'type': 'text',
            'pattern': '#[0-9A-Fa-f]{6}',
            'placeholder': '#000000',
            'style': 'width: 120px;',
        }
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)
    
    def format_value(self, value):
        """
        Return the value as-is if it's a valid hex color, otherwise return empty string.
        """
        if value:
            # Ensure value starts with # for consistency
            if not value.startswith('#'):
                return f'#{value}'
            return value
        return ''
    
    def render(self, name, value, attrs=None, renderer=None):
        """
        Render the widget with both color picker and text input.
        """
        if attrs is None:
            attrs = {}
        
        # Get the formatted value
        formatted_value = self.format_value(value)
        
        # Set default color for color picker if value is empty
        color_value = formatted_value if formatted_value else '#000000'
        
        # Build the text input attributes
        text_attrs = self.build_attrs(attrs, {'name': name, 'value': formatted_value})
        text_input = super().render(name, formatted_value, text_attrs, renderer)
        
        # Build the color picker attributes
        color_attrs = {
            'type': 'color',
            'id': f'{name}_color_picker',
            'value': color_value,
            'style': 'width: 50px; height: 38px; margin-left: 8px; vertical-align: middle; cursor: pointer; border: 1px solid #ccc; border-radius: 4px;',
        }
        color_input = f'<input {flatatt(color_attrs)}>'
        
        # JavaScript to sync color picker with text input
        js = f'''
        <script>
        (function() {{
            var textInput = document.querySelector('input[name="{name}"]');
            var colorInput = document.getElementById('{name}_color_picker');
            
            if (textInput && colorInput) {{
                // Update color picker when text input changes
                textInput.addEventListener('input', function() {{
                    var value = this.value.trim();
                    if (value.match(/^#[0-9A-Fa-f]{{6}}$/)) {{
                        colorInput.value = value;
                    }}
                }});
                
                // Update text input when color picker changes
                colorInput.addEventListener('input', function() {{
                    textInput.value = this.value;
                }});
            }}
        }})();
        </script>
        '''
        
        return mark_safe(
            f'<div style="display: flex; align-items: center;">'
            f'{text_input}'
            f'{color_input}'
            f'</div>'
            f'{js}'
        )
