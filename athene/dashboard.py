from admin_tools.dashboard import modules, Dashboard

HUMAN_LIST = modules.ModelList(
    title="Human beings", models=("seekers.models.Human", "seekers.models.Seeker", "seekers.models.CommunityPartner",),
)

CLINICAL_LIST = modules.ModelList(
    title="Extra care program",
    models=("clinical.models.ExtraCare", "clinical.models.ConnectionAgent", "clinical.models.ExtraCareBenefitType"),
)

PROGRAM_MANAGEMENT_LIST = modules.ModelList(
    title="Program management",
    models=("seekers.models.SeekerPairing", "events.models.HumanAttendance", "clinical.models.ExtraCareBenefitProxy"),
)

ATHENE_SETUP_LIST = modules.ModelList(
    title="Athene setup",
    models=(
        "events.models.Calendar",
        "seekers.models.SeekerNeedType",
        "clinical.models.ExtraCareBenefitType",
        "seekers.models.CommunityPartnerService",
    ),
)

DJANGO_SETUP_LIST = modules.ModelList(title="Django setup", models=("django.contrib.*",))


class AtheneDashboard(Dashboard):
    title = "Welcome to Athene!"
    children = [HUMAN_LIST, CLINICAL_LIST, PROGRAM_MANAGEMENT_LIST, ATHENE_SETUP_LIST, DJANGO_SETUP_LIST]
