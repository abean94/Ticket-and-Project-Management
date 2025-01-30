from __future__ import print_function
import datetime
import os
import pickle
import sys

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define the scopes required for Google Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_calendar_service():
    creds = None
    
    # Load credentials if previously saved
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # If no credentials are found or they are invalid, request new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('client_secret_634441787369-rst6o54jsg9t6tkkc1t5huvnl44fgka9.apps.googleusercontent.com.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next time
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('calendar', 'v3', credentials=creds)

def create_event(summary, start_time, end_time, description='', location=''):
    service = get_calendar_service()
    event = {
        'summary': summary,
        'location': location,
        'description': description,
        'start': {'dateTime': start_time, 'timeZone': 'America/New_York'},
        'end': {'dateTime': end_time, 'timeZone': 'America/New_York'},
        'reminders': {
            'useDefault': False,
            'overrides': [
                {'method': 'email', 'minutes': 24 * 60},
                {'method': 'popup', 'minutes': 10},
            ],
        },
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f'Event created: {event.get("htmlLink")}')



