"""One form renderer for the whole site (config.forms.FormRenderer): every
form rendered with as_div, and every field with as_field_group, comes out in
the design system's .field markup, with no template of its own."""

import re

from django import forms
from django.conf import settings
from django.forms.renderers import get_default_renderer


class Demo(forms.Form):
    name = forms.CharField(help_text="As on your contract.")
    when = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    starts = forms.TimeField(required=False, widget=forms.TimeInput(attrs={"type": "time"}))
    hours = forms.DecimalField(required=False)
    postcode = forms.CharField(required=False, max_length=10)
    notes = forms.CharField(required=False, max_length=300)
    agree = forms.BooleanField(required=False, label="I agree", help_text="Tick to agree.")
    kind = forms.ChoiceField(required=False, widget=forms.RadioSelect,
                             choices=[("a", "Apple"), ("b", "Banana")])
    secret = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean(self):
        raise forms.ValidationError("Something about the whole form.")


def _field_div(html, name):
    """The .field wrapper holding the control named `name`: the page cut
    at the start of each wrapper (they never nest)."""
    for block in re.split(r'(?=<(?:div|fieldset) class="field[ "])', html):
        if block.startswith(("<div class=\"field", "<fieldset class=\"field")) and f'name="{name}"' in block:
            return block
    raise AssertionError(f"no .field for {name}")


def test_the_site_uses_the_project_renderer():
    assert settings.FORM_RENDERER == "config.forms.FormRenderer"
    assert type(get_default_renderer()).__name__ == "FormRenderer"


def test_every_field_is_wrapped_labelled_without_a_colon_and_helped():
    html = str(Demo().as_div())
    assert html.count('class="field') >= 8
    name = _field_div(html, "name")
    assert '<label for="id_name">Name</label>' in name
    assert '<p class="field-help" id="id_name_helptext">As on your contract.</p>' in name
    assert 'aria-describedby="id_name_helptext"' in name
    assert ":</label>" not in html


def test_errors_are_alerts_and_mark_the_field_invalid():
    form = Demo(data={"name": "", "when": "nonsense"})
    html = str(form.as_div())
    first_error = html.index('class="field-error"')
    assert first_error < re.search(r'class="field[ "]', html).start(), "non-field errors come first"
    assert '<p class="field-error" role="alert">Something about the whole form.</p>' in html
    name = _field_div(html, "name")
    assert 'class="field field-invalid"' in name
    assert '<p class="field-error" role="alert">This field is required.</p>' in name
    assert 'id="id_name_error"' in name and 'aria-invalid="true"' in name


def test_a_checkbox_sits_inside_its_label():
    html = str(Demo().as_div())
    agree = _field_div(html, "agree")
    assert agree.startswith('<div class="field field-check">')
    assert re.search(r'<label for="id_agree"><input type="checkbox" name="agree"[^>]*> I agree</label>', agree)
    assert '<p class="field-help" id="id_agree_helptext">Tick to agree.</p>' in agree


def test_dates_times_numbers_and_short_text_are_short():
    html = str(Demo().as_div())
    for name in ("when", "starts", "hours", "postcode"):
        assert "field-short" in _field_div(html, name).split(">")[0], name
    for name in ("name", "notes", "agree"):
        assert "field-short" not in _field_div(html, name).split(">")[0], name


def test_radios_keep_their_row_and_hidden_fields_are_rendered_once():
    html = str(Demo().as_div())
    kind = _field_div(html, "kind")
    assert kind.startswith('<fieldset class="field">') and "<legend>Kind</legend>" in kind
    assert '<div class="radio-row">' in kind and "> Apple</label>" in kind
    assert html.count('name="secret"') == 1 and 'type="hidden"' in html


def test_a_single_field_group_uses_the_same_template():
    html = str(Demo()["when"].as_field_group())
    assert html.strip().startswith('<div class="field field-short">')
    assert '<label for="id_when">When</label>' in html


def test_the_personal_details_page_uses_it_with_autocomplete(employee_client, employee_user):
    from tests.factories import hours_employee, make_employee
    hours_employee(employee=make_employee(user=employee_user))
    body = employee_client.get("/people/me/").content.decode()
    assert '<label for="id_personal_email">Personal email</label>' in body
    assert 'autocomplete="email"' in body and 'autocomplete="tel"' in body and 'inputmode="tel"' in body
    assert 'autocomplete="postal-code"' in body
    assert 'class="field field-short"' in body                       # the postcode
