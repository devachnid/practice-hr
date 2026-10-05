"""The NI number as people type it and as it is stored. Stored: two
letters, six digits and A, B, C or D, in capitals and without spaces
(Employee.ni_number's validator). Typed: any case, with spaces, as it is
printed on a payslip ("ab 12 34 56 c"); the forms that take it normalise
it before the model's validator sees it."""

# Long enough for the spaced form a person types; the stored value is 9.
TYPED_MAX = 20


def normalise(value):
    """No whitespace anywhere, in capitals. Blank stays blank."""
    return "".join((value or "").split()).upper()


def accept_typed(form, field="ni_number"):
    """Let `form`'s NI number field take the spaced form: its length limit
    becomes TYPED_MAX (the form's clean_ni_number normalises it, and the
    model's own validator and max_length then check what is stored)."""
    from django.core.validators import MaxLengthValidator

    f = form.fields[field]
    f.max_length = TYPED_MAX
    f.validators = [v for v in f.validators if not isinstance(v, MaxLengthValidator)]
    f.validators.append(MaxLengthValidator(TYPED_MAX))
    f.widget.attrs["maxlength"] = str(TYPED_MAX)
