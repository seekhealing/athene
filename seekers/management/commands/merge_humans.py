from django.core.management.base import BaseCommand
from django.db import transaction

from seekers import models


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("human_ids", nargs=2)

    def merge_objects(self, model, target, source):
        for field in model._meta.fields:
            field_name = field.attname
            if getattr(source, field_name) and not getattr(target, field_name):
                val = getattr(source, field_name)
                print(f"Copying value on {model._meta.verbose_name} for {field_name}: {val}")
                setattr(target, field_name, val)
        target.save()

    def move_related_objects(self, qs, fk_attr, target):
        if qs.count():
            print(f"Updating {fk_attr} on {qs.model._meta.verbose_name_plural}")
            qs.update(**{fk_attr: target})

    @transaction.atomic()
    def handle(self, *args, **options):
        source, target = models.Human.objects.filter(id__in=options["human_ids"]).order_by("created")
        print(f"Merging {source} ({source.id}) into {target} ({target.id})")
        _ = input("Okay? Press enter.")
        self.merge_objects(models.Human, target, source)
        self.move_related_objects(source.humannote_set.all(), "human", target)
        self.move_related_objects(source.humancalendarsubscription_set.all(), "human", target)
        self.move_related_objects(source.humanattendance_set.all(), "human", target)

        try:
            source_seeker = source.seeker
        except models.Seeker.DoesNotExist:
            pass
        else:
            try:
                target_seeker = target.seeker
            except models.Seeker.DoesNotExist:
                target_seeker = target.upgrade_to_seeker()
            self.merge_objects(models.Seeker, target_seeker, source_seeker)
            self.move_related_objects(source_seeker.left_pair.all(), "left", target_seeker)
            self.move_related_objects(source_seeker.righ_pair.all(), "right", target_seeker)
            self.move_related_objects(source_seeker.seekermilestone_set.all(), "seeker", target_seeker)
            self.move_related_objects(source_seeker.seekerbenefit_set.all(), "seeker", target_seeker)

        try:
            source_cp = source.communitypartner
        except models.CommunityPartner.DoesNotExist:
            pass
        else:
            try:
                target_cp = target.communityparter
            except models.CommunityPartner.DoesNotExist:
                target_cp = target.mark_as_community_partner()
            self.merge_objects(models.CommunityPartner, target_cp, source_cp)
        source.delete()
