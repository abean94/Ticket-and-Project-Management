from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

# Initialize the database
db = SQLAlchemy()

# User Model
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')  # 'user' or 'admin'

    def __repr__(self):
        return f'<User {self.username}>'


# Ticket Model
class Ticket(db.Model):
    __tablename__ = 'ticket'

    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(200), nullable=False)
    requestor_email = db.Column(db.String(150), nullable=False)
    cc_emails = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Open')
    priority = db.Column(db.String(50), nullable=False, default='Important-NotUrgent')
    billable = db.Column(db.String(50), nullable = False, default = 'NB')
    
    # Foreign key to User (who created the ticket)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_ticket_user'), nullable=False)

    # Foreign key to User (who is assigned to the ticket)
    assigned_to = db.Column(db.Integer, db.ForeignKey('user.id', name='fk_ticket_assigned_to'), nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())  # Ticket opened time
    updated_at = db.Column(db.DateTime, onupdate=db.func.current_timestamp())
    completed_at = db.Column(db.DateTime, nullable=True)  # Ticket closed time
    view_start_time = db.Column(db.DateTime, nullable=True)
    note_start_time = db.Column(db.DateTime, nullable=True)  # For tracking when a note starts


    # Completion flag
    complete = db.Column(db.Boolean, default=False)  # Ticket completion flag

    # Foreign key to Phase (to link the ticket to a phase)
    phase_id = db.Column(db.Integer, db.ForeignKey('phase.id', name='fk_ticket_phase'), nullable=True)

    # Foreign key to Project (to link the ticket to a project)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', name='fk_ticket_project'), nullable=True)

    due_date = db.Column(db.DateTime, default=None)
    estimated_hours = db.Column(db.Float, default=0.5)

    # Relationship for notes
    notes = db.relationship('TicketNote', backref='ticket', lazy=True)

    # Relationship to project
    project = db.relationship('Project', back_populates='tickets')  # Back_populates instead of backref

    # Relationship to phase
    phase = db.relationship('Phase', back_populates='tickets')  # Back_populates instead of backref

    # Foreign key to the client (employee) who made the request
    client_id = db.Column(db.Integer, db.ForeignKey('client.id', name='fk_ticket_client'), nullable=False)

    # Gmail message ID for tickets created from email
    gmail_message_id = db.Column(db.String(128), nullable=True)

    # Relationship to the company (through the client)
    client = db.relationship('Client', back_populates='tickets')

    def __repr__(self):
        return f'<Ticket {self.subject}>'


# TicketNote Model for adding notes to tickets
class TicketNote(db.Model):
    __tablename__ = 'ticket_note'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id', name='fk_ticketnote_ticket'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    note_start_time = db.Column(db.DateTime, nullable = True)
    note_finish_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_resolution = db.Column(db.Boolean, default=False, nullable=False)
    def __repr__(self):
        return f'<TicketNote {self.id} for Ticket {self.ticket_id}>'


# Project Model
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    # Foreign key to relate to Company
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', name='fk_project_company'), nullable=False)

    
    # Add status column
    status = db.Column(db.String(50), nullable=False, default='Open')  # Possible values: 'Open', 'In Progress', 'Closed'

    # Relationship to tickets
    tickets = db.relationship('Ticket', back_populates='project', lazy=True)

    # Relationship to Phases
    phases = db.relationship('Phase', back_populates='project', lazy=True)

    company = db.relationship('Company', back_populates='projects')



    def __repr__(self):
        return f'<Project {self.name} - Status: {self.status}>'


# Phase Model
class Phase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    
    # Add status column
    status = db.Column(db.String(50), nullable=False, default='Open')  # Possible values: 'Open', 'In Progress', 'Closed'
    
    # Foreign key to Project
    project_id = db.Column(db.Integer, db.ForeignKey('project.id', name='fk_phase_project'), nullable=False)

    # Relationship to tickets
    tickets = db.relationship('Ticket', back_populates='phase', lazy=True)

    # Relationship to project
    project = db.relationship('Project', back_populates='phases')

    def __repr__(self):
        return f'<Phase {self.name} - Status: {self.status}>'


# Company Model
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    street_address = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(50), nullable=False)
    zip_code = db.Column(db.String(20), nullable=False)
    main_phone = db.Column(db.String(20), nullable=True)
    customer_type = db.Column(db.String(50), nullable=False)  # Lead, Customer, Former Customer

    # Relationship with clients (employees)
    employees = db.relationship('Client', back_populates='company', lazy=True)

    # Relationship to Projects
    projects = db.relationship('Project', back_populates='company', lazy=True)

    def __repr__(self):
        return f'<Company {self.name}>'


# Client (Employee) Model
class Client(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(20), nullable=True)

    # Foreign key to relate to the company they work for
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', name='fk_client_company'), nullable=False)

    # Relationship to tickets
    tickets = db.relationship('Ticket', back_populates='client', lazy=True)

    # Relationship to company
    company = db.relationship('Company', back_populates='employees')

    def __repr__(self):
        return f'<Client {self.first_name} {self.last_name}>'