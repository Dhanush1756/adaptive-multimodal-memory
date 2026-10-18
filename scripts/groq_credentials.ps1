# Windows current-user DPAPI storage. No plaintext credential is written to disk.
function Get-GroqCredentialPath {
    if ($env:OS -ne 'Windows_NT' -or [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
        throw 'Remembered credentials require Windows user-profile encryption. Use GROQ_API_KEY instead.'
    }
    return Join-Path $env:LOCALAPPDATA 'AdaptiveEvidenceGroundedMemory\credentials\groq.dpapi'
}

function Read-GroqCredential {
    param([Parameter(Mandatory=$true)][string]$Path)
    if ($env:OS -ne 'Windows_NT') {
        throw 'DPAPI credential loading is supported on Windows only.'
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    try {
        return ConvertTo-SecureString -String ([IO.File]::ReadAllText($Path).Trim()) -ErrorAction Stop
    } catch {
        throw 'Saved Groq key could not be decrypted. Run the launcher with -ReplaceKey to enter it again.'
    }
}

function Save-GroqCredential {
    param(
        [Parameter(Mandatory=$true)][Security.SecureString]$Key,
        [Parameter(Mandatory=$true)][string]$Path
    )
    if ($env:OS -ne 'Windows_NT') {
        throw 'DPAPI credential saving is supported on Windows only.'
    }
    # No -Key or -AsPlainText: Windows encrypts for the current user/machine.
    $encrypted = ConvertFrom-SecureString -SecureString $Key -ErrorAction Stop
    $parent = Split-Path -Parent ([IO.Path]::GetFullPath($Path))
    $null = [IO.Directory]::CreateDirectory($parent)
    $temporary = Join-Path $parent ([IO.Path]::GetRandomFileName())
    $created = $false
    try {
        $bytes = [Text.Encoding]::ASCII.GetBytes($encrypted)
        $stream = [IO.File]::Open($temporary, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
        $created = $true
        try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            # PowerShell 5.1 otherwise coerces $null to an empty backup path.
            [IO.File]::Replace($temporary, $Path, [NullString]::Value)
        } else {
            [IO.File]::Move($temporary, $Path)
        }
    } finally {
        # Only this operation's freshly created temporary ciphertext is removed.
        if ($created -and (Test-Path -LiteralPath $temporary -PathType Leaf)) {
            [IO.File]::Delete($temporary)
        }
    }
}
