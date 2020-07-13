# Generated by Django 2.1.7 on 2019-03-27 13:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("seekers", "0007_auto_20190326_1150"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="human", options={"ordering": ["first_names", "last_names"], "verbose_name": "Prospect"},
        ),
        migrations.AddField(
            model_name="seeker",
            name="connection_agent_organization",
            field=models.CharField(blank=True, max_length=120),
        ),
    ]
