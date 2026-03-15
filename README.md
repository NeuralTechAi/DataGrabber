# DataGrabber — AI Document Data Extractor

DataGrabber turns your PDFs, images, and documents into structured spreadsheets using AI.  
Upload a stack of invoices, CVs, forms, or any documents — get back a clean Excel file with the fields you care about.

> **No subscription. No credits. Runs on your own computer.**
> 
Note:

Data extraction from files/documents is continuous and incremental with DataGrabber. Once you create a template, you don’t need to recreate it when you want to extract data from similar files/documents next time; you just have to continue from where you left off. Extracted data is continuously saved in the folder you defined when creating the template.

With DataGrabber, you can upload or drag-and-drop your unstructured files/documents, relax, and wait for it to do the job for you. You can also plug in a folder with thousands of related files/documents, and DataGrabber will do the rest for you.

The clearer the field description context during template creation in DataGrabber, the better the extraction outputs will be.

You can review or update extracted data, giving you full assurance and control.

---

## What it does

You define the fields you want — DataGrabber finds and extracts them from any document, automatically.

 You tell it exactly what to look for, and it reads through your files and pulls out only the data you need into a clean spreadsheet.

| You have | You define (examples) | You get |
|---|---|---|
| Invoices | `invoice_number`, `vendor`, `total_amount`, `due_date`, `tax` | One Excel row per invoice |
| CVs / Resumes | `name`, `email`, `skills`, `years_of_experience`, `highest_qualification` | One row per candidate |
| Contracts | `parties`, `contract_value`, `start_date`, `expiry_date`, `jurisdiction` | One row per contract |
| Medical records | `patient_id`, `diagnosis`, `prescription`, `doctor_name`, `visit_date` | One row per record |
| Property listings | `address`, `price`, `bedrooms`, `size_sqm`, `listing_date` | One row per listing |
| Research papers | `title`, `authors`, `abstract`, `publication_year`, `keywords` | One row per paper |
| Scanned forms | Any fields printed on the form | Filled-in values extracted automatically |
| Your own documents | **Anything you define** | Whatever you ask for |

**The fields are entirely up to you.** If the information exists somewhere in the document — on any page, in any layout — DataGrabber will find it.

---

## Table of Contents

1. [What you need before you start](#1-what-you-need-before-you-start)
2. [Get a free AI API key](#2-get-a-free-ai-api-key)
3. [Download DataGrabber](#3-download-datagrabber)
4. [Install — Windows](#4a-install--windows)
5. [Install — macOS](#4b-install--macos)
6. [Install — Linux](#4c-install--linux)
7. [Configure your API key](#5-configure-your-api-key)
8. [Run the app](#6-run-the-app)
9. [First-time walkthrough](#7-first-time-walkthrough)
10. [Change AI provider or model](#8-change-ai-provider-or-model-in-the-app)
11. [Supported file types](#9-supported-file-types)
12. [Troubleshooting](#10-troubleshooting)
13. [FAQ](#11-faq)

---

## 1. What you need before you start

| Requirement | Notes |
|---|---|
| **Python 3.10 or newer** | Free. One-time install. |
| **An AI API key** | Free tiers available. See Step 2. |
| **Internet connection** | Needed during install and when processing files (unless you use Ollama). |
| A modern browser | Chrome, Firefox, Edge, Safari — any will work. |

You do **not** need Docker, PostgreSQL, or any cloud account.

---

## 2. Get a free AI API key

DataGrabber works with several AI providers. **Pick one** — you only need one key to get started.

### Option A — Google Gemini (recommended for beginners, generous free tier)

1. Go to **[aistudio.google.com](https://aistudio.google.com)**
2. Sign in with your Google account
3. Click **"Get API key"** → **"Create API key"**
4. Copy the key (looks like `AIzaSy...`) — you'll paste it in Step 5

### Option B — OpenAI (GPT models)

1. Go to **[platform.openai.com](https://platform.openai.com)**
2. Create an account (or sign in)
3. Go to **API Keys** → **"Create new secret key"**
4. Copy the key (looks like `sk-...`) — you'll paste it in Step 5
5. Add a small amount of credit ($5 gets you a lot of processing)

### Option C — OpenRouter (access many models with one key)

1. Go to **[openrouter.ai](https://openrouter.ai)**
2. Sign in, click your profile → **"Keys"** → **"Create Key"**
3. Copy the key — you'll paste it in Step 5

### Option D — Ollama (100% free, runs locally, no internet needed for processing)

1. Go to **[ollama.com](https://ollama.com)** and download Ollama for your OS
2. Install and run it — it runs quietly in the background
3. Open a terminal and run: `ollama pull llama3.2`  
   *(This downloads a local AI model — about 2 GB)*
4. No API key needed

---

## 3. Download DataGrabber

### If you have Git installed:

Open a terminal and run:

```bash
git clone https://github.com/NeuralTechAi/DataGrabber.git
cd DataGrabber
```

### If you don't have Git:

1. Click the green **"Code"** button on GitHub → **"Download ZIP"**
2. Unzip the file somewhere easy to find (e.g. your Desktop or Documents folder)
3. Open your terminal and navigate to the unzipped folder:

```bash
# Example — adjust the path to match where you unzipped it
cd ~/Desktop/DataGrabber
```

> **Windows tip:** Right-click inside the unzipped folder and choose **"Open in Terminal"** or **"Open PowerShell window here"**.

---

## 4a. Install — Windows

> Do all of these steps in **PowerShell** or **Command Prompt**, run from inside the DataGrabberV1 folder.

**Step 1 — Check Python is installed:**

```powershell
python --version
```

You should see something like `Python 3.12.x`. If you get an error, download Python from [python.org](https://www.python.org/downloads/) — tick **"Add Python to PATH"** during install, then re-open your terminal.

**Step 2 — Create a virtual environment:**

```powershell
python -m venv .venv
```

**Step 3 — Activate it:**

```powershell
.venv\Scripts\Activate.ps1
```

> If you get a permissions error, run this first:  
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`  
> Then try the activate command again.

Your prompt should now start with `(.venv)`.

**Step 4 — Install all dependencies:**

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

This takes 1–3 minutes. You'll see packages being downloaded and installed.

**Step 5 — Set up your config file:**

```powershell
copy .env.example .env
```

Now open the `.env` file in Notepad (or any text editor) and add your API key — see [Step 5](#5-configure-your-api-key) below.

---

## 4b. Install — macOS

> Do all of these steps in the **Terminal** app, run from inside the DataGrabberV1 folder.

**Step 1 — Check Python is installed:**

```bash
python3 --version
```

You should see `Python 3.10.x` or newer. If not, install it from [python.org](https://www.python.org/downloads/macos/) or via Homebrew: `brew install python`.

**Step 2 — Create a virtual environment:**

```bash
python3 -m venv .venv
```

**Step 3 — Activate it:**

```bash
source .venv/bin/activate
```

Your prompt should now start with `(.venv)`.

**Step 4 — Install all dependencies:**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Step 5 — Set up your config file:**

```bash
cp .env.example .env
```

Open `.env` in TextEdit (or any editor) and add your API key — see [Step 5](#5-configure-your-api-key) below.

---

## 4c. Install — Linux

> Do all of these steps in a terminal, run from inside the DataGrabberV1 folder.

**Step 1 — Check Python is installed:**

```bash
python3 --version
```

If not installed: `sudo apt install python3 python3-venv python3-pip` (Ubuntu/Debian) or equivalent.

**Step 2 — Create and activate a virtual environment:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Step 3 — Install all dependencies:**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

**Step 4 — Set up your config file:**

```bash
cp .env.example .env
```

---

## 5. Configure your API key

Open the `.env` file you just created in any text editor.

Find the AI provider section and **uncomment** (remove the `#`) and fill in your chosen provider:

### Using Gemini (Option A from Step 2):

```env
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-flash
GEMINI_API_KEY=paste_your_key_here
```

### Using OpenAI (Option B from Step 2):

```env
AI_PROVIDER=openai
AI_MODEL=gpt-4o-mini
OPENAI_API_KEY=paste_your_key_here
```

### Using OpenRouter (Option C from Step 2):

```env
AI_PROVIDER=openrouter
AI_MODEL=openrouter/openai/gpt-4o-mini
OPENROUTER_API_KEY=paste_your_key_here
```

### Using Ollama locally (Option D from Step 2):

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.2
```

> **Leave everything else in `.env` as-is for now.** The defaults work out of the box.

---

## 6. Run the app

Make sure your virtual environment is still active (you should see `(.venv)` in your prompt).  
If not, activate it again (see Step 4 for your OS).

Then run:

```bash
python app.py
```

You should see:

```
* Running on http://127.0.0.1:8080
* Running on http://0.0.0.0:8080
```

**Open your browser and go to: [http://localhost:8080](http://localhost:8080)**

> The app will automatically create a database and storage folder under `~/DataGrabber/` the first time it runs.

**To stop the app:** press `Ctrl + C` in the terminal.

**To start it again next time:**

```bash
# 1. Activate the virtual environment (if not already active)
source .venv/bin/activate    # macOS / Linux
.venv\Scripts\Activate.ps1   # Windows

# 2. Run
python app.py
```

---

## 7. First-time walkthrough

### Step 1 — Register an account

1. Open [http://localhost:8080](http://localhost:8080) in your browser
2. Click **"Sign Up"** or **"Register"**
3. Fill in a username, email, and password
4. Click **"Register"** — you'll be redirected to the login page
5. Log in with the credentials you just created

### Step 2 — (Optional) Add your AI API key in the app

You can manage your AI key directly inside the app (in addition to the `.env` file):

1. Click your username (top-right corner) → **"AI Settings"**
2. Select your provider (e.g. OpenAI, Gemini)
3. Choose a model from the dropdown
4. Paste your API key
5. Click **"Save Settings"**

> Keys saved here are used only for your account. Other users can have their own keys.

### Step 3 — Create a project

A **project** is a collection of documents you want to extract from, plus the fields you want extracted.

1. From the Dashboard, click **"New Project"**
2. Fill in:
   - **Project Name** — e.g. `Invoice Extractor` or `CV Screening`
   - **Description** — optional, for your reference
   - **Fields to extract** — this is the important part:
     - Click **"Add Field"**
     - Enter a **Field Name** (e.g. `candidate_name`) — no spaces, use underscores
     - Enter a **Description** (e.g. `Full name of the candidate`) — this helps the AI find it
     - Add as many fields as you need
   - **Storage Location** — choose where project files are saved on your machine
3. Click **"Create Project"**

**Example fields for a CV project:**

| Field Name | Description |
|---|---|
| `name` | Full name of the candidate |
| `email` | Email address |
| `phone` | Phone number |
| `address` | Home or postal address |
| `technical_skills` | Programming languages, frameworks, and tools |
| `experience` | Summary of work experience and years |
| `education` | Highest qualification and institution |

**Example fields for an invoice project:**

| Field Name | Description |
|---|---|
| `invoice_number` | Invoice or reference number |
| `invoice_date` | Date the invoice was issued |
| `vendor_name` | Name of the company or vendor |
| `total_amount` | Total amount due including tax |
| `due_date` | Payment due date |

### Step 4 — Upload documents

1. Open your project
2. Drag and drop files onto the upload area, or click **"Choose Files"** to browse
3. You can upload multiple files at once (PDFs, images, Word docs, etc.)
4. Click **"Upload"**

DataGrabber will process each file automatically. A progress indicator shows the status.

> Multi-page PDFs are read in full — the AI sees every page before extracting.

### Step 5 — View and download your data

Once processing is complete:

1. Your project page shows a table with all extracted data
2. Click **"Download Excel"** to get a `.xlsx` spreadsheet with all records
3. Each row is one document; each column is one of your fields

---

## 8. Change AI provider or model in the app

You can switch provider or model at any time — no restart needed:

1. Click your username (top-right) → **"AI Settings"**
2. Change the **Provider** dropdown
3. Select a **Model** from the list
4. Update your API key if switching to a different provider
5. Click **"Save Settings"**

### Available providers and models:

| Provider | Good for | Models available |
|---|---|---|
| **Google Gemini** | Best free tier, great at documents | gemini-2.5-flash, gemini-2.0-flash, gemini-3-flash, and more |
| **OpenAI** | Excellent accuracy | gpt-4o-mini (default), gpt-4.1, gpt-4.1-mini, ChatGPT-4o, GPT-5.2, GPT-5-mini |
| **OpenRouter** | Access 100+ models with one key | Various — enter your preferred model |
| **Ollama** | Fully offline/local, free | llama3.2 and any model you've pulled |

---

## 9. Supported file types

| Type | Formats |
|---|---|
| **PDF** | `.pdf` — including multi-page and scanned |
| **Images** | `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.bmp` |
| **Word documents** | `.doc`, `.docx` |
| **Text files** | `.txt` |
| **Spreadsheets** | `.xls`, `.xlsx`, `.csv` |

---

## 10. Troubleshooting

### "Python is not recognized" (Windows)

Python isn't in your PATH. Re-install Python from [python.org](https://www.python.org/downloads/) and tick **"Add Python to PATH"** during setup.

### "Port 8080 is already in use"

Another application is using port 8080. Either stop it, or run DataGrabber on a different port:

```bash
PORT=5001 python app.py
```

Then open [http://localhost:5001](http://localhost:5001).

### "Gemini API key not configured" or extraction fails

- Open `.env` and confirm `GEMINI_API_KEY=` (or your provider's key) is set correctly — no quotes, no spaces around the `=`
- Or go to **AI Settings** in the app and re-enter your key there

### Activation fails on Windows ("cannot be loaded")

Run this in PowerShell first:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Then try activating again.

### "Not found" for some fields after extraction

- Make sure your **field descriptions** are clear and specific (e.g. `Full name of the candidate`, not just `name`)
- Try a more powerful model (e.g. switch from `gpt-4o-mini` to `gpt-4.1` in AI Settings)
- For very dense PDFs, Gemini often performs well since it can process the native PDF format

### App runs but browser shows nothing / error page

- Make sure the terminal is still running `python app.py` — don't close it
- Try refreshing or going to [http://127.0.0.1:8080](http://127.0.0.1:8080) instead

---

## 11. FAQ

**Do I need to keep the terminal open while using the app?**  
Yes. The terminal window running `python app.py` must stay open. The app stops when you close it or press `Ctrl+C`.

**Is my data sent to the cloud?**  
Your documents are sent to whichever AI provider you configure (Gemini, OpenAI, etc.) for processing. If you use **Ollama**, everything stays on your machine. The app itself never sends data anywhere else.

**Can multiple people use it at the same time?**  
Yes. DataGrabber supports multiple user accounts. Each user can have their own AI settings and projects. By default it runs on your local machine, so others on the same network can access it at `http://your-ip-address:8080`.

**Can I use it without an API key?**  
You need at least one API key (or Ollama running locally). Processing requires an AI model to do the extraction.

**Where are my files stored?**  
Everything is stored locally in `~/DataGrabber/`:
- `~/DataGrabber/datagrabber.db` — the database
- `~/DataGrabber/uploads/` — uploaded documents and Excel outputs

**How do I update DataGrabber?**  
If you cloned with Git: `git pull` inside the folder, then `pip install -r requirements.txt` again.  
If you downloaded a ZIP: download the new version, copy your `.env` file into it, and run `pip install -r requirements.txt`.

**Can I run this on a server for my team?**  
Yes — for a shared server, use a production WSGI server like Gunicorn (already included in requirements):

```bash
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

---

*For in-app help, click the **Documentation** link in the navigation bar after logging in.*
Contact us: https://www.linkedin.com/showcase/datagrabber/about/?viewAsMember=true
