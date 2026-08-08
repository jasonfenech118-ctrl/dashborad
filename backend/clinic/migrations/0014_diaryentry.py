import datetime
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clinic", "0013_seed_roster_staff"),
    ]

    operations = [
        migrations.CreateModel(
            name="DiaryEntry",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("entry_date", models.DateField(default=datetime.date.today)),
                ("title", models.CharField(blank=True, max_length=200, null=True)),
                ("body", models.TextField()),
                ("created_by", models.CharField(blank=True, max_length=200, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "diary_entries",
                "ordering": ["-entry_date", "-created_at"],
                "managed": True,
            },
        ),
    ]
