from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("control_center", "0007_managedorganization_superadmin_email_and_reset_token"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedorganization",
            name="portal_api_base_url",
            field=models.URLField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="syncdeliveryjob",
            name="base_url",
            field=models.URLField(blank=True, default=""),
        ),
    ]
