from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Message, Mail
from werkzeug.security import generate_password_hash, check_password_hash
from forms import RegistrationForm, LoginForm, TicketForm, UpdateTicketForm, AddNoteForm, ProjectForm, PhaseForm, SelectProjectForm, SelectPhaseForm, ClientForm, CompanyForm, EditClientForm, EditCompanyForm, ChangeRoleForm, EditNoteForm, UpdateProjectForm, RandomNumberForm
from models import db, User, Ticket, TicketNote, Project, Phase, Client, Company
from datetime import datetime, timezone
from flask_migrate import Migrate
from sqlalchemy import func
from sqlalchemy.sql import text
import pymysql
import random
from io import BytesIO
import pandas as pd
from config import Config
from google_calendar import create_event
from google_auth_oauthlib.flow import Flow
import pickle
from pytz import timezone, UTC
# from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import OperationalError
from dateutil import parser

# db = SQLAlchemy()

app = Flask(__name__)



#configurations
app.config.from_object(Config)


@app.context_processor
def inject_branding():
    return {
        'BRAND_NAME': app.config.get('BRAND_NAME'),
        'BRAND_LOGO_PATH': app.config.get('BRAND_LOGO_PATH')
    }


mail = Mail(app)

# #initialize the database
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


SCOPES = ['https://www.googleapis.com/auth/calendar.events']
CLIENT_SECRET_PATH =  app.config['CLIENT_SECRET_PATH']
TOKEN_PATH =  app.config['TOKEN_PATH']


@app.before_request
def before_request():
    """Ensure MySQL connection is active before processing requests."""
    try:
        with app.app_context():
            db.session.execute(text("SELECT 1"))
    except OperationalError:
        db.session.rollback()

@app.teardown_appcontext
def shutdown_session(exception=None):
    """Ensure databse session is properly closed after each request."""
    db.session.remove()

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

@app.route('/register', methods=['GET', 'POST'])
@login_required
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Login unsuccessful. Please check your username and password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    # Custom ordering for status: Open > In Progress > Closed
    tickets = Ticket.query.filter(
        ~Ticket.status.in_(['Closed'])  # ✅ Corrected
    ).order_by(
        db.case(
            (Ticket.status.in_(['Open', 'In Progress']), 1),
            (Ticket.status == 'Touched', 2),
            (Ticket.status == 'On Hold', 3),
            (Ticket.status == 'Closed', 4),
        ).asc(),
        db.case(
            (Ticket.priority == 'Important-Urgent', 1),
            (Ticket.priority == 'Important-NotUrgent', 2),
            (Ticket.priority == 'NotImportant-Urgent', 3),
            (Ticket.priority == 'NotImportant-NotUrgent', 4),
        ).asc(),
    ).all()

    eastern = timezone('US/Eastern')
    current_time = datetime.now(UTC)

    # ✅ Fix: Handle NULL/Invalid timestamps
    for ticket in tickets:
        if ticket.created_at:
            try:
                # ✅ Convert string timestamps safely
                if isinstance(ticket.created_at, str):
                    if ticket.created_at not in [None, "0000-00-00 00:00:00"]:
                        ticket.created_at = datetime.strptime(ticket.created_at, "%Y-%m-%d %H:%M:%S")
                    else:
                        ticket.created_at = None  # Handle invalid timestamps

                # ✅ Ensure proper timezone conversion
                if ticket.created_at:
                    ticket.created_at = ticket.created_at.replace(tzinfo=UTC).astimezone(eastern)

                    # ✅ Calculate ticket age
                    age = current_time - ticket.created_at.astimezone(UTC)
                    days = age.days
                    hours = age.seconds // 3600  # Get hours from seconds
                    ticket.age = f"{days}d:{hours}h"
                else:
                    ticket.age = "N/A"  # Handle cases with missing timestamps

            except ValueError:
                ticket.created_at = None  # Handle any parsing errors
                ticket.age = "N/A"

    session.pop('start_time_utc', None)
    return render_template('dashboard.html', tickets=tickets)

@app.route('/download_tickets_excel')
@login_required
def download_tickets_excel():
    # Retrieve all the tickets from the database (replace with your actual query)
    # Create a list of dictionaries to store ticket data
    tickets = Ticket.query.filter(
        Ticket.status != 'Closed'
    ).order_by(
        db.case(
            (Ticket.status in ['Open', 'In Progress'], 1),
            (Ticket.status == 'Touched', 2),
            (Ticket.status == 'On Hold', 3),
            (Ticket.status == 'Closed', 4),
        ).asc(),
        db.case(
            (Ticket.priority == 'Important-Urgent', 1),
            (Ticket.priority == 'Important-NotUrgent', 2),
            (Ticket.priority == 'NotImportant-Urgent', 3),
            (Ticket.priority == 'NotImportant-NotUrgent', 4),
        ).asc(),
    ).all()
    ticket_data = []
    for ticket in tickets:
        ticket_data.append({
            'Ticket ID': ticket.id,
            'Subject': ticket.subject,
            'Status': ticket.status,
            'Priority': ticket.priority,
            'Due Date': ticket.due_date.strftime('%Y-%m-%d') if ticket.due_date else None,
            'Estimated Hours': ticket.estimated_hours,
            'Project': ticket.project.name if ticket.project else 'No Project',
            'Phase': ticket.phase.name if ticket.phase else 'No Phase'
        })

    # Create a DataFrame from the ticket data
    df = pd.DataFrame(ticket_data)

    # Create an in-memory output file
    output = BytesIO()

    # Write the DataFrame to an Excel file
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Tickets')

    # Set the output file's position to the beginning
    output.seek(0)

    # Send the file as an attachment to be downloaded by the user
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name='tickets.xlsx')

@app.route('/')
@login_required
def dashboard_today():
    # ✅ Fix: Correct MySQL date filter (Includes today and tomorrow)
    tickets = Ticket.query.filter(
        Ticket.due_date.between(
            func.date(func.now()),
            func.timestampadd(text('SECOND'), 86399, func.date(func.now()))  # ✅ 11:59:59 PM today
        )
    ).order_by(
        db.case(
            (Ticket.status.in_(['Open', 'In Progress']), 1),
            (Ticket.status == 'Touched', 2),
            (Ticket.status == 'On Hold', 3),
            (Ticket.status == 'Closed', 4),
        ).asc(),
        db.case(
            (Ticket.priority == 'Important-Urgent', 1),
            (Ticket.priority == 'Important-NotUrgent', 2),
            (Ticket.priority == 'NotImportant-Urgent', 3),
            (Ticket.priority == 'NotImportant-NotUrgent', 4),
        ).asc(),
    ).all()

    eastern = timezone('US/Eastern')
    current_time = datetime.now(UTC)

    # ✅ Fix: Handle NULL/Invalid timestamps
    for ticket in tickets:
        if ticket.created_at:
            try:
                # ✅ Convert string timestamps safely
                if isinstance(ticket.created_at, str):
                    if ticket.created_at not in [None, "0000-00-00 00:00:00"]:
                        ticket.created_at = datetime.strptime(ticket.created_at, "%Y-%m-%d %H:%M:%S")
                    else:
                        ticket.created_at = None  # Handle invalid timestamps

                # ✅ Ensure proper timezone conversion
                if ticket.created_at:
                    ticket.created_at = ticket.created_at.replace(tzinfo=UTC).astimezone(eastern)

                    # ✅ Calculate ticket age
                    age = current_time - ticket.created_at.astimezone(UTC)
                    days = age.days
                    hours = age.seconds // 3600  # Get hours from seconds
                    ticket.age = f"{days}d:{hours}h"
                else:
                    ticket.age = "N/A"  # Handle cases with missing timestamps

            except ValueError:
                ticket.created_at = None  # Handle any parsing errors
                ticket.age = "N/A"

    session.pop('start_time_utc', None)
    return render_template('dashboard.html', tickets=tickets)


@app.route('/project_or_regular')
@login_required
def project_or_regular():
    return render_template('project_or_regular.html')

@app.route('/new_ticket', methods=['GET', 'POST'])
@login_required
def new_ticket():
    project_id = request.args.get('project_id', type=int)  # Get project_id if passed
    phase_id = request.args.get('phase_id', type=int)      # Get phase_id if passed
    from_dashboard = request.args.get('from_dashboard')    # Track the origin

    form = TicketForm()

    # Populate the client (employee) choices for the requestor
    clients = Client.query.all()  # Retrieve all clients (employees)
    form.client_id.choices = [(client.id, f"{client.first_name} {client.last_name} ({client.company.name})") for client in clients]

    # Populate phase choices if a project is selected
    if project_id:
        project = Project.query.get_or_404(project_id)
        phases = [(p.id, p.name) for p in project.phases]
        form.phase_id.choices = phases if phases else [(0, 'No Phases Available')]
    else:
        form.phase_id.choices = [(0, 'No Project Assigned')]

    # Validate and handle the form submission
    if form.validate_on_submit():
        # Create the ticket
        ticket = Ticket(
            subject=form.subject.data,
            description=form.description.data,
            priority=form.priority.data,
            status=form.status.data,
            user_id=current_user.id,  # User who created the ticket
            phase_id=form.phase_id.data if form.phase_id.data != 0 else None,
            project_id=project_id,
            client_id=form.client_id.data,  # Link the requestor (client)
            requestor_email=form.requestor_email.data,  # Add requestor email
            cc_emails=form.cc_emails.data,  # Add CC emails
            due_date=form.due_date.data,
            estimated_hours=form.estimated_hours.data
        )
        db.session.add(ticket)
        db.session.commit()
        flash('Ticket created successfully!', 'success')
        # Redirect based on whether it’s linked to a project
        if phase_id:
            return redirect(url_for('project_dashboard', project_id=project_id))
        elif from_dashboard:
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('dashboard_today'))

    return render_template('new_ticket.html', form=form, project_id=project_id)


@app.route('/view_ticket/<int:id>', methods=['GET', 'POST'])
@login_required
def view_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    note_form = AddNoteForm()
    eastern = timezone('US/Eastern')  # Define the Eastern timezone

    # Safely access the project and company (if they exist)
    project = ticket.project
    company = project.company if project else None

    # Store the start time in UTC in the session when user views the ticket
    if 'start_time_utc' not in session:
        session['start_time_utc'] = datetime.now(UTC).isoformat()  # Store as ISO format string

    start_time_utc = datetime.fromisoformat(session['start_time_utc'])


    # Handle form submissions
    if request.method == 'POST':
        # Handle Add Note form submission
        if request.form.get('form_name') == 'note_form' and note_form.validate_on_submit():
            # Convert form data from Eastern time to UTC
            if note_form.note_start_time.data:
                note_start_time = eastern.localize(note_form.note_start_time.data).astimezone(UTC)
            else:
                note_start_time = start_time_utc

            if note_form.note_finish_time.data:
                note_finish_time = eastern.localize(note_form.note_finish_time.data).astimezone(UTC)
            else:
                note_finish_time = datetime.now(UTC)  # Set the finish time to now in UTC if not provided

            # Create and store the new note
            note = TicketNote(
                content=note_form.content.data,
                ticket_id=ticket.id,
                note_start_time=note_start_time,
                note_finish_time=note_finish_time
            )
            db.session.add(note)
            db.session.commit()

            start_time_google = note_start_time.isoformat()
            end_time_google = note_finish_time.isoformat()

            create_event(
                summary=ticket.subject,
                start_time=start_time_google,
                end_time=end_time_google,
                description=note_form.content.data,
                location=''
            )

            # Clear the start time after the note is added
            session.pop('start_time_utc', None)


            if request.form.get('send_email') == 'true':
                send_note_email(ticket.requestor_email, ticket, note)


            flash('Note added successfully!', 'success')
            return redirect(url_for('view_ticket', id=ticket.id))

    # Convert completed_at and note times to Eastern Time for display
    if ticket.completed_at:
        ticket.completed_at = ticket.completed_at.replace(tzinfo=UTC).astimezone(eastern)

    # Convert note times from UTC to Eastern Time for display
    for note in ticket.notes:
        if note.created_at:
            note.created_at = note.created_at.replace(tzinfo=UTC).astimezone(eastern)
        if note.note_start_time:
            note.note_start_time = note.note_start_time.replace(tzinfo=UTC).astimezone(eastern)
        if note.note_finish_time:
            note.note_finish_time = note.note_finish_time.replace(tzinfo=UTC).astimezone(eastern)



    # Render the template, passing the project and company details as well
    return render_template('view_ticket.html', ticket=ticket, note_form=note_form, project=project, company=company)

# Function to send an email when a note is added
def send_note_email(requestor_email, ticket, note):
    subject = f"New Note Added to Ticket# {ticket.id}: {ticket.subject}"
    eastern = timezone('US/Eastern')
    note_start_time_eastern = note.note_start_time.replace(tzinfo=UTC).astimezone(eastern).strftime('%m/%d/%y %H:%M')
    note_finish_time_eastern = note.note_finish_time.replace(tzinfo=UTC).astimezone(eastern).strftime('%m/%d/%y %H:%M')

    # Link to the Google Drive image (replace with your correct link)
    logo_url = Config.LOGO_URL

    # HTML email body with linked logo image
    body = f"""
    <html>
    <head>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #e0e6ed;
                color: #2a3f54;
                padding: 20px;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #ffffff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }}
            h2 {{
                color: #1b3a57;
                text-align: center;
            }}
            .note-details {{
                background-color: #cbd5e0;
                padding: 10px;
                border-radius: 5px;
            }}
            .time {{
                font-weight: bold;
                color: #0077b6;
            }}
            .footer {{
                text-align: center;
                font-size: 0.9em;
                color: #2a3f54;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div style="text-align: center;">
                <img src="{logo_url}" alt="RVA IT Pros Logo" style="max-width: 200px; margin-bottom: 20px;">
            </div>
            <h2>New Note Added to Your Ticket</h2>
            <p>Hello <strong>{ticket.client.first_name}</strong>,</p>
            <p>A new note has been added to your ticket:</p>
            <div class="note-details">
                <p><strong>Ticket ID:</strong> {ticket.id}</p>
                <p><strong>Subject:</strong> {ticket.subject}</p>
                <p><strong>Note Content:</strong> {note.content}</p>
                <p><strong>Time Spent:</strong> <span class="time">{note_start_time_eastern} to {note_finish_time_eastern}</span></p>
            </div>
            <p>If you have any questions or need further assistance, feel free to contact us.</p>
            <p>Regards,<br>
            <strong>RVA IT Helpdesk Team</strong></p>
            <div class="footer">
                <p>{Config.COMPANY_NAME} | Contact Us: {Config.COMPANY_SUPPORT_PHONE} | {Config.COMPANY_SUPPORT_EMAIL}</p>
            </div>
        </div>
    </body>
    </html>
    """

    msg = Message(subject, recipients=[requestor_email])
    msg.html = body

    # Send the email without attaching the logo since it's linked via URL
    mail.send(msg)



@app.route('/edit_ticket/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_ticket(id):
    ticket = Ticket.query.get_or_404(id)

    # ✅ Fix: Normalize due_date before binding to the form
    if ticket.due_date and isinstance(ticket.due_date, str):
        try:
            ticket.due_date = parser.parse(ticket.due_date)
        except ValueError:
            ticket.due_date = None

    update_form = UpdateTicketForm(obj=ticket)  # ✅ Moved here

    # Populate client (employee) choices
    clients = Client.query.all()
    update_form.client_id.choices = [(client.id, f"{client.first_name} {client.last_name} ({client.company.name})") for client in clients]

    # Set phase choices only if the ticket is linked to a project with phases
    if ticket.project_id:
        project = Project.query.get(ticket.project_id)
        if project and project.phases:
            update_form.phase_id.choices = [(p.id, p.name) for p in project.phases]
        else:
            update_form.phase_id.choices = [(0, 'No Phases Available')]
    else:
        update_form.phase_id.choices = [(0, 'No Project Assigned')]

    if request.method == 'POST' and update_form.validate_on_submit():
        # Update the ticket fields with form data
        ticket.subject = update_form.subject.data
        ticket.description = update_form.description.data
        ticket.status = update_form.status.data
        ticket.priority = update_form.priority.data
        ticket.client_id = update_form.client_id.data
        ticket.requestor_email = update_form.requestor_email.data
        ticket.cc_emails = update_form.cc_emails.data
        ticket.phase_id = update_form.phase_id.data if update_form.phase_id.data != 0 else None
        ticket.estimated_hours = update_form.estimated_hours.data

        # Check if due_date is provided in the form, else retain the current due_date
        if update_form.due_date.data:
            ticket.due_date = update_form.due_date.data

        db.session.commit()
        flash('Ticket updated successfully!', 'success')
        return 'Updated', 200  # Return a success status

    return render_template('edit_ticket.html', ticket=ticket, update_form=update_form)

@app.route('/edit_note/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = TicketNote.query.get_or_404(note_id)
    form = EditNoteForm(obj=note)
    eastern = timezone('US/Eastern')  # Define the Eastern timezone
    utc = timezone('UTC')  # Define UTC timezone

    if form.validate_on_submit():
        # Convert form times (in Eastern Time) back to UTC before saving
        if form.note_start_time.data:
            note.note_start_time = eastern.localize(form.note_start_time.data).astimezone(utc).replace(tzinfo=None)
        if form.note_finish_time.data:
            note.note_finish_time = eastern.localize(form.note_finish_time.data).astimezone(utc).replace(tzinfo=None)
        note.content = form.content.data

        db.session.commit()
        flash('Note updated successfully!', 'success')
        return redirect(url_for('view_ticket', id=note.ticket_id))

    if request.method == 'GET':
        # Convert stored UTC times to Eastern Time for form display
        if note.note_start_time:
            form.note_start_time.data = utc.localize(note.note_start_time).astimezone(eastern).replace(tzinfo=None)
        if note.note_finish_time:
            form.note_finish_time.data = utc.localize(note.note_finish_time).astimezone(eastern).replace(tzinfo=None)
        form.content.data = note.content

    return render_template('edit_note.html', form=form, ticket=note.ticket, note=note)

@app.route('/delete_note/<int:note_id>', methods=['POST'])
@login_required
def delete_note(note_id):
    note = TicketNote.query.get_or_404(note_id)

    db.session.delete(note)
    db.session.commit()
    flash('Ticket Note deleted successfully!', 'success')
    return redirect(url_for('view_ticket', id=note.ticket_id))

@app.route('/toggle_resolution/<int:note_id>', methods=['POST'])
@login_required
def toggle_resolution(note_id):
    note = TicketNote.query.get_or_404(note_id)
    print(note)

    # Toggle the billable status
    if note.is_resolution == False:
        note.is_resolution = True  # Convert to resolution note
    else:
        note.is_resolution = False  # Convert to not resolution

    db.session.commit()
    flash(f'Note "{note.id}" updated to {"Resolution" if note.is_resolution == True else "Not-Resolution"}!', 'success')
    return redirect(url_for('view_ticket', id=note.ticket_id))

@app.route('/toggle_billable/<int:ticket_id>', methods=['POST'])
@login_required
def toggle_billable(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    # Toggle the billable status
    if ticket.billable == 'NB':
        ticket.billable = 'R'  # Convert to Billable
    else:
        ticket.billable = 'NB'  # Convert to Non-Billable

    db.session.commit()
    flash(f'Ticket "{ticket.subject}" updated to {"Billable" if ticket.billable == "R" else "Non-Billable"}!', 'success')
    return redirect(url_for('view_ticket', id=ticket_id))


@app.route('/toggle_billable_reviewed/<int:ticket_id>', methods=['POST'])
@login_required
def toggle_billable_reviewed(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)

    # Toggle the billable status
    if ticket.billable == 'NB':
        ticket.billable = 'R'  # Convert to Billable
    else:
        ticket.billable = 'NB'  # Convert to Non-Billable

    db.session.commit()
    flash(f'Ticket "{ticket.subject}" updated to {"Billable" if ticket.billable == "R" else "Non-Billable"}!', 'success')
    return redirect(url_for('billing_review_dashboard', id=ticket_id))

@app.route('/toggle_invoiced/<int:ticket_id>', methods=['POST'])
@login_required
def toggle_invoiced(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    #toggle invoiced status
    if ticket.billable == 'R':
        ticket.billable = 'I'
    else:
        ticket.billable = 'R'
    db.session.commit()
    flash(f'Ticket "{ticket.subject}" updated to {"Invoiced" if ticket.billable == "I" else "Non-Billable"}!', 'success')
    return redirect(url_for('billing_dashboard'))

@app.route('/mark_reviewed_nonbillable/<int:ticket_id>', methods=['POST'])
@login_required
def mark_reviewed_nonbillable(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    if ticket.billable == 'NB':
        ticket.billable = 'RNB'  # Mark as reviewed but not billable
        db.session.commit()
        flash(f'Ticket \"{ticket.subject}\" marked as Reviewed - Not Billable.', 'info')
    return redirect(url_for('billing_review_dashboard'))

@app.route('/billing_dashboard', methods=['GET', 'POST'])
@login_required
def billing_dashboard():


    # Default date range: last 7 days
    start_date = request.form.get('start_date') or datetime.now().replace(day=1).strftime('%Y-%m-%d')
    end_date = request.form.get('end_date') or datetime.now().strftime('%Y-%m-%d')

    # Convert strings to datetime objects
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')

    # Get billable tickets (B) within the selected date range
    tickets = Ticket.query.filter(
        Ticket.billable == 'R',
        Ticket.completed_at >= start_date_obj,
        Ticket.completed_at <= end_date_obj
    ).order_by(
        db.case(
            (Ticket.status in ['Open', 'In Progress'], 1),
            (Ticket.status == 'Touched', 2),
            (Ticket.status == 'On Hold', 3),
            (Ticket.status == 'Closed', 4),
        ).asc(),
        db.case(
            (Ticket.priority == 'Important-Urgent', 1),
            (Ticket.priority == 'Important-NotUrgent', 2),
            (Ticket.priority == 'NotImportant-Urgent', 3),
            (Ticket.priority == 'NotImportant-NotUrgent', 4),
        ).asc(),
    ).all()


    # Calculate total time spent per ticket from TicketNote
    ticket_totals = {}
    for ticket in tickets:
        total_time = db.session.query(
            func.sum(
                func.timestampdiff(text('MINUTE'), TicketNote.note_start_time, TicketNote.note_finish_time)
            )
        ).filter_by(ticket_id=ticket.id).scalar()


        # Store the total time per ticket in minutes
        ticket_totals[ticket.id] = total_time / 60 if total_time else 0
    
    for ticket in tickets:
        if ticket.due_date and isinstance(ticket.due_date, str):
            try:
                ticket.due_date = parser.parse(ticket.due_date)
            except ValueError:
                ticket.due_date = None
    return render_template('billing_dashboard.html', tickets=tickets, ticket_totals=ticket_totals, start_date=start_date, end_date=end_date)

@app.route('/billing_review_dashboard', methods=['GET', 'POST'])
@login_required
def billing_review_dashboard():
    # Default date range: last 7 days
    start_date = request.form.get('start_date') or datetime.now().replace(day=1).strftime('%Y-%m-%d')
    end_date = request.form.get('end_date') or datetime.now().strftime('%Y-%m-%d')

    # Convert strings to datetime objects
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d')
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d')

    # Get billable tickets (B) within the selected date range
    tickets = Ticket.query.filter(
        Ticket.billable == 'NB',
        Ticket.completed_at >= start_date_obj,
        Ticket.completed_at <= end_date_obj
    ).order_by(
        Ticket.completed_at.asc()
    ).all()

    for ticket in tickets:
        # Fix due_date
        if ticket.due_date and isinstance(ticket.due_date, str):
            try:
                ticket.due_date = parser.parse(ticket.due_date)
            except ValueError:
                ticket.due_date = None

        # Fix completed_at
        if ticket.completed_at and isinstance(ticket.completed_at, str):
            try:
                ticket.completed_at = parser.parse(ticket.completed_at)
            except ValueError:
                ticket.completed_at = None


    # Calculate total time spent per ticket from TicketNote
    ticket_totals = {}
    for ticket in tickets:
        total_time = db.session.query(
            func.sum(
                func.timestampdiff(text('MINUTE'), TicketNote.note_start_time, TicketNote.note_finish_time)
            )
        ).filter_by(ticket_id=ticket.id).scalar()

        # Store the total time per ticket in minutes
        ticket_totals[ticket.id] = total_time if total_time else 0

    return render_template('review_for_billing.html', tickets=tickets, ticket_totals=ticket_totals, start_date=start_date, end_date=end_date)


@app.route('/delete_ticket_page')
@login_required
def delete_ticket_page():
    tickets = Ticket.query.all()  # Or filter by user, etc.
    return render_template('delete_ticket.html', tickets=tickets)


@app.route('/delete_ticket/<int:id>', methods=['POST'])
@login_required
def delete_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    if current_user.role != 'admin':
        flash('You do not have permission to delete this ticket.', 'danger')
        return redirect(url_for('view_ticket', id=ticket.id))

    db.session.delete(ticket)
    db.session.commit()
    flash('Ticket deleted successfully!', 'success')
    return redirect(url_for('dashboard'))

# def send_complete_email(requestor_email, ticket):
#     subject = f"New Note Added to Ticket# {ticket.id}: {ticket.subject}"
#     eastern = timezone('US/Eastern')

#     # Link to the Google Drive image (replace with your correct link)
#     logo_url = Config.LOGO_URL

#     # HTML email body with linked logo image
#     body = f"""
#     <html>
#     <head>
#         <style>
#             body {{
#                 font-family: Arial, sans-serif;
#                 background-color: #e0e6ed;
#                 color: #2a3f54;
#                 padding: 20px;
#             }}
#             .container {{
#                 max-width: 600px;
#                 margin: 0 auto;
#                 background-color: #ffffff;
#                 padding: 20px;
#                 border-radius: 10px;
#                 box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
#             }}
#             h2 {{
#                 color: #1b3a57;
#                 text-align: center;
#             }}
#             .note-details {{
#                 background-color: #cbd5e0;
#                 padding: 10px;
#                 border-radius: 5px;
#             }}
#             .time {{
#                 font-weight: bold;
#                 color: #0077b6;
#             }}
#             .footer {{
#                 text-align: center;
#                 font-size: 0.9em;
#                 color: #2a3f54;
#                 margin-top: 20px;
#             }}
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <div style="text-align: center;">
#                 <img src="{logo_url}" alt="RVA IT Pros Logo" style="max-width: 200px; margin-bottom: 20px;">
#             </div>
#             <h2>Ticket Completed</h2>
#             <p>Hello <strong>{ticket.client.first_name}</strong>,</p>
#             <p>Your ticket has been completed:</p>
#             <div class="note-details">
#                 <p><strong>Ticket ID:</strong> {ticket.id}</p>
#                 <p><strong>Subject:</strong> {ticket.subject}</p>
#             </div>
#             <p>If you have any questions or need further assistance, feel free to contact us.</p>
#             <p>Regards,<br>
#             <strong>RVA IT Helpdesk Team</strong></p>
#             <div class="footer">
#                 <p>{Config.COMPANY_NAME} | Contact Us: {Config.COMPANY_SUPPORT_PHONE} | {Config.COMPANY_SUPPORT_EMAIL}</p>
#             </div>
#         </div>
#     </body>
#     </html>
#     """

#     msg = Message(subject, recipients=['andrew.bean@rvaitpros.com'])
#     msg.html = body

#     # Send the email without attaching the logo since it's linked via URL
#     mail.send(msg)

# Route to mark a ticket as complete (records completed_at time)
@app.route('/complete_ticket/<int:id>', methods=['POST'])
@login_required
def complete_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    ticket.complete = True
    ticket.completed_at = datetime.now(UTC)  # Mark the ticket as completed
    ticket.status = 'Closed'
    ticket.requestor_email
    db.session.commit()
    flash('Ticket marked as complete!', 'success')
    # send_complete_email(ticket.requestor_email, ticket)
    return redirect(url_for('view_ticket', id=ticket.id))

@app.route('/create_project', methods=['GET', 'POST'])
@login_required
def create_project():
    form = ProjectForm()

    # Populate company choices from the Company model
    companies = Company.query.all()
    form.company_id.choices = [(company.id, company.name) for company in companies]

    if form.validate_on_submit():
        # Create the project with the status and company fields
        project = Project(
            name=form.name.data,
            description=form.description.data,
            status=form.status.data,  # Save the selected status
            company_id=form.company_id.data  # Save the selected company
        )
        db.session.add(project)
        db.session.commit()

        # Check if a phase was provided, and create a phase if it was
        if form.phase_name.data:
            phase = Phase(name=form.phase_name.data, project_id=project.id, status='Open')
            db.session.add(phase)
            db.session.commit()

        flash('Project created successfully!', 'success')
        return redirect(url_for('projects_home'))

    return render_template('create_project.html', form=form)

#create phase of project
@app.route('/create_phase/<int:project_id>', methods=['GET', 'POST'])
@login_required
def create_phase(project_id):
    project = Project.query.get_or_404(project_id)
    form = PhaseForm()
    if form.validate_on_submit():
        phase = Phase(
            name=form.name.data,
            project_id=project.id,
            status=form.status.data  # Save the selected status
        )
        db.session.add(phase)
        db.session.commit()
        flash('Phase created successfully!', 'success')
        return redirect(url_for('project_dashboard', project_id=project.id))

    return render_template('create_phase.html', form=form, project=project)
# Projects Home Page - lists all projects and links to their phases and tickets
@app.route('/projects')
@login_required
def projects_home():
    projects = Project.query.filter(Project.status != 'Closed').all()
    session.pop('start_time_utc', None)
    return render_template('projects_home.html', projects=projects)

# View project dashboard - show phases and tickets under each phase
@app.route('/project_dashboard/<int:project_id>')
@login_required
def project_dashboard(project_id):
    project = Project.query.get_or_404(project_id)

    # Custom ordering for phases: Open > In Progress > Closed
    phases = Phase.query.filter_by(project_id=project.id).order_by(
        db.case(
            (Phase.status == 'Open', 1),
            (Phase.status == 'In Progress', 2),
            (Phase.status == 'Closed', 3),
        ).asc()
    ).all()

    # Query the tickets and order by their status
    tickets = Ticket.query.filter_by(project_id=project.id).order_by(
        db.case(
            (Ticket.status == 'Open', 1),
            (Ticket.status == 'In Progress', 2),
            (Ticket.status == 'Closed', 3),
        ).asc()
    ).all()

    return render_template('project_dashboard.html', project=project, phases=phases, tickets=tickets)

@app.route('/select_project/<int:ticket_id>', methods=['GET', 'POST'])
@login_required
def select_project(ticket_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    form = SelectProjectForm()

    # Populate the project choices
    form.project_id.choices = [(0, 'Select a Project')] + [(p.id, p.name) for p in Project.query.all()]

    if form.validate_on_submit():
        selected_project = Project.query.get(form.project_id.data)
        ticket.project_id = selected_project.id
        db.session.commit()  # Save project_id to the ticket

        # Redirect to the phase selection page
        return redirect(url_for('select_phase', ticket_id=ticket_id, project_id=selected_project.id))

    return render_template('select_project.html', form=form, ticket=ticket)

@app.route('/select_project_new_ticket', methods=['GET', 'POST'])
@login_required
def select_project_new_ticket():
    form = SelectProjectForm()

    # Populate the project choices
    form.project_id.choices = [(0, 'Select a Project')] + [(p.id, p.name) for p in Project.query.all()]

    if form.validate_on_submit():
        selected_project = Project.query.get(form.project_id.data)
        db.session.commit()  # Save project_id to the ticket

        # Redirect to the phase selection page
        return redirect(url_for('new_ticket', project_id=selected_project.id))

    return render_template('select_project_new_ticket.html', form=form)

@app.route('/select_phase/<int:ticket_id>/<int:project_id>', methods=['GET', 'POST'])
@login_required
def select_phase(ticket_id, project_id):
    ticket = Ticket.query.get_or_404(ticket_id)
    project = Project.query.get_or_404(project_id)
    form = SelectPhaseForm()

    # Populate the phase choices based on the selected project
    form.phase_id.choices = [(0, 'Select a Phase')] + [(p.id, p.name) for p in project.phases]

    if form.validate_on_submit():
        if form.phase_id.data != 0:  # Ensure a valid phase is selected
            ticket.phase_id = form.phase_id.data
            db.session.commit()  # Save phase_id to the ticket
            flash('Ticket successfully assigned to project and phase!', 'success')
            return redirect(url_for('view_ticket', id=ticket.id))
        else:
            flash('Please select a valid phase.', 'danger')

    return render_template('select_phase.html', form=form, project=project, ticket=ticket)

@app.route('/edit_project/<int:project_id>', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    form = UpdateProjectForm(obj=project)

    # Query the list of companies to populate the SelectField
    companies = Company.query.all()
    form.company_id.choices = [(company.id, company.name) for company in companies]

    # Pre-select the current company in the form
    if request.method == 'GET':
        form.company_id.data = project.company_id

    if form.validate_on_submit():
        project.name = form.name.data
        project.description = form.description.data
        project.status = form.status.data

        # Update the company_id with the selected company from the form
        project.company_id = form.company_id.data

        db.session.commit()
        flash('Project updated successfully!', 'success')
        return redirect(url_for('project_dashboard', project_id=project.id))

    return render_template('edit_project.html', form=form, project=project)

@app.route('/edit_phase/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_phase(id):
    phase = Phase.query.get_or_404(id)
    form = PhaseForm(obj=phase)

    if form.validate_on_submit():
        # Update the phase details
        phase.name = form.name.data
        phase.status = form.status.data  # Update the status
        db.session.commit()
        flash('Phase updated successfully!', 'success')
        return redirect(url_for('project_dashboard', project_id=phase.project_id))

    return render_template('edit_phase.html', form=form, phase=phase)

# Route to create a company
@app.route('/create_company', methods=['GET', 'POST'])
@login_required  # If needed
def create_company():
    form = CompanyForm()

    if form.validate_on_submit():
        # Create a new company object
        company = Company(
            name=form.name.data,
            street_address=form.street_address.data,
            city=form.city.data,
            state=form.state.data,
            zip_code=form.zip_code.data,
            main_phone=form.main_phone.data,
            customer_type=form.customer_type.data
        )
        db.session.add(company)
        db.session.commit()
        flash('Company created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('create_company.html', form=form)

# Route to create a client
@app.route('/create_client', methods=['GET', 'POST'])
@login_required  # If needed
def create_client():
    form = ClientForm()

    # Populate company choices dynamically from the database
    form.company_id.choices = [(c.id, c.name) for c in Company.query.all()]

    if form.validate_on_submit():
        # Create a new client object
        client = Client(
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            phone=form.phone.data,
            company_id=form.company_id.data
        )
        db.session.add(client)
        db.session.commit()
        flash('Client created successfully!', 'success')
        return redirect(url_for('dashboard'))

    return render_template('create_client.html', form=form)

@app.route('/company_dashboard', methods=['GET'])
@login_required
def view_company():
    # Query the database to get all companies
    companies = Company.query.all()

    # Pass the companies to the template
    return render_template('company_dashboard.html', companies=companies)

@app.route('/company/<int:company_id>', methods=['GET', 'POST'])
@login_required
def view_edit_company(company_id):
    company = Company.query.get_or_404(company_id)
    form = EditCompanyForm(obj=company)

    if form.validate_on_submit():
        # Update company details
        company.name = form.name.data
        company.street_address = form.street_address.data
        company.city = form.city.data
        company.state = form.state.data
        company.zip_code = form.zip_code.data
        company.main_phone = form.main_phone.data
        company.customer_type = form.customer_type.data
        db.session.commit()
        flash('Company details updated successfully!', 'success')
        return redirect(url_for('view_edit_company', company_id=company.id))

    # Retrieve clients (employees) for this company
    clients = Client.query.filter_by(company_id=company_id).all()

    return render_template('view_edit_company.html', form=form, company=company, clients=clients)

@app.route('/client/<int:client_id>', methods=['GET', 'POST'])
@login_required
def view_edit_client(client_id):
    client = Client.query.get_or_404(client_id)
    form = EditClientForm(obj=client)

    if form.validate_on_submit():
        # Update client details
        client.first_name = form.first_name.data
        client.last_name = form.last_name.data
        client.email = form.email.data
        client.phone = form.phone.data
        db.session.commit()
        flash('Client details updated successfully!', 'success')
        return redirect(url_for('view_edit_client', client_id=client.id))

    return render_template('view_edit_client.html', form=form, client=client)

@app.route('/get_client_email', methods=['GET'])
@login_required
def get_client_email():
    client_id = request.args.get('client_id')
    client = Client.query.get_or_404(client_id)

    # Return the email in JSON format
    return jsonify(email=client.email)

@app.route('/admin_dashboard', methods=['GET', 'POST'])
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard'))

    users = User.query.all()
    role_form = ChangeRoleForm()

    if role_form.validate_on_submit():
        user_id = role_form.user_id.data
        new_role = role_form.role.data
        user = User.query.get(user_id)
        if user:
            user.role = new_role
            db.session.commit()
            flash(f"Role for {user.username} updated to {new_role}.", 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin_dashboard.html', users=users, role_form=role_form)

@app.route('/random_task')
@login_required
def random_task():
    tickets = Ticket.query.filter(
        Ticket.due_date.between(
            func.date(func.now()),  # ✅ Fix: Gets today's date at 00:00:00
            func.date(func.now() + text('INTERVAL 1 DAY'))  # ✅ Fix: Gets tomorrow's date
        ),
         ~Ticket.status.in_(['Touched', 'Closed', 'On Hold'])  # Exclude tickets with status 'Touched' or 'Closed'
    ).order_by(
        db.case(
            (Ticket.status == 'Open', 1),
            (Ticket.status == 'In Progress', 2),
            (Ticket.status == 'Touched', 3),
            (Ticket.status == 'Closed', 4),
            (Ticket.status == 'On Hold',5),
        ).asc(),
        db.case(
            (Ticket.priority == 'Important-Urgent', 1),
            (Ticket.priority == 'Important-NotUrgent', 2),
            (Ticket.priority == 'NotImportant-Urgent', 3),
            (Ticket.priority == 'NotImportant-NotUrgent', 4),
        ).asc()
    ).all()

    # Create a weighted list of tickets
    weighted_tickets = []
    for ticket in tickets:
        if ticket.priority == 'Important-Urgent':
            weighted_tickets.extend([ticket] * 5)  # Add high-priority ticket 5 times
        elif ticket.priority == 'Important-NotUrgent':
            weighted_tickets.extend([ticket] * 3)  # Add medium-high-priority ticket 3 times
        elif ticket.priority == 'NotImportant-Urgent':
            weighted_tickets.extend([ticket] * 3)  # Add medium-low-priority ticket 3 times
        elif ticket.priority == 'NotImportant-NotUrgent':
            weighted_tickets.append(ticket)  # Add low-priority ticket 1 time

    number_of_tickets = len(weighted_tickets)

    if number_of_tickets > 0:
        random_ticket = random.choice(weighted_tickets)  # Select a random ticket based on the weighted list
    else:
        random_ticket = None  # Handle case where there are no tickets

    return render_template('random_task.html', random_ticket=random_ticket)

@app.route('/random_number_generator', methods=['GET', 'POST'])
@login_required
def random_number():
    form = RandomNumberForm()
    random_int = 0
    if form.validate_on_submit():
        random_int = random.randint(1,form.number.data)

    return render_template('random_number_generator.html', form=form, random_int=random_int)



def execute_query(query, params=None):
    """Helper function to execute a query on MySQL."""
    conn = None
    try:
        # Connect to MySQL
        conn = pymysql.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,  # Returns results as dictionaries
            connect_timeout=30,
            autocommit=True
        )
        cursor = conn.cursor()

        # Execute query
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)

        # Commit if it's an INSERT, UPDATE, or DELETE
        conn.commit()

        return {"success": True, "message": "Query executed successfully", "affected_rows": cursor.rowcount}
    except (pymysql.OperationalError, pymysql.InterfaceError) as e:  # ✅ Fix syntax
        print(f"⚠️ Lost connection to MySQL: {e}")
        return {"success": False, "message": str(e)}
    finally:
        if conn:
            conn.close()

@app.route('/update-tickets', methods=['GET','POST'])
def update_tickets():
    # Get today's date dynamically in the correct format
    today = datetime.now().strftime('%Y-%m-%d 00:00:00')

    # Define dynamic queries
    queries = [
        # ✅ Fix: Replace `?` with `%s`
        {
            "query": """UPDATE ticket
                        SET due_date = %s
                        WHERE due_date < %s
                        AND status NOT IN ('Closed', 'On Hold');""",
            "params": (today, today)
        },
        {
            "query": """UPDATE ticket
                        SET due_date = NULL
                        WHERE status = 'On Hold';""",
            "params": None
        },
        {
            "query": """UPDATE ticket
                        SET status = 'In Progress'
                        WHERE status = 'Touched';""",
            "params": None
        },
        {
            "query": """UPDATE ticket
                        SET completed_at = NULL, complete = 0
                        WHERE status <> 'Closed' AND completed_at IS NOT NULL AND complete = 1;""",
            "params": None
        },
    ]

    print(queries)  # Debugging - Check if queries are correct

    # ✅ Fix: Ensure `None` queries pass correctly
    results = [execute_query(q["query"], q["params"] or ()) for q in queries]

    return render_template('clean_up_tickets.html', results=results)


from flask import send_file
import pandas as pd
from io import BytesIO
from datetime import datetime

@app.route('/download_project_excel/<int:project_id>')
def download_project_excel(project_id):
    project = Project.query.get_or_404(project_id)

    rows = []

    for phase in project.phases:
        for ticket in phase.tickets:
            is_billable = ticket.billable == 'R'
            billable_label = 'Yes' if is_billable else 'No'

            # Sum time deltas only if billable
            total_seconds = 0
            note_texts = []

            for note in ticket.notes:
                note_texts.append(note.content)
                if is_billable and note.note_start_time and note.note_finish_time:
                    delta = note.note_finish_time - note.note_start_time
                    total_seconds += delta.total_seconds()

            hours = round(total_seconds / 3600, 2) if is_billable else 0

            rows.append({
                "Project Name": project.name,
                "Project Status": project.status,
                "Company": project.company.name,
                "Phase Name": phase.name,
                "Phase Status": phase.status,
                "Ticket Subject": ticket.subject,
                "Ticket Status": ticket.status,
                "Priority": ticket.priority,
                "Billable": billable_label,
                "Logged Hours": hours,
                "Notes": "\n---\n".join(note_texts)
            })

    df = pd.DataFrame(rows)

    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Project Details')

    output.seek(0)
    filename = f"{project.name.replace(' ', '_')}_details_{datetime.now().strftime('%Y%m%d')}.xlsx"

    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route("/calendar")
def calendar():
    return render_template('calendar.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)