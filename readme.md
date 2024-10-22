This was coded in Python 3.12, you will need this or higher. 

You will need to install the requirements from requirements.txt

You will need a config file in this format



# Email configurations
config.py
from flask_mail import Mail

app = Flask(__name__)

app.config['MAIL_SERVER'] = mail server
app.config['MAIL_PORT'] = mail server port
app.config['MAIL_USE_TLS'] = True - if your mail server uses TLS
app.config['MAIL_USERNAME'] = mail user sign on  # Your email address
app.config['MAIL_PASSWORD'] = mail user password - if you are using Gmail you will need an App Password 
app.config['MAIL_DEFAULT_SENDER'] = ('Send as Name', 'sending_email@email.com')
app.config['MAIL_USE_SSL'] = False - if using SSL

mail = Mail(app)