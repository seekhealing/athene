import base64
import datetime
import json
import os
import pickle

from googleapiclient.discovery import build
from googleapiclient import errors
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from pytz import utc

class Calendar(object):
    def __init__(self):
        if os.environ.get('GOOGLE_TOKEN'):
            self.token = pickle.loads(base64.decodebytes(os.environ['GOOGLE_TOKEN']))
        else:
            token_file = os.path.join(os.path.dirname(__file__), 'token.pickle')
            self.token = pickle.load(open(token_file, 'rb'))
        if not self.token or not self.token.valid:
            if self.token and self.token.expired and self.token.refresh_token:
                self.token.refresh(Request())
            else:
                raise ValueError('Token is not valid.')
        self.service = build('calendar', 'v3', credentials=self.token)
    
    def get_calendar(self, calendar_id):
        try:
            result = self.service.calendars().get(calendarId=calendar_id).execute()
        except errors.HttpError as e:
            raise ValueError(f'Invalid calendar ID reference: {e.args}')
        return result
    
    def get_event(self, calendar_id, event_id):
        try:
            result = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        except errors.HttpError as e:
            raise ValueError(f'Invalid event ID reference: {e.args}')
        return result
    
    def get_recurring_events(self, calendar_id, recurring_event_id, start_dt=None, count=25):
        time_min = start_dt.astimezone(utc).replace(tzinfo=None).isoformat() + 'Z' if start_dt else None        
        try:
            result = self.service.events().instances(calendarId=calendar_id,
                                                     eventId=recurring_event_id,
                                                     timeMin=time_min,
                                                     maxResults=count
                                                     ).execute()
        except errors.HttpError as e:
            raise ValueError(f'Invalid recurring event lookup: {e.args}')
        return result.get('items', [])

    def get_upcoming_events(self, calendar_id, start_dt=None, end_dt=None, count=25):
        if start_dt is None:
            start_dt = datetime.datetime.utcnow()
        else:
            if start_dt.tzinfo is not None:
                start_dt = start_dt.astimezone(utc)
                start_dt = start_dt.replace(tzinfo=None)
        time_min = start_dt.isoformat() + 'Z'
        time_max = end_dt.astimezone(utc).replace(tzinfo=None).isoformat() + 'Z' if end_dt else None
        try:
            result = self.service.events().list(calendarId=calendar_id,
                                                timeMin=time_min,
                                                timeMax=time_max,
                                                maxResults=count,
                                                singleEvents=True,
                                                orderBy='startTime').execute()
        except errors.HttpError as e:
            raise ValueError(f'Invalid event lookup: {e.args}')
        return result.get('items', [])




client = Calendar()
