# Generated by Django 2.2.14 on 2020-07-03 23:45

from django.db import migrations


def cleanup_contact_preference(apps, schema_editor):
    Human = apps.get_model("seekers", "Human")
    for human in Human.objects.all():
        subs = human.humancalendarsubscription_set.all()
        if subs:
            human.contact_preference = subs[0].contact_method
        elif not human.contact_preference:
            human.contact_preference = 2
        elif human.contact_preference > 2:
            if human.phone_number:
                human.contact_preference = 2
            elif human.email:
                human.contact_preference = 1
            else:
                human.contact_preference = 2
        human.save()


class Migration(migrations.Migration):

    dependencies = [
        ("seekers", "0015_seeker_enroll_date"),
    ]

    operations = [migrations.RunPython(cleanup_contact_preference)]
