"""Actual Windows DPAPI, disposable profiles and fake Python/API/app processes."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which('powershell.exe')
pytestmark = pytest.mark.skipif(os.name != 'nt' or not POWERSHELL,
                              reason='Windows PowerShell/DPAPI integration test')
KEY = 'offline-launcher-fixture-not-a-real-api-key'


@pytest.fixture(scope='module', autouse=True)
def windows_profile_supports_dpapi():
    # Sandboxed impersonation can deny DPAPI even on Windows. Detect the native
    # prerequisite separately; do not report mocked encryption as a real pass.
    probe = subprocess.run([POWERSHELL,'-NoProfile','-NonInteractive','-Command',
        "$ErrorActionPreference='Stop'; $s=ConvertTo-SecureString 'disposable-dpapi-prerequisite' -AsPlainText -Force; "
        "try { $null=ConvertFrom-SecureString $s } finally { $s.Dispose() }"],
        capture_output=True,text=True,timeout=20)
    if probe.returncode:
        pytest.skip('Native Windows DPAPI unavailable in this process user-profile context')


@pytest.fixture
def launcher(tmp_path):
    root = tmp_path/'project'
    scripts = root/'scripts'
    scripts.mkdir(parents=True)
    for name in ['start_groq.ps1','groq_credentials.ps1']:
        shutil.copyfile(ROOT/'scripts'/name,scripts/name)
    fake = root/'fake_python.ps1'
    fake.write_text('''
$module = $args[2]
$record = @{ module=$module; key_length=$env:GROQ_API_KEY.Length; model=$env:GROQ_MODEL }
$record | ConvertTo-Json -Compress | Add-Content -LiteralPath $env:AEGM_LAUNCHER_LOG
if ($module -eq 'src.groq_provider' -and $env:AEGM_FAKE_PROBE_FAIL -eq '1') {
    $global:LASTEXITCODE = 1
} else { $global:LASTEXITCODE = 0 }
''',encoding='utf-8')
    runner = root/'runner.ps1'
    runner.write_text('''
$ErrorActionPreference = 'Stop'
function Read-Host {
    param([string]$Prompt, [switch]$AsSecureString)
    if (-not $env:AEGM_TEST_INPUT) { throw 'Unexpected credential prompt in test' }
    if ($AsSecureString) { return ConvertTo-SecureString $env:AEGM_TEST_INPUT -AsPlainText -Force }
    return ''
}
function Get-Clipboard {
    param([switch]$Raw)
    if (-not $env:AEGM_TEST_INPUT) { throw 'Unexpected clipboard access in test' }
    return $env:AEGM_TEST_INPUT
}
$parameters = @{ Python=(Join-Path $PSScriptRoot 'fake_python.ps1'); Clipboard=$true }
if ($env:AEGM_TEST_REPLACE -eq '1') { $parameters.ReplaceKey=$true }
if ($env:AEGM_TEST_FORGET -eq '1') { $parameters.ForgetKey=$true }
if ($env:AEGM_TEST_NOSAVE -eq '1') { $parameters.NoSaveKey=$true }
& (Join-Path $PSScriptRoot 'scripts/start_groq.ps1') @parameters
''',encoding='utf-8')
    env = os.environ.copy()
    env.pop('GROQ_API_KEY',None)
    env['LOCALAPPDATA'] = str(tmp_path/'disposable_profile')
    env['AEGM_LAUNCHER_LOG'] = str(tmp_path/'calls.jsonl')
    cache = Path(env['LOCALAPPDATA'])/'AdaptiveEvidenceGroundedMemory'/'credentials'/'groq.dpapi'

    def run(**changes):
        child = {**env,**changes}
        result = subprocess.run([POWERSHELL,'-NoProfile','-NonInteractive','-File',str(runner)],
                                env=child,capture_output=True,text=True,timeout=30)
        assert KEY not in result.stdout+result.stderr
        return result

    def calls():
        path = Path(env['AEGM_LAUNCHER_LOG'])
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    return run,calls,cache,env,root


def test_dpapi_first_setup_then_no_prompt_or_extra_api_probe(launcher):
    run,calls,cache,env,root = launcher
    assert run(AEGM_TEST_INPUT=KEY).returncode == 0
    assert cache.is_file() and KEY not in cache.read_text()
    assert [r['module'] for r in calls()]==['src.groq_provider','streamlit']
    result = run()  # mocks fail if a second prompt or clipboard read occurs
    assert result.returncode == 0,result.stderr
    assert 'remembered Groq key' in result.stdout
    assert [r['module'] for r in calls()]==['src.groq_provider','streamlit','streamlit']
    assert all(r['key_length']==len(KEY) for r in calls())
    # Verify exact round trip with the real Windows DPAPI, not just a length.
    check = root/'check.ps1'
    check.write_text('''
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'scripts/groq_credentials.ps1')
$secret=Read-GroqCredential -Path (Get-GroqCredentialPath)
$pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try {
    if ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) -ne $env:AEGM_TEST_INPUT) { throw 'DPAPI mismatch' }
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    $secret.Dispose()
}
''')
    probe = subprocess.run([POWERSHELL,'-NoProfile','-NonInteractive','-File',str(check)],
                           env={**env,'AEGM_TEST_INPUT':KEY},capture_output=True,text=True,timeout=30)
    assert probe.returncode == 0,probe.stderr
    assert not probe.stdout.strip()


def test_failed_replacement_preserves_working_cache_and_forget_is_scoped(launcher):
    run,calls,cache,_,_ = launcher
    assert run(AEGM_TEST_INPUT=KEY).returncode==0
    original = cache.read_bytes()
    failed = run(AEGM_TEST_INPUT='different-offline-fixture-key-value',
                 AEGM_TEST_REPLACE='1',AEGM_FAKE_PROBE_FAIL='1')
    assert failed.returncode!=0
    assert cache.read_bytes()==original
    assert [r['module'] for r in calls()]==['src.groq_provider','streamlit','src.groq_provider']
    sentinel = cache.parent/'unrelated.txt'
    sentinel.write_text('preserve unrelated user files')
    assert run(AEGM_TEST_FORGET='1').returncode==0
    assert not cache.exists() and sentinel.read_text()=='preserve unrelated user files'
    assert len(calls())==3


def test_successful_replacement_persists_new_key(launcher):
    run,calls,cache,_,_ = launcher
    assert run(AEGM_TEST_INPUT=KEY).returncode==0
    original = cache.read_bytes()
    assert run(AEGM_TEST_INPUT=KEY+'-replacement',AEGM_TEST_REPLACE='1').returncode==0
    assert cache.read_bytes()!=original
    assert run().returncode==0
    assert calls()[-1]['key_length']==len(KEY+'-replacement')


def test_environment_key_needs_no_prompt_and_is_not_saved(launcher):
    run,calls,cache,_,_ = launcher
    assert run(GROQ_API_KEY=KEY,GROQ_MODEL='configured-test-model').returncode==0
    assert not cache.exists()
    assert [r['module'] for r in calls()]==['streamlit']
    assert calls()[0]['model']=='configured-test-model'


def test_no_save_retains_ephemeral_mode(launcher):
    run,calls,cache,_,_ = launcher
    assert run(AEGM_TEST_INPUT=KEY,AEGM_TEST_NOSAVE='1').returncode==0
    assert not cache.exists()
    assert [r['module'] for r in calls()]==['src.groq_provider','streamlit']


def test_corrupt_cache_has_generic_error_and_no_api_request(launcher):
    run,calls,cache,_,_ = launcher
    cache.parent.mkdir(parents=True)
    cache.write_text('corrupted ciphertext fixture')
    result = run()
    assert result.returncode!=0 and 'could not be decrypted' in result.stderr
    assert 'corrupted ciphertext fixture' not in result.stderr
    assert not calls() and cache.read_text()=='corrupted ciphertext fixture'
