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

You will need a config file in this format

```python
# config.py

class Config:
    SECRET_KEY = 'secretkey'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email settings
    MAIL_SERVER = '{{mail server}}'
    MAIL_PORT = {{port}}
    MAIL_USE_TLS = True  # if mail server uses TLS
    MAIL_USE_SSL = False  # if required
    MAIL_USERNAME = '{{email@address.com}}'
    MAIL_PASSWORD = '{{email password or app password}}'
    MAIL_DEFAULT_SENDER = ('Sender Name', 'sender@email.com')  # must be a tuple

    # MySQL connection details
    DB_HOST = '127.0.0.1'
    DB_USER = 'db user'
    DB_PASSWORD = 'dbpass'
    DB_NAME = 'database name'
    DB_PORT = 3306  # or your MySQL port
    SQLALCHEMY_DATABASE_URI = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}'

    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_timeout": 30,
        "pool_size": 10,
        "max_overflow": 5
    }
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

