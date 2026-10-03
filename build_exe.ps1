# Build VB-STUDIO WebView2 onefile exe (offline-first)
# Chạy: .\build_exe.ps1
$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "      VB-STUDIO Build & Package Exe       " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

if (-not (Test-Path -LiteralPath "src\web\index.html")) {
  throw "Không tìm thấy src\web\index.html. Hãy chạy script từ thư mục gốc của dự án."
}

Write-Host "[1/4] Đang cài đặt / nâng cấp các thư viện cần thiết..." -ForegroundColor Yellow
pip install --upgrade pyinstaller -r requirements.txt 2>&1 | Out-Null

$webData = "src\web;src\web"
$assetData = "assets;assets"

Write-Host "[2/4] Đang biên dịch mã nguồn với PyInstaller..." -ForegroundColor Yellow

pyinstaller --noconfirm --clean --windowed --onefile `
  --name "VB-STUDIO" `
  --icon "src\web\assets\app.ico" `
  --add-data "$webData" `
  --add-data "$assetData" `
  --hidden-import webview `
  --hidden-import playwright `
  --hidden-import packaging `
  --hidden-import packaging.version `
  --hidden-import cryptography `
  --hidden-import pyzipper `
  --hidden-import psycopg2 `
  --collect-submodules webview `
  --collect-submodules packaging `
  src/main.py

Write-Host "[3/4] Đang đóng gói bản phân phối (ZIP)..." -ForegroundColor Yellow

$pkgDir = "dist\VB-STUDIO-pkg"
if (Test-Path $pkgDir) { Remove-Item -Recurse -Force $pkgDir }
New-Item -ItemType Directory -Force -Path $pkgDir | Out-Null

Copy-Item "dist\VB-STUDIO.exe" "$pkgDir\"
if (Test-Path ".env.example") {
  Copy-Item ".env.example" "$pkgDir\"
}

$readmeContent = @"
==================================================
           VB-STUDIO Multi-Channel Manager
==================================================

1. HƯỚNG DẪN CÀI ĐẶT & SỬ DỤNG:
- Chạy trực tiếp file `VB-STUDIO.exe` để mở ứng dụng.
- Dữ liệu và profile trình duyệt sẽ được lưu tự động tại thư mục của ứng dụng.

2. YÊU CẦU HỆ THỐNG:
- Windows 10/11 64-bit.
- Đã cài Microsoft Edge WebView2 Runtime (thường có sẵn trên Windows 10/11).
- Nếu gặp lỗi thiếu Chromium trình duyệt, chạy lệnh:
  playwright install chromium
==================================================
"@
Set-Content -Path "$pkgDir\README.txt" -Value $readmeContent -Encoding UTF8

$zipPath = "dist\VB-STUDIO-win64.zip"
if (Test-Path $zipPath) { Remove-Item -Force $zipPath }
Compress-Archive -Path "$pkgDir\*" -DestinationPath $zipPath -Force

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " ĐÓNG GÓI HOÀN TẤT THÀNH CÔNG!" -ForegroundColor Green
Write-Host " File thực thi: dist\VB-STUDIO.exe" -ForegroundColor Green
Write-Host " File nén phát hành: dist\VB-STUDIO-win64.zip" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host "Lưu ý: Bạn có thể tải file 'VB-STUDIO.exe' hoặc 'VB-STUDIO-win64.zip' lên GitHub Releases để người dùng tải về." -ForegroundColor Cyan
