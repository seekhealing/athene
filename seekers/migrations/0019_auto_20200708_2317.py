# Generated by Django 2.2.14 on 2020-07-09 03:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("seekers", "0018_human_send_replies_to_channel"),
    ]

    operations = [
        migrations.AddField(model_name="seeker", name="admin_human", field=models.BooleanField(default=False),),
        migrations.AddField(model_name="seeker", name="creative_human", field=models.BooleanField(default=False),),
        migrations.AddField(model_name="seeker", name="needs_connection", field=models.BooleanField(default=False),),
    ]