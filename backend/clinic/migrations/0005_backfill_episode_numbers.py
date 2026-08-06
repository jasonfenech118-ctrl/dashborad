"""Give any pre-existing episodes and encounters their reference numbers."""

from django.db import migrations


def backfill(apps, schema_editor):
    CarePathway = apps.get_model("clinic", "CarePathway")
    PathwayEvent = apps.get_model("clinic", "PathwayEvent")

    counters = {}
    for pathway in CarePathway.objects.filter(
        episode_number__isnull=True
    ).order_by("created_at"):
        year = (pathway.created_at or pathway.updated_at).year
        counters[year] = counters.get(year, 0) + 1
        pathway.episode_number = f"EP-{year}-{counters[year]:04d}"
        pathway.save(update_fields=["episode_number"])

    for pathway in CarePathway.objects.all():
        seq = 0
        for event in PathwayEvent.objects.filter(pathway_id=pathway.id).order_by(
            "event_date", "created_at"
        ):
            seq += 1
            event.sequence = seq
            event.encounter_number = f"{pathway.episode_number or 'EP'}-{seq:02d}"
            event.save(update_fields=["sequence", "encounter_number"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("clinic", "0004_alter_pathwayevent_options_and_more"),
    ]

    operations = [
        migrations.RunPython(backfill, noop),
    ]
