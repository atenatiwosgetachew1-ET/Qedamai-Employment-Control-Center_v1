from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("control_center", "0006_managedorganization_superadmin_password_hash"),
    ]

    operations = [
        migrations.AddField(
            model_name="managedorganization",
            name="superadmin_email",
            field=models.EmailField(blank=True, default="", max_length=254),
        ),
        migrations.CreateModel(
            name="OrganizationPasswordResetToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.CharField(max_length=64, unique=True)),
                ("delivery_email", models.EmailField(blank=True, default="", max_length=254)),
                ("created_by_username", models.CharField(blank=True, default="", max_length=150)),
                ("expires_at", models.DateTimeField()),
                ("used_at", models.DateTimeField(blank=True, null=True)),
                ("email_sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_delivery_error", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "organization",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="password_reset_tokens", to="control_center.managedorganization"),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
