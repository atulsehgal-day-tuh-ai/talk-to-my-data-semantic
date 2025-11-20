<#
.SYNOPSIS
  Talk-to-My-Data  Local runner for Windows
.DESCRIPTION
  Loads environment variables from configs\dev.env,
  installs dependencies, activates the venv,
  and launches the Streamlit app.
#>

Write-Host "Starting Talk-to-My-Data (Windows Mode)" -ForegroundColor Cyan

# --- Step 1: Define paths ---
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ConfigFile = Join-Path $ProjectRoot "configs\dev.env"
$ConfigYaml = Join-Path $ProjectRoot "configs\settings.yaml"

Write-Host "Project root: $ProjectRoot"
Write-Host "Using config:  $ConfigFile"

# --- Step 2: Load environment variables ---
if (Test-Path $ConfigFile) {
    Write-Host "Loading environment variables..."
    Get-Content $ConfigFile | ForEach-Object {
        if ($_ -and ($_ -notmatch '^#')) {
            $pair = $_ -split '=', 2
            if ($pair.Length -eq 2) {
                [System.Environment]::SetEnvironmentVariable($pair[0], $pair[1])
            }
        }
    }
} else {
    Write-Host "ERROR: Config file not found at $ConfigFile" -ForegroundColor Red
    exit 1
}

# --- Step 3: Read Python version from YAML config ---
if (Test-Path $ConfigYaml) {
    try {
        $yamlContent = Get-Content $ConfigYaml -Raw | ConvertFrom-Yaml
        $pythonVersion = $yamlContent.python_version
        if (-not $pythonVersion) {
            $pythonVersion = "3.10"
        }
    }
    catch {
        Write-Host "Could not parse settings.yaml  defaulting to Python 3.10" -ForegroundColor Yellow
        $pythonVersion = "3.10"
    }
} else {
    Write-Host "settings.yaml not found  defaulting to Python 3.10" -ForegroundColor Yellow
    $pythonVersion = "3.10"
}

# --- Step 4: Locate specific Python version ---
$pythonCmd = "python$pythonVersion"
$pythonPath = (Get-Command $pythonCmd -ErrorAction SilentlyContinue).Source

if (-not $pythonPath) {
    Write-Host ("Python " + $pythonVersion + " not found on system.") -ForegroundColor Red
    Write-Host ("Please install it via: py -" + $pythonVersion + " install") -ForegroundColor Yellow
    exit 1
} else {
    Write-Host ("Using Python " + $pythonVersion + " from: " + $pythonPath) -ForegroundColor Green
}

# --- Step 5: Create virtual environment if missing ---
$venvPath = Join-Path $ProjectRoot ".venv"
if (!(Test-Path $venvPath)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $pythonPath -m venv $venvPath
} else {
    Write-Host "Virtual environment already exists." -ForegroundColor DarkGray
}

# --- Step 6: Activate virtual environment ---
Write-Host "Activating virtual environment..." -ForegroundColor Cyan
& "$venvPath\Scripts\Activate.ps1"

# --- Step 7: Install dependencies ---
Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r "$ProjectRoot\requirements.txt" --quiet

# --- Step 8: Run Streamlit app ---
Write-Host "Launching Streamlit app..." -ForegroundColor Green
streamlit run "$ProjectRoot\src\main_app.py"



