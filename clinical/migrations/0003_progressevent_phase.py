# Generated by Django 3.1.2 on 2020-11-11 16:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clinical", "0002_auto_20201110_1049"),
    ]

    operations = [
        migrations.AddField(
            model_name="progressevent",
            name="phase",
            field=models.CharField(default="", max_length=20),
            preserve_default=False,
        ),
    ]