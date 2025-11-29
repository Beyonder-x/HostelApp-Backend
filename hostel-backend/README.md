# Hostel Backend - Run in Virtual Environment

This simple Flask backend stores students and logs in JSON files and provides endpoints for admin and students.

## Prerequisites
- macOS
- Python 3.8+ (recommended 3.10+)
- zsh (default on macOS)

If you don’t have Python installed, install with Homebrew:
```bash
brew install python
```

## Steps to run in a virtual environment

1. Open a terminal and change into the project directory:
```bash
cd /Users/ankitkumar/Downloads/Backend/hostel-backend
```

2. Create a virtual environment (use whichever name you prefer: `.venv` or `venv`):
```bash
python3 -m venv .venv
```

If this repo already contains `venv/` or `.venv`, you can skip the creation step and activate that instead.

3. Activate the virtual environment (zsh):
```bash
source venv/bin/activate
# or if the repo uses `venv/`:
# source venv/bin/activate
```

4. Upgrade pip (optional but recommended):
```bash
python -m pip install --upgrade pip
```

5. Install dependencies from `requirements.txt`:
```bash
pip install -r requirements.txt
```

6. Run the app:
- Option A — use python directly (recommended for this project):
```bash
python app.py
```

- Option B — use `flask run`:
```bash
export FLASK_APP=app.py
export FLASK_ENV=development  # optional: set this if you want debug mode
flask run --host=0.0.0.0 --port=3000
```

7. Open the API at: `http://localhost:3000/` (endpoints: `/students`, `/login`, `/add_student`, etc.)

8. Deactivate the venv when you’re done:
```bash
deactivate
```

## Notes & Tips
- The project already contains `students.json` and `logs.json` and initializes them if they do not exist.
- If you change dependencies, generate a new `requirements.txt` with:
```bash
pip freeze > requirements.txt
```

- If the project uses `venv/` by default, just activate it with `source venv/bin/activate`.

If you'd like, I can also: add a `Makefile` or scripts to simplify activation and run commands, or create a `pyproject.toml` for reproducible installs. Let me know which you'd prefer.
