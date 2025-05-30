import threading
import webbrowser
from flask import Flask, redirect, url_for
from config import Config
from .models import db
from .routes import blueprints

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    # Register all routes under a single custom URL prefix
    for bp in blueprints:
        app.register_blueprint(bp, url_prefix='/Kerim_Financial_Management_System')

    # Optional: redirect base URL to custom home route
    @app.route('/')
    def redirect_home():
        return redirect(url_for('main.home'))

    # # ✅ Automatically open browser once app is running
    # @app.before_first_request
    # def open_browser():
    #     def _open():
    #         webbrowser.open("http://127.0.0.1:5000/Kerim_Financial_Management_System")
    #     threading.Thread(target=_open).start()

    return app
