"""The site's one form renderer. Every form rendered with {{ form.as_div }}
and every field with {{ form.field.as_field_group }} comes out in the design
system's markup (components.css: .field, .field-help, .field-error), from
templates/django/forms/div.html and field.html, with no template of its own.

TemplatesSetting, so those project templates override Django's own; it is
also why django.forms is an installed app (the widget templates). The
BoundField below only answers questions the field template asks: which
wrapper the field wants, and whether it is short enough not to stretch."""

from django import forms
from django.forms.renderers import TemplatesSetting

# Input types whose content has a natural short width.
SHORT_TYPES = {"date", "time", "datetime-local", "month", "week", "number"}
SHORT_MAX_LENGTH = 12


class BoundField(forms.BoundField):
    @property
    def is_checkbox(self):
        return isinstance(self.field.widget, forms.CheckboxInput)

    @property
    def is_choice_row(self):
        """Radios and checkbox lists: a fieldset whose options sit in a row."""
        return isinstance(self.field.widget, (forms.RadioSelect, forms.CheckboxSelectMultiple))

    @property
    def is_short(self):
        widget = self.field.widget
        kind = widget.attrs.get("type") or getattr(widget, "input_type", None)
        if kind in SHORT_TYPES or widget.attrs.get("inputmode") == "numeric":
            return True
        max_length = getattr(self.field, "max_length", None)
        return isinstance(widget, forms.TextInput) and max_length is not None and max_length <= SHORT_MAX_LENGTH


class FormRenderer(TemplatesSetting):
    form_template_name = "django/forms/div.html"
    field_template_name = "django/forms/field.html"
    bound_field_class = BoundField
