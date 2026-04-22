# Flask Beginner Project

Welcome! This is a simple guide to running your first Flask backend on Windows.

## 1. Prerequisites (Setup First)

### Install Python
1.  Download Python 3.10 or newer from [python.org](https://www.python.org/downloads/).
2.  **IMPORTANT:** When installing, check the box that says **"Add Python to PATH"**.
3.  To verify, open Command Prompt (cmd) or PowerShell and type:
    ```powershell
    python --x
    ```
    You should see something like `Python 3.10.x`.

### Install VS Code
1.  Download and install [Visual Studio Code](https://code.visualstudio.com/).
2.  Open this project folder in VS Code.

---

## 2. Setting Up the Project

Follow these steps exactly in your terminal (VS Code Terminal or PowerShell).

### Step 1: Create a Virtual Environment
A virtual environment keeps your project dependencies separate from other projects.
```powershell
python -m venv venv
```

### Step 2: Activate the Virtual Environment
Command to tell your computer to use the virtual environment:
```powershell
.\venv\Scripts\activate
```
*You should see `(venv)` appear at the beginning of your command line.*

### Step 3: Install Required Libraries
We need to install Flask.
```powershell
pip install -r requirements.txt
```

---

## 3. Running the App

### Start the Server
Run the following command:
```powershell
python app.py
```

You should see output like:
```
 * Running on http://127.0.0.1:5000
```

### Access the App
Open your web browser (Chrome/Edge) and visit:
1.  Home: [http://localhost:5000/](http://localhost:5000/)
    - You will see: `{"message": "Flask is running"}`
2.  Health Check: [http://localhost:5000/health](http://localhost:5000/health)
    - You will see: `{"status": "ok"}`

---

## 4. Stopping the Server
To stop the server, go back to your terminal and press:
`Ctrl + C`
