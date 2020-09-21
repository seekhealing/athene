from admin_tools.dashboard import modules, Dashboard

HUMAN_MODEL_LIST = modules.ModelList(
    title="Human beings", models=("seekers.models.Human", "seekers.models.Seeker", "seekers.models.CommunityPartner")
)

PROGRAM_MANAGEMENT_LIST = modules.ModelList(
    title="Program management",
    models=("seekers.models.SeekerPairing", "events.models.HumanAttendance", "seekers.models.SeekerBenefitProxy"),
)

ATHENE_SETUP_LIST = modules.ModelList(
    title="Athene setup", models=("events.models.Calendar", "seekers.models.SeekerBenefitType")
)

DJANGO_SETUP_LIST = modules.ModelList(title="Django setup", models=("django.contrib.*",))


class AtheneDashboard(Dashboard):
    title = "Welcome to Athene!"
    children = [HUMAN_MODEL_LIST, PROGRAM_MANAGEMENT_LIST, ATHENE_SETUP_LIST, DJANGO_SETUP_LIST]
