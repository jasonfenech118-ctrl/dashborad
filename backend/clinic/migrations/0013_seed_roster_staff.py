from django.db import migrations


CORE = [
    ("Jacqueline Sammut", "Practice Nurse"),
    ("Jason Fenech", "Practice Nurse"),
    ("Lorraine Stivala", "Staff Nurse"),
    ("Erika Psaila", "Senior Staff Nurse"),
]
OVERTIME = [
    ("Tracey Galea", "OT Nurse"),
    ("Katrina Gauci", "OT Nurse"),
]


def add_staff(apps, schema_editor):
    RosterStaff = apps.get_model("clinic", "RosterStaff")
    if RosterStaff.objects.exists():
        return
    order = 0
    for name, role in CORE:
        RosterStaff.objects.create(full_name=name, role=role, category="core",
                                   display_order=order, active=True)
        order += 1
    order = 0
    for name, role in OVERTIME:
        RosterStaff.objects.create(full_name=name, role=role, category="overtime",
                                   display_order=order, active=True)
        order += 1


def remove_staff(apps, schema_editor):
    RosterStaff = apps.get_model("clinic", "RosterStaff")
    names = [n for n, _ in CORE + OVERTIME]
    RosterStaff.objects.filter(full_name__in=names).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("clinic", "0012_rosterstaff_rostershift"),
    ]

    operations = [
        migrations.RunPython(add_staff, remove_staff),
    ]
