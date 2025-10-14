import threading
import webbrowser
from flask import Flask, redirect, url_for
from config import Config
from .models import db
from .routes import blueprints
from dotenv import load_dotenv

load_dotenv()

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

    from app.functions import format_number_pl
    app.jinja_env.filters["pl_number"] = format_number_pl           # 12 345,67
    app.jinja_env.filters["pl_currency"] = lambda v: format_number_pl(v, currency=True)  # 12 345,67 zł

    return app
