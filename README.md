# Auto-Enter Assistant

A high-precision script that automatically simulates pressing the "Enter" key at an exact specified time. This is useful for securing limited bookings, flash sales, or sending messages at precise moments.

## Prerequisites

- Python 3
- `pyautogui` library

## Installation

macOS restricts system-wide package installations. The recommended way to install and run this tool is by using an isolated Python Virtual Environment (`venv`).

### Step 1: Set up a virtual environment
Open your terminal, navigate to this directory, and run:
```bash
python3 -m venv .venv
```

### Step 2: Activate the virtual environment
```bash
source .venv/bin/activate
```

### Step 3: Install dependencies
```bash
pip3 install pyautogui
```

## Usage

While your virtual environment is active, you can run the script:

```bash
./auto_enter.py -t <TARGET_TIME> -l <LEAD_MILLISECONDS>
```

### Examples
Trigger the Enter key at exactly 6:00:00 PM with an 80ms lead time to account for network/processing delay:
```bash
./auto_enter.py -t 18:00:00 -l 80
```

Trigger the Enter key at 6:00:00.500 PM:
```bash
./auto_enter.py -t 18:00:00.500 -l 80
```

### Important: macOS Accessibility Permissions
The first time you run this script on macOS, the system might block it from simulating keystrokes. 
If nothing happens when the timer finishes:
1. Go to **System Settings > Privacy & Security > Accessibility**.
2. Make sure your Terminal app (or Python/IDE) is allowed to control your computer.

### Quitting the virtual environment
When you are done using the script, simply type:
```bash
deactivate
```
