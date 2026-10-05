"""The message an admin reads after a password link is sent (the Login
accounts page and the employee add page both send one)."""

from django.contrib import messages
from django.utils.html import format_html


def report_send(request, user, result, *, invite, to=None):
    """The three outcomes of a send, as the message the admin reads. A link
    is shown here, once, and nowhere else. `to` names the address when it
    was not the account's own (an invitation sent to a personal email)."""
    what = "Invitation" if invite else "Password-reset link"
    address = to or user.email
    if result is None:
        messages.success(request, f"{what} sent to {address}.")
    elif not result.reason:
        messages.warning(request, format_html(
            "Email isn't set up — copy this link and send it to {} yourself: "
            '<a href="{}">{}</a>', address, result.link, result.link))
    else:
        messages.error(request, format_html(
            "Sending to {} failed ({}) — copy this link and send it yourself: "
            '<a href="{}">{}</a>', address, result.reason, result.link, result.link))
