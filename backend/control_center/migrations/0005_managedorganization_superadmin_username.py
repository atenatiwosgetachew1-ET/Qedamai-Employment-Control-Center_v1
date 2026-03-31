from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("control_center", "0004_syncdeliveryjob"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedorganization",
            name="superadmin_username",
            field=models.CharField(blank=True, default="", max_length=150),
        ),
    ]
