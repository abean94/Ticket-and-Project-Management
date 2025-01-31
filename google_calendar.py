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

BASE_DIR = "/home/andrewbean94/Ticket-and-Project-Management"  # Adjust this to match your directory
TOKEN_PATH = os.path.join(BASE_DIR, "token.pickle")
CLIENT_SECRET_PATH = os.path.join(BASE_DIR, "client_secret_634441787369-rst6o54jsg9t6tkkc1t5huvnl44fgka9.apps.googleusercontent.com.json")  # Rename your client secret file


def get_calendar_service():
    creds = None
    token_path = r'C:\Users\andre\OneDrive - RVA IT Pros\Documents\Work\Ticket and Project Management\token.pickle'

    # Load credentials if previously saved
    if os.path.exists(TOKEN_PATH):
        with open(TOKEN_PATH, 'rb') as token:
            creds = pickle.load(token)

    # Refresh expired credentials
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    # If still not valid, re-authenticate
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            CLIENT_SECRET_PATH,
            SCOPES,
            redirect_uri='https://tickets.rvaitpros.com/oauth2callback'
        )
        creds = flow.run_console()  # Use console-based authentication instead of localhost


        # Save the new credentials
        with open(TOKEN_PATH, 'wb') as token:
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
    print(f'Event created: {event.get('htmlLink')}')



