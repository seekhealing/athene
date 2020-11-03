from ckeditor.fields import RichTextField
from django import template
from django.db import models
from django.utils import timezone

from seekers.models import Human, HumanMixin

EXTRACARE_STATUS = [("active", "Active"), ("inactive", "Inactive"), ("complete", "Complete")]


class ExtraCare(HumanMixin, models.Model):
    human = models.OneToOneField(Human, primary_key=True, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=EXTRACARE_STATUS, default="inactive")

    class Meta:
        verbose_name = "Extra Care participant"


class ExtraCareNote(models.Model):
    extracare = models.ForeignKey(ExtraCare, on_delete=models.CASCADE)
    created = models.DateTimeField(auto_now_add=True)
    added_by = models.ForeignKey("auth.User", on_delete=models.SET_NULL, editable=False, null=True)
    note = RichTextField()

    STR_TEMPLATE = template.Template('{{ timestamp|date:"DATETIME_FORMAT" }} by {{ added_by|default:"Athene" }}')

    def __str__(self):
        return self.STR_TEMPLATE.render(template.Context(dict(timestamp=self.created, added_by=self.added_by)))

    class Meta:
        ordering = ("-created",)
        verbose_name = "Note"


class ExtraCareBenefitType(models.Model):
    name = models.CharField(max_length=120)
    default_cost = models.DecimalField(decimal_places=2, max_digits=5, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ("name",)
        verbose_name = "Extra Care benefit type"


class ExtraCareBenefit(models.Model):
    extracare = models.ForeignKey(ExtraCare, on_delete=models.CASCADE)
    benefit_type = models.ForeignKey(ExtraCareBenefitType, on_delete=models.CASCADE)
    cost = models.DecimalField(decimal_places=2, max_digits=5)
    date = models.DateField()

    def __str__(self):
        return f"{self.extracare} @ {self.benefit_type} on {self.date}"

    class Meta:
        ordering = ("-date",)


# A proxy model to register a special admin class just for managing ECP benefits
class ExtraCareBenefitProxy(ExtraCare):
    def this_month(self):
        qs = self.extracarebenefit_set.filter(date__month=timezone.now().month).select_related()
        result = qs.aggregate(total_cost=models.Sum("cost"))
        return result["total_cost"]

    def all_time(self):
        qs = self.extracarebenefit_set.all().select_related()
        result = qs.aggregate(total_cost=models.Sum("cost"))
        return result["total_cost"]

    class Meta:
        proxy = True
        verbose_name = "Extra Care benefit report"
