import functools
import operator

from dateutil.relativedelta import relativedelta

from .models import ProgressEvent
from .constants import INTAKE_EVENTS, PROGRAM_EVENTS, RELEASE_EVENTS


def extra_care_flow(extracare):
    if extracare.pk:
        events = ProgressEvent.objects.filter(
            extracare=extracare, program_flow=extracare.current_program_flow, complete=True,
        )
    else:
        events = []

    # Intake events can happen in any order, but there must be at least one
    # of each completed before the last one (index -1) can be completed. After
    # that last one is completed, no other intake event can occur.
    intake_events_remaining = functools.reduce(operator.add, [[event] * count for event, count in INTAKE_EVENTS])
    for event in events:
        if event.event_type in intake_events_remaining:
            intake_events_remaining.remove(event.event_type)
    if INTAKE_EVENTS[-1][0] in intake_events_remaining:
        return intake_events_remaining, "intake", lambda date: True

    # If the final intake step occurred in the first 7 days of the month, then
    # the program events can begin this month. Otherwise, they begin next month.
    final_intake = [e for e in events if e.event_type == INTAKE_EVENTS[-1][0]][0]
    final_intake_date = final_intake.occurred or final_intake.excused
    if final_intake_date.day <= 7:
        program_start = final_intake_date.replace(day=1)
    else:
        program_start = (final_intake_date + relativedelta(months=+1)).replace(day=1)

    # The program lasts six months. You must complete all events of a given month
    # before you can even schedule the events of the next month. The dates for the
    # program events have to be in the proper month.
    for month in [program_start + relativedelta(months=i) for i in range(6)]:
        month_end = month + relativedelta(months=+1, days=-1)
        program_events_remaining = functools.reduce(operator.add, [[event] * count for event, count in PROGRAM_EVENTS])
        for event in [e for e in events if month <= (e.occurred or e.excused) <= month_end]:
            if event.event_type in program_events_remaining:
                program_events_remaining.remove(event.event_type)
        if program_events_remaining:
            return program_events_remaining, "program", lambda date: month <= date <= month_end

    # Release events can happen in any order, but once they're all complete,
    # the seeker has completed the program.
    release_events_remaining = functools.reduce(operator.add, [[event] * count for event, count in RELEASE_EVENTS])
    for event in events:
        if event.event_type in release_events_remaining:
            release_events_remaining.remove(event.event_type)
    return release_events_remaining, "release", lambda date: True


def validate_extra_care_flow(extracare, datasets):
    event_types, _, date_fn = extra_care_flow(extracare)
    for dataset in datasets:
        # Make sure the event types given are valid and in the right quantity
        if dataset["event_type"] not in event_types:
            return f'Event type {dataset["event_type"]} not valid here.'
        event_types.remove(dataset["event_type"])
        # Make sure dates given fall in the correct month
        for field in ["scheduled", "occurred", "excused"]:
            if dataset[field] and not date_fn(dataset[field]):
                return f"Invalid {field} date - it falls outside of program guidelines for monthly sessions"
        # If the final intake event is being presented here, make sure that
        # at least one instance of each intake event is complete too
        if dataset["event_type"] == INTAKE_EVENTS[-1][0] and (dataset["occurred"] or dataset["excused"]):
            intake_event_types = [p[0] for p in INTAKE_EVENTS]
            completed_intake_events = (
                ProgressEvent.objects.filter(
                    extracare=extracare,
                    program_flow=extracare.current_program_flow,
                    complete=True,
                    event_type__in=intake_event_types,
                )
                .values_list("event_type", flat=True)
                .distinct()
            )
            dataset_intake_events = [
                ds["event_type"]
                for ds in datasets
                if ds["event_type"] in intake_event_types and (ds["occurred"] or ds["excused"])
            ]
            for event_type in intake_event_types:
                if event_type not in completed_intake_events and event_type not in dataset_intake_events:
                    return "Cannot complete intake until all phases are complete."
