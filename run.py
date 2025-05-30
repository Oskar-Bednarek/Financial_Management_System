import threading
import webbrowser
from app import create_app

def open_browser():
    try:
        webbrowser.open_new("http://127.0.0.1:5000/Kerim_Financial_Management_System")
    except:
        pass  # Silent fail in case browser can't open

app = create_app()

if __name__ == '__main__':
    threading.Timer(1.5, open_browser).start()
    app.run(debug=False, use_reloader=False)
