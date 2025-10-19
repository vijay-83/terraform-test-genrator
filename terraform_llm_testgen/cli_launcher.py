import os
import sys
import subprocess

# Find installed app.py location
app_path = os.path.join(os.path.dirname(__file__), "app.py")

# Run Streamlit
subprocess.run([sys.executable, "-m", "streamlit", "run", app_path])
