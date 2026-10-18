# Run from PowerShell. Never paste a key into this file or a command argument.
[CmdletBinding()]
param(
    [string]$Python,
    [switch]$Clipboard,
    [switch]$ReplaceKey,
    [switch]$ForgetKey,
    [switch]$NoSaveKey
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'groq_credentials.ps1')
$credentialPath = Get-GroqCredentialPath
if ($ForgetKey) {
    if (Test-Path -LiteralPath $credentialPath -PathType Leaf) {
        [IO.File]::Delete($credentialPath)
    }
    Write-Host 'Remembered Groq key removed. No account memories or shell-provided keys were changed.'
    return
}
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = @(
        (Join-Path $projectRoot '.venv\Scripts\python.exe'),
        (Join-Path $env:USERPROFILE 'anaconda3\python.exe')
    ) | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
    if (-not $Python) {
        $command = Get-Command python -ErrorAction SilentlyContinue
        if ($command) { $Python = $command.Source }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw 'Python was not found. Pass -Python with the supported python.exe path.'
}

$settingNames = @('AEGM_CONFIG_PATH', 'AEGM_LLM_PROVIDER', 'GROQ_MODEL',
    'AEGM_ALLOW_EXTERNAL_LLM', 'GROQ_API_KEY')
$previousSettings = @{}
foreach ($settingName in $settingNames) {
    $previousSettings[$settingName] = [Environment]::GetEnvironmentVariable($settingName, 'Process')
}

Push-Location -LiteralPath $projectRoot
try {
    Write-Host 'App text and relevant memory context are sent to Groq while enabled.'
    $newKey = $false
    $replacementKey = $null
    if (-not $ReplaceKey -and -not [string]::IsNullOrWhiteSpace($env:GROQ_API_KEY)) {
        Write-Host 'Using the Groq key already configured in this environment.'
    } elseif (-not $ReplaceKey -and (Test-Path -LiteralPath $credentialPath -PathType Leaf)) {
        $replacementKey = Read-GroqCredential -Path $credentialPath
        Write-Host 'Using your remembered Groq key (Windows-encrypted, outside the repository).'
    } else {
        $newKey = $true
        Write-Host 'One-time setup: confirm your Groq account is on the Free plan.'
        Write-Host 'A new key is tested once, then remembered using Windows user-profile encryption.'
        Write-Host 'Use a replacement key if you previously shared one in chat.'
        if ($Clipboard) {
            Write-Host 'Copy your replacement key, then press Enter here. Do not paste it into this terminal.'
            $null = Read-Host 'Press Enter to read the clipboard privately (Ctrl+C cancels)'
            try {
                $clipboardText = Get-Clipboard -Raw -ErrorAction Stop
            } catch {
                throw 'Clipboard could not be read. Use the normal masked prompt instead.'
            }
            if ([string]::IsNullOrWhiteSpace($clipboardText)) {
                throw 'Clipboard is empty. No API request was made.'
            }
            try {
                $replacementKey = ConvertTo-SecureString -String $clipboardText.Trim() -AsPlainText -Force
            } finally {
                Remove-Variable clipboardText
            }
        } else {
            $replacementKey = Read-Host 'Replacement Groq API key (hidden; Enter cancels)' -AsSecureString
        }
    }
    if ($null -ne $replacementKey) {
        if ($replacementKey.Length -eq 0) {
            $replacementKey.Dispose()
            Write-Host 'Cancelled. No API request was made.'
            return
        }
        $keyLength = $replacementKey.Length
        if ($keyLength -lt 20) {
            $replacementKey.Dispose()
            throw "Only $keyLength characters were received. No request was made. Retry with -Clipboard."
        }
        Write-Host "Received $keyLength characters; the key itself is hidden."
        $secretPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($replacementKey)
        try {
            $env:GROQ_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($secretPointer)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($secretPointer)
            $replacementKey.Dispose()
            Remove-Variable replacementKey, secretPointer
        }
    }

    $env:AEGM_CONFIG_PATH = Join-Path $projectRoot 'config.groq.yaml'
    $env:AEGM_LLM_PROVIDER = 'groq'
    if ([string]::IsNullOrWhiteSpace($env:GROQ_MODEL)) { $env:GROQ_MODEL = 'openai/gpt-oss-20b' }
    $env:AEGM_ALLOW_EXTERNAL_LLM = '1'

    if ($newKey) {
        & $Python -B -m src.groq_provider --allow-live-request
        if ($LASTEXITCODE -ne 0) {
            throw 'Groq connection test failed. Key was not saved and Streamlit was not started. Check the error above.'
        }
        if (-not $NoSaveKey) {
            $keyToSave = ConvertTo-SecureString -String $env:GROQ_API_KEY -AsPlainText -Force
            try {
                Save-GroqCredential -Key $keyToSave -Path $credentialPath
                Write-Host 'Key remembered securely for this Windows account. Future launches need no key prompt.'
            } catch {
                Write-Warning 'Windows secure saving failed. Any previous saved key is unchanged. Use -ReplaceKey again next launch, or configure GROQ_API_KEY.'
            } finally { $keyToSave.Dispose() }
        }
    } else {
        Write-Host 'Startup API probe skipped to avoid unnecessary quota use. Use -ReplaceKey if this key has expired.'
    }

    Write-Host 'Starting Streamlit; Ctrl+C stops it.'
    & $Python -B -m streamlit run app/account_app.py --server.address 127.0.0.1 --server.headless true
    if ($LASTEXITCODE -ne 0) {
        throw 'Streamlit stopped with an error.'
    }
} finally {
    # Child processes inherit the key; stop Streamlit before closing this shell.
    $env:GROQ_API_KEY = $null
    foreach ($settingName in $settingNames) {
        [Environment]::SetEnvironmentVariable($settingName, $previousSettings[$settingName], 'Process')
    }
    $previousSettings.Clear()
    Pop-Location
}
