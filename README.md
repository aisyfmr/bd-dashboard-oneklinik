# OneKlinik BD Dashboard

A Flask web dashboard for the OneKlinik Business Development team, with separate views for IHC and Corp Wellness leads.

## Pages

| URL | Description |
|-----|-------------|
| `/` | Redirects to `/ihc` |
| `/ihc` | IHC Dashboard (Company · Apartment · Hotel) |
| `/cw` | Corp Wellness Dashboard (HR · Broker · Insurance) |

## Setup (Windows)

### 1. Prerequisites
Make sure Python 3.9+ is installed. Check with:
```
python --version
```
If not installed, download from https://python.org/downloads — tick **"Add Python to PATH"** during setup.

### 2. Open a terminal in the project folder
In File Explorer, navigate to the `BD Dashboard` folder, then open a terminal:
- Right-click inside the folder → **Open in Terminal**, or
- Press `Ctrl+L` in the address bar, type `cmd`, press Enter

### 3. Create a virtual environment
```
python -m venv venv
```

### 4. Activate the virtual environment
```
venv\Scripts\activate
```
You should see `(venv)` appear at the start of your prompt.

### 5. Install dependencies
```
pip install -r requirements.txt
```

### 6. Run the app
```
python app.py
```

### 7. Open in browser
Go to: **http://localhost:5000**

---

## Data file: `data.json`

Add leads by appending entries to `data.json`. Each entry must follow this structure:

```json
{
  "companyName":    "PT Example",
  "icpSegment":     "IHC - Company",
  "location":       "Jakarta Selatan",
  "contactName":    "John Doe",
  "contactTitle":   "HR Manager",
  "contactEmail":   "john@example.co.id",
  "outreachStatus": "New",
  "createdTime":    "2026-04-28T09:00:00"
}
```

### Valid `icpSegment` values
- `IHC - Company`
- `IHC - Apartment`
- `IHC - Hotel`
- `Corp Wellness - HR`
- `Corp Wellness - Broker`
- `Corp Wellness - Insurance`

### Valid `outreachStatus` values
`New` · `Contacted` · `Replied` · `Follow Up` · `Meeting Set` · `Won` · `Not a Fit`

### `createdTime` format
ISO 8601 — `YYYY-MM-DDTHH:MM:SS` (e.g. `2026-04-28T09:00:00`)

---

## Stopping the server
Press `Ctrl+C` in the terminal.

## Restarting after closing the terminal
```
venv\Scripts\activate
python app.py
```
