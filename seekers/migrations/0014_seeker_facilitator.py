# Generated by Django 2.2.2 on 2019-07-25 02:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('seekers', '0013_human_first_conversation'),
    ]

    operations = [
        migrations.AddField(
            model_name='seeker',
            name='facilitator',
            field=models.BooleanField(default=False),
        ),
    ]