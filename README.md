# 💼 Financial Management System

A custom-built, Flask-based financial management system designed to track projects, loans, tranches, repayments, and generate detailed reports.

---

## 🚀 Features

- Project and loan tracking
- Tranches and repayment management
- Yearly and loan-specific interest reports
- Adjustable interest capitalization and taxation
- Custom UI built with Tailwind CSS
- Optional: packaged as a standalone `.exe` (no setup required for end users)

---

## 📁 Project Structure

```
tailwind-flask-starter/
├── app/
│   ├── __init__.py
│   ├── config.py             # Needs to be created 
│   ├── config_example.py     # template for config above
│   ├── models.py
│   ├── routes/
│   └── static/
│       ├── logo.png          # Add your logo here
│       └── logo2.png         # Add your logo here
├── run.py
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 🛠️ Setup Instructions

Follow these steps to run the project locally.

---

### ✅ Step 1: Clone the repository



### ✅ Step 2: Create a virtual environment (recommended)



### ✅ Step 3: Install the required packages

```bash
pip install -r requirements.txt
```

---

### ✅ Step 4: Configure the application

Copy the example configuration file and edit it:

```bash
cp app/config_example.py app/config.py
```

Then open `app/config.py` and set your:

- `SQLALCHEMY_DATABASE_URI` (e.g. your Neon/PostgreSQL connection string)
- `SECRET_KEY` (any random string)

---

### ✅ Step 5: Add your logos

Add 2 logo files to that routes:

- `app/static/logo.png` - the main logo visible on the side
- `app/static/logo2.png` - the logo used for the watermark

You may use the placeholders already included if you just want to test.

---

### ✅ Step 6: Run the application

```bash
python run.py
```

Your default web browser will open automatically at:

[http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## 🧊 Building a Windows Executable (Optional)

To generate a single `.exe` for end users (no Python required):

1. Install PyInstaller:

```bash
pip install pyinstaller
```

2. Build the executable:

```bash
pyinstaller --noconfirm --onefile --add-data "app;app" --add-data "tailwind.config.js;." run.py
```

3. The `.exe` will appear in the `dist/` folder.

You can distribute this to others without requiring Python or manual setup.

---

## 📝 License

This project is proprietary to your company or personal use unless otherwise specified.

---

## 🤝 Contributing

If you'd like to collaborate or extend the project, feel free to fork it and make a pull request.
