# Creates/reuses a Windows DPAPI-protected DATA key, never a Groq credential.
[CmdletBinding()]
param([string]$Python='python', [switch]$Research, [switch]$Groq)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$folder=Join-Path $env:LOCALAPPDATA 'AdaptiveEvidenceGroundedMemory\credentials'
$keyFile=Join-Path $folder 'data-key.dpapi'
if (-not (Test-Path -LiteralPath $keyFile)) {
    New-Item -ItemType Directory -Force -Path $folder | Out-Null
    $dataBytes=New-Object byte[] 32
    $rng=[Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($dataBytes) } finally { $rng.Dispose() }
    $dataText=[Convert]::ToBase64String($dataBytes).Replace('+','-').Replace('/','_')
    $secured=ConvertTo-SecureString -String $dataText -AsPlainText -Force
    # CreateNew refuses to overwrite a key created by another launch.
    $stream=[IO.File]::Open($keyFile,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try {
        $payload=[Text.Encoding]::UTF8.GetBytes((ConvertFrom-SecureString $secured))
        $stream.Write($payload,0,$payload.Length)
        $stream.Flush()
    } finally { $stream.Dispose();[Array]::Clear($dataBytes,0,$dataBytes.Length);$dataText=$null }
}
$oldKey=$env:AEGM_DATA_KEY
$oldConfig=$env:AEGM_CONFIG_PATH
$oldGroq=$env:GROQ_API_KEY
$oldConsent=$env:AEGM_ALLOW_EXTERNAL_LLM
try {
    $secured=Get-Content -LiteralPath $keyFile -Raw | ConvertTo-SecureString
    $env:AEGM_DATA_KEY=[Net.NetworkCredential]::new('', $secured).Password
    $profile=if ($Research) {'config.research.yaml'} else {'config.protected.yaml'}
    $env:AEGM_CONFIG_PATH=Join-Path $root $profile
    if ($Groq) {
        . (Join-Path $PSScriptRoot 'groq_credentials.ps1')
        if ([string]::IsNullOrWhiteSpace($env:GROQ_API_KEY)) {
            $groqKey=Read-GroqCredential -Path (Get-GroqCredentialPath)
            if ($null -eq $groqKey) { throw 'No saved Groq credential. Configure it separately or launch without -Groq for deterministic mode.' }
            $env:GROQ_API_KEY=[Net.NetworkCredential]::new('', $groqKey).Password
        }
        $env:AEGM_ALLOW_EXTERNAL_LLM='1'
    } else { $env:AEGM_ALLOW_EXTERNAL_LLM='0' }
    Write-Host 'Protected workspace profile selected. External processing still requires server opt-in and account consent.'
    & $Python -B -m streamlit run (Join-Path $root 'app/account_app.py') --server.address 127.0.0.1
} finally {
    $env:AEGM_DATA_KEY=$oldKey
    $env:AEGM_CONFIG_PATH=$oldConfig
    $env:GROQ_API_KEY=$oldGroq
    $env:AEGM_ALLOW_EXTERNAL_LLM=$oldConsent
}
