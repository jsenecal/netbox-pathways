from django.db import migrations, models


def copy_attachment_height_to_both_sides(apps, schema_editor):
    """Forward: copy the single attachment_height value into both per-side fields."""
    AerialSpan = apps.get_model("netbox_pathways", "AerialSpan")
    qs = AerialSpan.objects.exclude(attachment_height__isnull=True)
    for span in qs:
        span.start_attachment_height = span.attachment_height
        span.end_attachment_height = span.attachment_height
        span.save(update_fields=["start_attachment_height", "end_attachment_height"])


def copy_start_attachment_height_back(apps, schema_editor):
    """Reverse: copy start_attachment_height back into the restored attachment_height column.

    The end side is dropped because the pre-migration schema cannot represent it. This
    reverse path is for developer downgrades only, not production.
    """
    AerialSpan = apps.get_model("netbox_pathways", "AerialSpan")
    qs = AerialSpan.objects.exclude(start_attachment_height__isnull=True)
    for span in qs:
        span.attachment_height = span.start_attachment_height
        span.save(update_fields=["attachment_height"])


class Migration(migrations.Migration):
    dependencies = [
        ("netbox_pathways", "0016_cablesegment_lashed_with"),
    ]

    operations = [
        migrations.AddField(
            model_name="aerialspan",
            name="start_attachment_height",
            field=models.FloatField(
                blank=True,
                help_text="Attachment height at the start endpoint, in meters",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="aerialspan",
            name="end_attachment_height",
            field=models.FloatField(
                blank=True,
                help_text="Attachment height at the end endpoint, in meters",
                null=True,
            ),
        ),
        migrations.RunPython(
            copy_attachment_height_to_both_sides,
            copy_start_attachment_height_back,
        ),
        migrations.RemoveField(
            model_name="aerialspan",
            name="attachment_height",
        ),
    ]
