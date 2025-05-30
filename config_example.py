import os

class Config:
    # Secret key for session encryption. 
    # Either set this as an environment variable, or the app will generate a random key each run.
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-here'

    # Database connection string template. Replace with your real credentials,
    # or set as an environment variable and reference it instead:
    #   SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_DATABASE_URI = (
        'postgresql://<username>:<password>@<host>:<port>/<database_name>?sslmode=require'
    )

    # Turn off event-based notifications to save resources
    SQLALCHEMY_TRACK_MODIFICATIONS = False
