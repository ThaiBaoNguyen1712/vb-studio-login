# Build VB-Login WebView2 onefile exe (offline-first)
# Chay: .\build_exe.ps1
$ErrorActionPreference = "Continue"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       VB-Login Build & Package Exe       " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath "src\web\index.html")) {
  Write-Host "Khong tim thay src\web\index.html. Hay chay script tu thu muc goc cua du an." -ForegroundColor Red
  exit 1
}

Write-Host "[1/4] Dang cai dat / nang cap cac thu vien can thiet..." -ForegroundColor Yellow
python -m pip install --upgrade pyinstaller -r requirements.txt | Out-Null

$webData = "src\web;src\web"
$assetData = "assets;assets"

Write-Host "[2/4] Dang bien dich ma nguon voi PyInstaller..." -ForegroundColor Yellow

pyinstaller --noconfirm --clean --windowed --onefile `
  --name "VB-Login" `
  --icon "src\web\assets\app.ico" `
  --paths "." `
  --paths "src" `
  --add-data "$webData" `
  --add-data "$assetData" `
  --hidden-import webview `
  --hidden-import playwright `
  --hidden-import packaging `
  --hidden-import packaging.version `
  --hidden-import cryptography `
  --hidden-import pyzipper `
  --hidden-import src `
  --collect-submodules webview `
  --collect-submodules packaging `
  --collect-submodules src `
  run.py

Write-Host "[3/4] Dang dong goi ban phan phoi (ZIP)..." -ForegroundColor Yellow

$pkgDir = "dist\VB-Login-pkg"
if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
New-Item -ItemType Directory -Force -Path $pkgDir | Out-Null

Copy-Item "dist\VB-Login.exe" "$pkgDir\"
if (Test-Path ".env.example") {
  Copy-Item ".env.example" "$pkgDir\"
}

$readmeLines = @(
  "==================================================",
  "             VB-Login Manager",
  "==================================================",
  "",
  "1. HUONG DAN SU DUNG:",
  "- Chay truc tiep file VB-Login.exe de mo ung dung.",
  "- Du lieu va profile se duoc luu tu dong tai thu muc cua ung dung.",
  "",
  "2. YEU CAU HE THONG:",
  "- Windows 10/11 64-bit.",
  "- Microsoft Edge WebView2 Runtime.",
  "- Neu gap loi thieu Chromium: chay 'playwright install chromium'",
  "=================================================="
)
$readmeLines | Out-File -FilePath "$pkgDir\README.txt" -Encoding utf8

$zipPath = "dist\VB-Login-win64.zip"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " DONG GOI HOAN TAT THANH CONG!" -ForegroundColor Green
Write-Host " File thuc thi: dist\VB-Login.exe" -ForegroundColor Green
Write-Host " File nen phat hanh: dist\VB-Login-win64.zip" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
