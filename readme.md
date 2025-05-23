# Help Desk and Project Ticketing System

## Project Scope
A Flask-based open-source ticketing and project management system built for small MSPs and freelancers, with billing, scheduling, and reporting features.

## Base Features
-Ticket and project tracking
-Daily task planner
-Google Tasks and Calendar integration
-QuickBooks invoice attachment via API
-Role-based login and permission system

## Installation
# Clone the repository
git clone https://github.com/abean94/Ticket-and-Project-Management.git
cd Ticket-and-Project-Management

### Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

### Install dependencies
pip install -r requirements.txt

You will need to create in the project root directory

a config file in this format

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()  # Load environment variables from .env

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER_NAME = os.getenv('MAIL_DEFAULT_SENDER_NAME')
    MAIL_DEFAULT_SENDER_EMAIL = os.getenv('MAIL_DEFAULT_SENDER_EMAIL')
    MAIL_DEFAULT_SENDER = (MAIL_DEFAULT_SENDER_NAME, MAIL_DEFAULT_SENDER_EMAIL) if MAIL_DEFAULT_SENDER_NAME and MAIL_DEFAULT_SENDER_EMAIL else None


    DB_HOST = os.getenv('DB_HOST')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_timeout": 30,
        "pool_size": 10,
        "max_overflow": 5
    }

    CLIENT_SECRET_PATH = os.getenv("CLIENT_SECRET_PATH")
    TOKEN_PATH = os.getenv("TOKEN_PATH")
    CALENDAR_ID = os.getenv("CALENDAR_ID")
    BASE_DIR = os.getenv("BASE_DIR")
    COMPANY_SUPPORT_EMAIL=os.getenv("COMPANY_SUPPORT_EMAIL")
    COMPANY_SUPPORT_PHONE=os.getenv("COMPANY_SUPPORT_PHONE")
    COMPANY_NAME=os.getenv("COMPANY_NAME")
    LOGO_URL = os.getenv("LOGO_URL")
    BRAND_NAME = os.getenv("BRAND_NAME")
    BRAND_LOGO_PATH = os.getenv("BRAND_LOGO_PATH")
```
and an .env file:
```python
# .env
SECRET_KEY = #secretkey
MAIL_SERVER = #mailserver
MAIL_PORT = #mailport
MAIL_USE_TLS= #True or False
MAIL_USE_SSL= #True or False
MAIL_USERNAME =  # Your email address
MAIL_PASSWORD =  # Your email password or app password
MAIL_DEFAULT_SENDER_NAME= #Default sender name
MAIL_DEFAULT_SENDER_EMAIL= #default email address 

DB_HOST= #db host or IP
DB_USER=#db user
DB_PASSWORD= #db password
DB_NAME= #db name
DB_PORT= #db port

CLIENT_SECRET_PATH= #google api client secret.json
TOKEN_PATH= #pickle token path for google integration

CALENDAR_ID= #calendar to write to ID - run list_calendars() in google_calendar.py to get the ID's of all calendars printed out
BASE_DIR = #base directory 
COMPANY_SUPPORT_EMAIL= #support email
COMPANY_SUPPORT_PHONE= #support phone number
COMPANY_NAME= #company name
LOGO_URL = #link to company logo externally hosted for email sending
BRAND_NAME= #brand name
BRAND_LOGO_PATH= #local path to brand image
```


## Database setup

This code initially was built with sqlite but migrated to mysql. Small refractoring needed to utilize postgresql or even back to sqlite

# Create MySQL database
CREATE DATABASE ticketing_db;

# Then run the app to initialize the schema
flask db upgrade

flask run


## Setup Google Calendar
You'll need to follow the steps to enable and get a client secret.json https://developers.google.com/workspace/calendar/api/quickstart/go

