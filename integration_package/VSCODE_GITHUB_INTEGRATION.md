# 🔧 VSCode & GitHub Integration Guide

## Step-by-Step Integration Process

### 1. Update Your VSCode Project Structure

```bash
# In VSCode terminal
cd ~/Documents/Caravan_Scraper  # Your project directory

# Create new source files for Google enrichment
touch src/enrich_google.py
touch src/dashboard.py  
touch src/mail_merge.py

# Copy the enhanced code from my files
# Option A: If you downloaded the zip
unzip ~/Downloads/caravan_parks_enricher_v2.zip
cp caravan_parks_enricher/enrich_with_google_v2.py src/enrich_google.py
cp caravan_parks_enricher/dashboard.py src/dashboard.py
cp caravan_parks_enricher/mail_merge.py src/mail_merge.py

# Option B: Copy-paste the code directly from Claude
```

### 2. Update Your requirements.txt

Add these new dependencies to your existing `requirements.txt`:

```python
# Existing requirements...

# Google enrichment
googlemaps==4.10.0
python-dotenv==1.0.0
fuzzywuzzy==0.18.0
python-Levenshtein==0.23.0

# Dashboard
streamlit==1.30.0
streamlit-folium==0.17.4
folium==0.15.1
plotly==5.18.0

# Mail merge
python-docx==1.1.0
jinja2==3.1.3
email-validator==2.1.0
```

### 3. Modify Your Pipeline Runner

Create `src/run_full_pipeline.py`:

```python
#!/usr/bin/env python3
"""
Complete pipeline runner with Google enrichment
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd):
    """Run a command and check for errors"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        return False
    print(result.stdout)
    return True

def main():
    """Run complete pipeline"""
    
    # Your existing pipeline
    commands = [
        "python -m src.overpass_fetch --states NSW QLD VIC --out data/osm_seed.csv",
        "python -m src.brands.run_all --out data/brands_seed.csv",
        "python -m src.merge_dedupe data/osm_seed.csv data/brands_seed.csv --out data/parks_merged.csv",
        "python -m src.area_nsw --in data/parks_merged.csv --out data/parks_merged_nsw.csv",
        "python -m src.area_qld --in data/parks_merged_nsw.csv --out data/parks_merged_nsw_qld.csv",
        "python -m src.classify --in data/parks_merged_nsw_qld.csv --out data/caravan_parks_master.csv",
        
        # NEW: Google enrichment step
        "python -m src.enrich_google --in data/caravan_parks_master.csv --out data/parks_enriched_final.csv"
    ]
    
    for cmd in commands:
        if not run_command(cmd):
            print(f"Pipeline failed at: {cmd}")
            sys.exit(1)
    
    print("\n✅ Pipeline complete!")
    print("\nNext steps:")
    print("1. Launch dashboard: streamlit run src/dashboard.py")
    print("2. Generate outreach: python -m src.mail_merge")

if __name__ == "__main__":
    main()
```

### 4. Git Workflow

```bash
# Stage your changes
git add src/enrich_google.py
git add src/dashboard.py
git add src/mail_merge.py
git add requirements.txt
git add src/run_full_pipeline.py

# Commit with descriptive message
git commit -m "feat: Add Google Places enrichment with development scoring

- Integrate Google Places API for contact details and reviews
- Add development scoring algorithm (0-100)
- Implement chain detection (BIG4, NRMA, etc)
- Create Streamlit dashboard for data exploration
- Add mail merge system for outreach
- Support Victoria parks without land size data"

# Push to GitHub
git push origin main

# Or if using feature branch
git push origin enhanced-google-enrichment
```

### 5. VSCode Workspace Settings

Create `.vscode/settings.json`:

```json
{
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": true,
    "python.formatting.provider": "black",
    "python.testing.pytestEnabled": true,
    "files.exclude": {
        "**/__pycache__": true,
        "**/*.pyc": true,
        ".venv": true
    },
    "python.envFile": "${workspaceFolder}/.env",
    "terminal.integrated.env.linux": {
        "PYTHONPATH": "${workspaceFolder}"
    }
}
```

### 6. Environment Variables

Create `.env` file (don't commit this!):

```bash
# Google API
GOOGLE_API_KEY=your_actual_key_here

# Optional: Email settings for automated outreach
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

Add to `.gitignore`:

```bash
# Environment variables
.env
.env.local

# Cache files
google_places_cache*.json

# Output files
data/parks_enriched*.csv
data/parks_enriched*.xlsx
outputs/
```

## Using Claude Code for Development

### Install Claude Code (if not already installed)

```bash
# Install via pip
pip install claude-code

# Or via brew (macOS)
brew install claude-code

# Configure with your API key
claude-code configure
```

### Common Claude Code Commands for This Project

#### 1. Debug Data Issues
```bash
# When you hit a problem
claude-code "My merge_dedupe is creating duplicates for BIG4 parks. 
Here's the error: [paste error]. 
The code is in src/merge_dedupe.py"
```

#### 2. Add New Features
```bash
# Request new functionality
claude-code "Add a function to src/enrich_google.py that extracts 
operating hours and identifies 24/7 parks as high-value targets"
```

#### 3. Optimize Performance
```bash
# Speed improvements
claude-code "The Google API enrichment takes 2 hours for 1600 parks. 
How can I parallelize src/enrich_google.py using asyncio?"
```

#### 4. Fix Integration Issues
```bash
# When components don't work together
claude-code "The dashboard.py can't read the output from enrich_google.py. 
Column names don't match. How do I fix this?"
```

#### 5. Generate Reports
```bash
# Create new outputs
claude-code "Create a function that generates a PDF report 
of the top 50 development opportunities with maps and charts"
```

### Claude Code Best Practices

1. **Be Specific**: Include file paths and error messages
2. **Provide Context**: Mention what you're trying to achieve
3. **Share Code**: Use `--file src/problem_file.py` to include code
4. **Iterative Development**: Start simple, then refine

Example workflow:
```bash
# Initial implementation
claude-code "Create a basic email template for caravan park outreach"

# Refinement
claude-code "The email template is too generic. Add personalization 
based on park size, location, and chain status"

# Debugging
claude-code "The template crashes when chain_name is None. Fix this"
```

## VSCode Extensions to Install

1. **Python** - Microsoft's official Python extension
2. **Pylance** - Better Python IntelliSense
3. **GitLens** - Enhanced Git integration
4. **GitHub Copilot** - AI pair programming (works great with Claude Code)
5. **Python Docstring Generator** - Auto-generate docstrings
6. **CSV to Table** - View CSV files as tables

## Testing Your Integration

### Run Tests
```bash
# Test Google API connection
python src/test_api.py

# Test enrichment on small dataset
python -m src.enrich_google --in data/test_sample.csv --out data/test_output.csv --limit 10

# Test dashboard locally
streamlit run src/dashboard.py --server.headless true
```

### Verify Output Quality
```python
# Quick verification script
import pandas as pd

df = pd.read_csv('data/parks_enriched_final.csv')
print(f"Total parks: {len(df)}")
print(f"Parks with phone: {df['phone'].notna().sum()}")
print(f"Chains identified: {df['is_chain'].sum()}")
print(f"High opportunity (70+): {(df['development_score'] > 70).sum()}")
print(f"Victoria parks: {(df['state'] == 'VIC').sum()}")
```

## Deployment to Production

### Option 1: GitHub Actions (Automated)
Create `.github/workflows/enrich.yml`:

```yaml
name: Weekly Enrichment
on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday
  workflow_dispatch:  # Manual trigger

jobs:
  enrich:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - uses: actions/setup-python@v2
    - run: pip install -r requirements.txt
    - run: python -m src.run_full_pipeline
      env:
        GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
    - uses: actions/upload-artifact@v2
      with:
        name: enriched-data
        path: data/parks_enriched_final.csv
```

### Option 2: Streamlit Cloud (Dashboard)
1. Push to GitHub
2. Go to share.streamlit.io
3. Connect your repo
4. Set secrets (API key)
5. Deploy!

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No module named googlemaps" | Run `pip install -r requirements.txt` |
| "API key not found" | Create `.env` file with `GOOGLE_API_KEY=...` |
| "Rate limit exceeded" | Add `time.sleep(0.5)` between API calls |
| "Duplicate parks in output" | Check merge key in `merge_dedupe.py` |
| "Dashboard won't load" | Check if port 8501 is blocked |

## Next Steps

1. ✅ Integrate enhanced enrichment
2. ⬜ Add Victoria land size estimation
3. ⬜ Implement async API calls for speed
4. ⬜ Add email automation
5. ⬜ Create investor pitch deck generator

Ready to enhance your pipeline! 🚀
