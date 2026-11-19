BIOTWIN SINGAPORE | LOCAL WINDOWS UPDATE

This ZIP does NOT replace your complete project. It updates the existing FastAPI/JavaScript website you showed in your screenshot. GitHub is not involved.

1. Open Downloads\BPS5321-Project-ui-changes\BPS5321-Project-ui-changes (the folder containing serve.py, api, biotwin, web, data).
2. Extract the CONTENTS of this ZIP directly into that folder. You should see UPDATE_AND_RUN.bat alongside serve.py.
3. Double click UPDATE_AND_RUN.bat. It applies the changes, installs dependencies, syntax checks, and launches the web server.
4. Open http://localhost:8000. Go to Evaluate, select a feedstock allocation, Get results, and Export PDF report.
5. Next time just double-click RUN_BIOTWIN.bat.

Expected additions:
- Black/white Times New Roman advisory-style scenario PDF from Results.
- Six PWC sector synthetic allocation option in Evaluate, and comparison in Evidence.
- Existing research model preserved; original data remains untouched.

IMPORTANT DATA NOTE: The six sectors correspond to actual administrative collection zones, but their numerical shares (22,20,16,15,14,13 percent) come from a SYNTHETIC distribution described in the Word document, not real operator tonnage observations. The observed 2025 national figure is 232,000 t; matching the national sum proves mass balance only.

The updater creates .before-consulting-upgrade.bak backups of changed files. It will reject a project whose structure does not match the FastAPI version. No Python source files are overwritten unless the compatibility checks all pass.

You manage your own GitHub commits and pushes. This ZIP does not connect to GitHub.
