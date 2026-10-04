from people.models import PositionTitle


def get_or_create(name):
    """The title row for `name`, exact match, created if missing."""
    name = (name or "").strip()
    if not name:
        raise ValueError("a title needs a name")
    title, _ = PositionTitle.objects.get_or_create(name=name)
    return title
