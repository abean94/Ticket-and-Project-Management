from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Message, Mail
from email.mime.image import MIMEImage
import os
from werkzeug.security import generate_password_hash, check_password_hash
from forms import RegistrationForm, LoginForm, TicketForm, UpdateTicketForm, AddNoteForm, ProjectForm, PhaseForm, SelectProjectForm, SelectPhaseForm, ClientForm, CompanyForm, EditClientForm, EditCompanyForm, ChangeRoleForm, EditNoteForm, UpdateProjectForm, RandomNumberForm
from models import db, User, Ticket, TicketNote, Project, Phase, Client, Company
from datetime import datetime, timezone
from flask_migrate import Migrate
from sqlalchemy import func
from pytz import timezone, UTC
import random
from io import BytesIO
import pandas as pd
import sqlite3
from config import Config


app = Flask(__name__)

#configurations
app.config.from_object(Config)

mail = Mail(app)

#initialize the database
db.init_app(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/register', methods=['GET', 'POST'])
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
        Ticket.status != 'Closed'
    ).order_by(
        db.case(
            (Ticket.status == 'Open', 1),
            (Ticket.status == 'In Progress', 2),
            (Ticket.status == 'Touched', 3),
            (Ticket.status == 'Closed', 4),
            # (Ticket.status == 'On Hold', 5),
        ).asc(),
        
        db.case(
            (Ticket.priority == 'High', 1),
            (Ticket.priority == 'Medium', 2),
            (Ticket.priority == 'Low', 3),
        ).asc()
    ).all()

    eastern = timezone('US/Eastern')

    current_time = datetime.now(UTC)

    # Calculate the age of each ticket
    for ticket in tickets:
        if ticket.created_at:
            ticket.created_at = ticket.created_at.replace(tzinfo=UTC).astimezone(eastern)

            # Calculate ticket age
            age = current_time - ticket.created_at.astimezone(UTC)
            days = age.days
            hours = age.seconds // 3600  # Get hours from seconds
            ticket.age = f"{days}d:{hours}h"

    for ticket in tickets:
        if ticket.created_at:
            ticket.created_at = ticket.created_at.replace(tzinfo=UTC).astimezone(eastern)

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
            (Ticket.status == 'Open', 1),
            (Ticket.status == 'In Progress', 2),
            (Ticket.status == 'Touched', 3),
            (Ticket.status == 'Closed', 4),
            # (Ticket.status == 'On Hold', 5),
        ).asc(),
        
        db.case(
            (Ticket.priority == 'High', 1),
            (Ticket.priority == 'Medium', 2),
            (Ticket.priority == 'Low', 3),
        ).asc()
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

    # Custom ordering for status: Open > In Progress > Closed
    tickets = Ticket.query.filter(
        Ticket.due_date.between(
            func.datetime('now', 'start of day'),  # Today at 00:00:00
            func.datetime('now', 'start of day', '+1 day')  # Tomorrow at 00:00:00
        )
    ).order_by(
        db.case(
            (Ticket.status == 'Open', 1),
            (Ticket.status == 'In Progress', 2),
            (Ticket.status == 'Touched', 3),
            (Ticket.status == 'Closed', 4),
            (Ticket.status == 'On Hold',5),
        ).asc(),
        
        db.case(
            (Ticket.priority == 'High', 1),
            (Ticket.priority == 'Medium', 2),
            (Ticket.priority == 'Low', 3),
        ).asc()
    ).all()

    eastern = timezone('US/Eastern')

    current_time = datetime.now(UTC)



    # Calculate the age of each ticket
    for ticket in tickets:
        if ticket.created_at:
            ticket.created_at = ticket.created_at.replace(tzinfo=UTC).astimezone(eastern)

            # Calculate ticket age
            age = current_time - ticket.created_at.astimezone(UTC)
            days = age.days
            hours = age.seconds // 3600  # Get hours from seconds
            ticket.age = f"{days}d:{hours}h"

    for ticket in tickets:
        if ticket.created_at:
            ticket.created_at = ticket.created_at.replace(tzinfo=UTC).astimezone(eastern)

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

from datetime import datetime
from pytz import timezone, UTC  # Import pytz for timezone handling

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

            # Clear the start time after the note is added
            session.pop('start_time_utc', None)

            
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

    
    # print("Ticket Properties:")
    # print(vars(ticket))  # Or use ticket.__dict__

    # Render the template, passing the project and company details as well
    return render_template('view_ticket.html', ticket=ticket, note_form=note_form, project=project, company=company)



# Function to send an email when a note is added
def send_note_email(requestor_email, ticket, note):
    subject = f"New Note Added to Ticket# {ticket.id}: {ticket.subject}"
    eastern = timezone('US/Eastern')
    print(ticket.client.first_name)
    note_start_time_eastern = note.note_start_time.replace(tzinfo=UTC).astimezone(eastern).strftime('%m/%d/%y %H:%M')
    note_finish_time_eastern = note.note_finish_time.replace(tzinfo=UTC).astimezone(eastern).strftime('%m/%d/%y %H:%M')

    # Link to the Google Drive image (replace with your correct link)
    logo_url = "https://drive.google.com/uc?export=view&id=1UY4jZ9uTc4zGQpOIOQgAr1YQXHUbCMpy"  # Replace this with your Google Drive image link

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
                <p>RVA IT Pros | Contact Us: (804) 220-0380 | helpdesk@rvaitpros.com</p>
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
    update_form = UpdateTicketForm(obj=ticket)

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

    if request.method == 'POST':
        if update_form.validate_on_submit():
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
            else:
                update_form.due_date.data = ticket.due_date  # Retain the old due date if no new date is selected


        db.session.commit()
        flash('Ticket updated successfully!', 'success')
        return redirect(url_for('view_ticket', id=ticket.id))

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

    return render_template('edit_note.html', form=form, ticket=note.ticket)

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
            (Ticket.status == 'Open', 1),
            (Ticket.status == 'In Progress', 2),
            (Ticket.status == 'Closed', 3),
        ).asc(),
        db.case(
            (Ticket.priority == 'High', 1),
            (Ticket.priority == 'Medium', 2),
            (Ticket.priority == 'Low', 3),
        ).asc()
    ).all()

    print(tickets)

    # Calculate total time spent per ticket from TicketNote
    ticket_totals = {}
    for ticket in tickets:
        total_time = db.session.query(
            func.sum(
                func.julianday(TicketNote.note_finish_time) - func.julianday(TicketNote.note_start_time)
            ) * 24   # Convert to minutes
        ).filter_by(ticket_id=ticket.id).scalar()

        # Store the total time per ticket in minutes
        ticket_totals[ticket.id] = total_time if total_time else 0

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
        db.case(
            (Ticket.status == 'Open', 1),
            (Ticket.status == 'In Progress', 2),
            (Ticket.status == 'Closed', 3),
        ).asc(),
        db.case(
            (Ticket.priority == 'High', 1),
            (Ticket.priority == 'Medium', 2),
            (Ticket.priority == 'Low', 3),
        ).asc()
    ).all()

    print(tickets)

    # Calculate total time spent per ticket from TicketNote
    ticket_totals = {}
    for ticket in tickets:
        total_time = db.session.query(
            func.sum(
                func.julianday(TicketNote.note_finish_time) - func.julianday(TicketNote.note_start_time)
            ) * 24   # Convert to minutes
        ).filter_by(ticket_id=ticket.id).scalar()

        # Store the total time per ticket in minutes
        ticket_totals[ticket.id] = total_time if total_time else 0

    return render_template('review_for_billing.html', tickets=tickets, ticket_totals=ticket_totals, start_date=start_date, end_date=end_date)

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

# Route to mark a ticket as complete (records completed_at time)
@app.route('/complete_ticket/<int:id>', methods=['POST'])
@login_required
def complete_ticket(id):
    ticket = Ticket.query.get_or_404(id)
    ticket.complete = True
    ticket.completed_at = datetime.now(UTC)  # Mark the ticket as completed
    ticket.status = 'Closed'
    db.session.commit()
    flash('Ticket marked as complete!', 'success')
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
    projects = Project.query.all()
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
            func.datetime('now', 'start of day'),  # Today at 00:00:00
            func.datetime('now', 'start of day', '+1 day')  # Tomorrow at 00:00:00
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
            (Ticket.priority == 'High', 1),
            (Ticket.priority == 'Medium', 2),
            (Ticket.priority == 'Low', 3),
        ).asc()
    ).all()

    # Create a weighted list of tickets
    weighted_tickets = []
    for ticket in tickets:
        if ticket.priority == 'High':
            weighted_tickets.extend([ticket] * 5)  # Add high-priority ticket 5 times
        elif ticket.priority == 'Medium':
            weighted_tickets.extend([ticket] * 3)  # Add medium-priority ticket 3 times
        elif ticket.priority == 'Low':
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
    """Helper function to execute a query."""
    try:
        conn = sqlite3.connect('instance/helpdesk.db')  # Replace with your DB connection if needed
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        return {"success": True, "message": "Query executed successfully"}
    except sqlite3.Error as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()

@app.route('/update-tickets', methods=['GET','POST'])
def update_tickets():
    # Get today's date dynamically in the correct format
    today = datetime.now().strftime('%Y-%m-%d 00:00:00.0000000')

    # Define dynamic queries
    queries = [
        {
            "query": """UPDATE ticket 
                        SET due_date = ? 
                        WHERE due_date < ? 
                        AND status NOT IN ('Closed', 'On Hold');""",
            "params": (today, today)
        },
        {
            "query": """UPDATE ticket 
                        SET priority = 'Medium' 
                        WHERE priority = 'High' AND status <> 'Closed';""",
            "params": None
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
        }
    ]

    # Execute all queries and collect responses
    results = [execute_query(q["query"], q["params"]) for q in queries]

    # Pass the results to the template for rendering
    return render_template('clean_up_tickets.html', results=results)
    


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)