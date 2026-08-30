Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "DEMONSTRATION: CRYPTOGRAPHIC EVIDENCE INTEGRITY & TAMPER DETECTION" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan

$sourceCapsule = "capsules/case-01.zip"
$tempDir = "scratch/tamper_demo"
$tamperedZip = "scratch/case-01-tampered.zip"

if (Test-Path "scratch") { Remove-Item -Recurse -Force "scratch" }
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

Write-Host "`n[1] Extracting legitimate reproduction capsule: $sourceCapsule..."
Expand-Archive -Path $sourceCapsule -DestinationPath $tempDir -Force

Write-Host "[2] Simulating adversary/malicious edit: Hand-editing manifest.json..."
Write-Host "    -> Changing pre-patch retries_per_request from 7.0 to 3.0 to fake lower amplification"
$manifestPath = "$tempDir/manifest.json"
$manifestContent = Get-Content $manifestPath -Raw
$manifestContent = $manifestContent.Replace('"retries_per_request": 7.0', '"retries_per_request": 3.0')
Set-Content -Path $manifestPath -Value $manifestContent -Encoding UTF8

Write-Host "[3] Repackaging tampered archive to $tamperedZip..."
Compress-Archive -Path "$tempDir/*" -DestinationPath $tamperedZip -Force

Write-Host "`n================================================================================" -ForegroundColor Red
Write-Host "TEST A: REPLAYING TAMPERED CAPSULE (EXPECTED: LOUD TAMPER DETECTION FAILURE)" -ForegroundColor Red
Write-Host "================================================================================" -ForegroundColor Red
python -m changeproof.replay $tamperedZip
$tamperExitCode = $LASTEXITCODE
Write-Host "Exit Code for Tampered Capsule: $tamperExitCode (Non-zero indicates loud failure)"

Write-Host "`n================================================================================" -ForegroundColor Green
Write-Host "TEST B: REPLAYING ORIGINAL UNTOUCHED CAPSULE (EXPECTED: PASS)" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Green
python -m changeproof.replay $sourceCapsule
$cleanExitCode = $LASTEXITCODE
Write-Host "Exit Code for Untouched Capsule: $cleanExitCode (0 indicates success)"

# Cleanup
Remove-Item -Recurse -Force "scratch"
Write-Host "`n================================================================================" -ForegroundColor Cyan
Write-Host "TAMPER DETECTION DEMO COMPLETED SUCCESSFULLY" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
