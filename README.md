# BioTwin Singapore

**Spatial decision support tool for converting Singapore's horticultural waste into biochar**

BioTwin is an interactive research prototype for assessing potential biochar production facilities in Singapore. It brings together spatial feedstock estimates, candidate locations, road transport, plant sizing, financial analysis and carbon accounting in one web interface.

**Repository:** [BPS5321-Project](https://github.com/mugheeskiyani115-oss/BPS5321-Project)  
**Branch to use:** `main`  
**Application port:** `8001`

> **Recommended for reviewers:** Use GitHub Codespaces (Option A) to run the complete application in a browser. GitHub itself hosts the source code; the Python server must be started before the website is available.

## A. Run in GitHub Codespaces (recommended)

This approach requires a GitHub account with access to the repository and access to GitHub Codespaces. No local Python installation is required.

1. Open the [`main` branch](https://github.com/mugheeskiyani115-oss/BPS5321-Project/tree/main).
2. Click **Code → Codespaces → Create codespace on main**. If Codespaces is not offered, use Option B below.
3. When the online VS Code workspace opens, select **Terminal → New Terminal**.
4. Run the following commands in the repository's root directory:

   ```bash
   python -m pip install -r requirements.txt
   python serve.py --host 0.0.0.0 --port 8001
   ```

5. Open the **Ports** tab in Codespaces. Find port **8001** and click **Open in Browser** (or follow the port forwarding prompt).
6. The **BioTwin Singapore** home page should appear. Select **Evaluate** to configure a scenario.

**Stopping the application:** Return to the terminal and press **Ctrl+C**. To conserve Codespaces usage, stop the Codespace from [github.com/codespaces](https://github.com/codespaces) when finished.

**Returning to an existing Codespace:** A Codespace does not automatically receive new GitHub commits. With no uncommitted local edits, update it by running:

```bash
git switch main
git pull --ff-only origin main
```

Then start the application again using the two commands in Step 4 (the dependency installation generally only needs to be repeated when requirements change).

## B. Run locally on Windows

**Prerequisites:** Python 3.10 or newer (Python 3.11 recommended) and an internet connection for the initial installation and map tiles. Git is needed only if cloning rather than downloading the ZIP. Install Python with the option to add it to PATH, or use the Windows `py` launcher.

1. Download the project from the `main` branch using **Code → Download ZIP** and extract it, **or** clone it:

   ```powershell
   git clone --branch main https://github.com/mugheeskiyani115-oss/BPS5321-Project.git
   cd BPS5321-Project
   ```

   If you downloaded a ZIP, open PowerShell in the extracted project folder instead.

2. Create the Python environment and install dependencies (from the folder containing `requirements.txt`):

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Start the website. **Either** double-click `RUN_BIOTWIN_8001.bat` (which expects `.venv` to exist), **or** run:

   ```powershell
   .\.venv\Scripts\python.exe serve.py --port 8001
   ```

4. Open [http://127.0.0.1:8001](http://127.0.0.1:8001) in your web browser if it does not open automatically.

Keep the terminal window open while using the website. Press **Ctrl+C** to stop it.

## C. Run locally on macOS or Linux

From a terminal, with Python 3.10+ and Git installed:

```bash
git clone --branch main https://github.com/mugheeskiyani115-oss/BPS5321-Project.git
cd BPS5321-Project
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python serve.py --port 8001
```

Visit [http://127.0.0.1:8001](http://127.0.0.1:8001). Press **Ctrl+C** in the terminal to stop the server.

## Using BioTwin

| Page | Purpose |
| --- | --- |
| **Home** | Project overview and context for the horticultural waste to biochar pathway. |
| **Evaluate** | Select a region, candidate plant site or sites, plant capacity, feedstock allocation and business assumptions; run a scenario. |
| **Results** | Review transport routes, plant performance, costs, financial outcomes, carbon metrics and alternative configurations. |
| **Saved** | Compare previously saved evaluations in the same browser. |
| **Evidence** | Inspect source assumptions, parameter information and available data validation tools. |

For a quick demonstration, open **Evaluate**, retain the default inputs, select the desired site and plant configuration, and click **Get results**. The application performs the evaluation through its Python API and displays the outputs in the browser.

## Troubleshooting

| Issue | What to do |
| --- | --- |
| **Website does not open** | Check that the Python server is still running. In Codespaces, open the forwarded **8001** port; locally, use `http://127.0.0.1:8001`. |
| **Port 8001 already in use** | Stop the previous BioTwin server using **Ctrl+C**, then retry. Close other processes using the port if necessary. |
| **`ModuleNotFoundError` or missing library** | Install dependencies again with the Python interpreter used to run the server: `python -m pip install -r requirements.txt`, or the `.venv` interpreter on Windows. |
| **Changes to GitHub are not showing** | In the existing Codespace, pull the latest `main` commit, restart the server, then refresh the browser with **Ctrl+Shift+R**. |
| **Map does not render correctly** | Use an updated Chrome, Edge or Firefox browser with WebGL enabled, and check that map tile services are reachable. |
| **Windows launcher says `.venv` not found** | Complete Windows installation Step 2 before opening `RUN_BIOTWIN_8001.bat`. |

To check whether the backend is responding, open `/api/health` at the same host and port; for a local run, visit [http://127.0.0.1:8001/api/health](http://127.0.0.1:8001/api/health).

## Technical structure

- **Backend:** FastAPI and Uvicorn, started by `serve.py`; API definitions in `api/server.py`.
- **Analytical model:** Python modules in `biotwin/`.
- **Frontend:** JavaScript, HTML and CSS in `web/` (no Node.js build step required).
- **Inputs:** Bundled model data and assumptions in `data/`.
- **Dependencies:** Listed in `requirements.txt`.
- **Optional checks:** Run `python -m pytest -q tests` from the repository root, after installing dependencies.

The project runs locally or in a Codespace. A **permanent public URL** would require separately deploying the FastAPI application to a hosting service; GitHub Pages alone cannot execute the Python backend.
