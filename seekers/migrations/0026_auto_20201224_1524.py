# Generated by Django 3.1.2 on 2020-12-24 20:24

from django.db import migrations, models

DEFAULT_NEEDS = [
    "Herbal First Aid",
    "Naloxone",
    "Just checkin’ in — calls",
    "Just checkin’ in — texts",
    "Meal delivery",
    "Meeting buddy",
    "Help with errands",
]


def boolean_to_m2m(apps, schema_editor):
    SeekerNeedType = apps.get_model("seekers", "SeekerNeedType")
    for need in DEFAULT_NEEDS:
        SeekerNeedType.objects.create(need=need)
    needs = SeekerNeedType.objects.all()
    Seeker = apps.get_model("seekers", "Seeker")
    for seeker in Seeker.objects.filter(needs_connection=True):
        for need in needs:
            seeker.needs.add(need)


def m2m_to_boolean(apps, schema_editor):
    Seeker = apps.get_model("seekers", "Seeker")
    Seeker.objects.filter(needs__isnull=False).update(needs_connection=True)


class Migration(migrations.Migration):

    dependencies = [
        ("seekers", "0025_auto_20201029_1538"),
    ]

    operations = [
        migrations.CreateModel(
            name="SeekerNeedType",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("need", models.CharField(max_length=40, unique=True)),
            ],
            options={"ordering": ["need",],},
        ),
        migrations.AddField(
            model_name="seeker",
            name="needs",
            field=models.ManyToManyField(blank=True, null=True, to="seekers.SeekerNeedType"),
        ),
        migrations.RunPython(boolean_to_m2m, m2m_to_boolean),
        migrations.RemoveField(model_name="seeker", name="needs_connection",),
    ]