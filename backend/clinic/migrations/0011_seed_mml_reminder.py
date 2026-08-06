import datetime

from django.db import migrations


def add_mml_reminder(apps, schema_editor):
    Reminder = apps.get_model("clinic", "Reminder")
    if Reminder.objects.filter(title="Weekly MML order (Part 1 & 2)").exists():
        return
    Reminder.objects.create(
        title="Weekly MML order (Part 1 & 2)",
        message="Prepare and send this week's MML Part 1 and MML Part 2 to "
                "Disposables & Supplies (orders are for the Tuesday team).",
        frequency="weekly",
        weekday=5,  # Saturday
        at_time=datetime.time(8, 0),
        active=True,
        action_url="/ordering/",
        action_label="Open Ordering Forms",
        created_by="system",
    )


def remove_mml_reminder(apps, schema_editor):
    Reminder = apps.get_model("clinic", "Reminder")
    Reminder.objects.filter(title="Weekly MML order (Part 1 & 2)").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("clinic", "0010_reminder"),
    ]

    operations = [
        migrations.RunPython(add_mml_reminder, remove_mml_reminder),
    ]
