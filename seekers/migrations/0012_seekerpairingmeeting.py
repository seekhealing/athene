# Generated by Django 2.2.2 on 2019-06-25 23:47

from django.db import migrations, models
import django.db.models.deletion
import seekers.models


class Migration(migrations.Migration):

    dependencies = [
        ("seekers", "0011_auto_20190625_1925"),
    ]

    operations = [
        migrations.CreateModel(
            name="SeekerPairingMeeting",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("meeting_date", models.DateField(default=seekers.models.today)),
                ("comment", models.CharField(max_length=200)),
                (
                    "seeker_pairing",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="seekers.SeekerPairing"),
                ),
            ],
            options={"ordering": ["-meeting_date"],},
        ),
    ]
