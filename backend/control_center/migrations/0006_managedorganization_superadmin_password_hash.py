from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("control_center", "0005_managedorganization_superadmin_username"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedorganization",
            name="superadmin_password_hash",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
