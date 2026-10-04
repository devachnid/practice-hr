"""The only writer of File rows and the only reader of their bytes.

A file's bytes are reached through open() and nothing else: it applies
access.can_view_file and writes the "viewed" audit row. MEDIA_ROOT is never
served (config/urls.py maps no MEDIA_URL). Stored paths are opaque
(documents/<year>/<uuid4 hex>.<ext>), never derived from the upload's name,
and the extension comes from what the bytes were sniffed to be."""
import hashlib
import unicodedata
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import FileResponse
from django.utils import timezone

from documents.models import File
from people.services import access, audit

TYPES = {  # sniffed kind -> (extension, content type)
    "pdf": ("pdf", "application/pdf"),
    "jpeg": ("jpg", "image/jpeg"),
    "png": ("png", "image/png"),
    "docx": ("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}
BY_EXTENSION = {"pdf": "pdf", "jpg": "jpeg", "jpeg": "jpeg", "png": "png", "docx": "docx"}
LABEL = {"pdf": "PDF", "jpeg": "JPEG", "png": "PNG", "docx": "DOCX"}
ROOT = "documents"
MB = 1024 * 1024
ADDED_HOOKS = []           # callables(file) run after add() has saved and audited, in its transaction


def _limit():
    limit = settings.DOCUMENT_MAX_BYTES
    return f"{limit // MB} MB" if limit >= MB and limit % MB == 0 else f"{limit} bytes"


def _too_big():
    return ValidationError(f"That file is bigger than {_limit()}.")


def _is_docx(upload):
    """A zip holding [Content_Types].xml and a word/ part. Only the central
    directory is read; nothing is decompressed."""
    try:
        with zipfile.ZipFile(upload) as z:
            names = z.namelist()
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, ValueError, EOFError):
        return False
    finally:
        upload.seek(0)
    return "[Content_Types].xml" in names and any(n.startswith("word/") for n in names)


def sniff(upload):
    """What the bytes are, or ValidationError. The extension says what the
    file claims to be; the bytes must agree."""
    ext = PurePosixPath(upload.name or "").suffix.lower().lstrip(".")
    claimed = BY_EXTENSION.get(ext)
    if claimed is None:
        raise ValidationError("Upload a PDF, JPEG, PNG or DOCX file.")
    if upload.size > settings.DOCUMENT_MAX_BYTES:
        raise _too_big()
    upload.seek(0)
    head = upload.read(8)
    upload.seek(0)
    actual = None
    if head.startswith(b"%PDF-"):
        actual = "pdf"
    elif head.startswith(b"\xff\xd8\xff"):
        actual = "jpeg"
    elif head.startswith(b"\x89PNG\r\n\x1a\n"):
        actual = "png"
    elif head.startswith(b"PK") and _is_docx(upload):
        actual = "docx"
    if actual != claimed:
        raise ValidationError(f"This file is not a {LABEL[claimed]}.")
    return actual


def _original_name(name, kind):
    """The name the download is offered under: the upload's own, without
    any directory part or control characters, at most 200 characters with
    its extension kept."""
    name = "".join(c for c in PurePosixPath((name or "").replace("\\", "/")).name
                   if not unicodedata.category(c).startswith("C")).strip()
    if not name:
        return f"document.{TYPES[kind][0]}"
    if len(name) > 200:
        suffix = PurePosixPath(name).suffix[:20]
        name = name[:200 - len(suffix)] + suffix
    return name


def _absolute(rel):
    """The file under MEDIA_ROOT/documents, or PermissionDenied for a path
    that would lead anywhere else."""
    base = (Path(settings.MEDIA_ROOT) / ROOT).resolve()
    target = (Path(settings.MEDIA_ROOT) / rel).resolve()
    if not target.is_relative_to(base):
        raise PermissionDenied
    return target


def _store(upload, kind):
    """Write the bytes under a fresh opaque name; (path, sha256, size). On
    any failure the partial file is removed."""
    rel = str(PurePosixPath(ROOT) / str(timezone.localdate().year) / f"{uuid.uuid4().hex}.{TYPES[kind][0]}")
    target = _absolute(rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("xb") as out:
            for chunk in upload.chunks():
                size += len(chunk)
                if size > settings.DOCUMENT_MAX_BYTES:
                    raise _too_big()
                digest.update(chunk)
                out.write(chunk)
    except BaseException:
        target.unlink(missing_ok=True)
        raise
    return rel, digest.hexdigest(), size


def add(actor, employee, category, title, upload, hr_only=False):
    """Check the upload (type, size, sniffed content) and the row, then
    write the bytes, the row and the audit, and run ADDED_HOOKS (a linked
    checklist item closing). A refusal at any point, a hook's included,
    leaves nothing on disk."""
    kind = sniff(upload)
    f = File(employee=employee, category=category, title=title, original_name=_original_name(upload.name, kind),
             content_type=TYPES[kind][1], size=upload.size, uploaded_by=actor, hr_only=hr_only)
    f.full_clean(exclude=["path", "sha256"])
    f.path, f.sha256, f.size = _store(upload, kind)
    try:
        with transaction.atomic():
            f.save()
            audit.record(actor, f, {"added": ("", f"{f.get_category_display()}: {title}")})
            # inside the block: a hook that raises takes the row and the bytes with it
            for hook in ADDED_HOOKS:
                hook(f)
    except BaseException:
        _absolute(f.path).unlink(missing_ok=True)
        raise
    return f


@transaction.atomic
def supersede(actor, file, by, note):
    """Mark `file` replaced by `by`, keeping both. The row is re-read under
    a lock so two concurrent calls cannot both succeed; the caller's
    instance is updated to match."""
    locked = File.objects.select_for_update().get(pk=file.pk)
    if locked.superseded_by_id:
        raise ValidationError("Already superseded.")
    if by.pk == locked.pk or by.employee_id != locked.employee_id:
        raise ValidationError("A file is superseded by another file of the same person.")
    note = note[:200]
    for f in (locked, file):
        f.superseded_by, f.superseded_note = by, note
    locked.save(update_fields=["superseded_by", "superseded_note"])
    audit.record(actor, locked, {"superseded_by": ("", by.pk)}, note=note)
    return file


def open(actor, file):  # the service's verb; this module never needs the builtin
    """The access rule, the audit row, the bytes. Every download uses this."""
    if not access.can_view_file(actor, file):
        raise PermissionDenied
    handle = _absolute(file.path).open("rb")
    try:
        audit.viewed(actor, file, "file")
    except BaseException:
        handle.close()
        raise
    return FileResponse(handle, content_type=file.content_type, as_attachment=True, filename=file.original_name)
