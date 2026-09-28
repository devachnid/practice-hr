from absence.models import AbsenceType


def test_seeded_types(db):
    codes = set(AbsenceType.objects.values_list("code", flat=True))
    assert {"AL", "BH", "STUDY", "TOIL", "SICK", "MAT", "PAT", "SPL", "ADOPT", "COMP", "DEP",
            "UNPAID", "OTHER"} <= codes
    al = AbsenceType.objects.get(code="AL")
    assert al.uses_pot and al.needs_approval and al.paid and al.calendar_label == "Leave"
    sick = AbsenceType.objects.get(code="SICK")
    assert not sick.uses_pot and not sick.needs_approval and sick.self_certified
    assert sick.health_sensitive and sick.calendar_label == "Sick"
    dep = AbsenceType.objects.get(code="DEP")
    assert not dep.paid and not dep.uses_pot and not dep.needs_approval
