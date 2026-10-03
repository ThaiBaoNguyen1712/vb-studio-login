# ==============================================================================
# VB-STUDIO Release Helper Script
# Cách dùng:
#   .\release.ps1 -Version "v1.0.1" -Message "Bản cập nhật sửa lỗi và thêm tính năng mới"
# ==============================================================================

param (
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [Parameter(Mandatory=$false)]
    [string]$Message = "Release $Version"
)

$ErrorActionPreference = "Stop"

# Đảm bảo format version có 'v' ở đầu (vd: v1.0.1)
if (-not $Version.StartsWith("v")) {
    $Version = "v" + $Version
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  TẠO BẢN PHÁT HÀNH (RELEASE): $Version   " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Cập nhật file src/core/constants.py
$constantsFile = "src\core\constants.py"
if (Test-Path $constantsFile) {
    Write-Host "[1/5] Cập nhật phiên bản trong $constantsFile -> $Version..." -ForegroundColor Yellow
    $content = Get-Content $constantsFile -Raw -Encoding UTF8
    $newContent = $content -replace 'APP_VERSION = ".*?"', "APP_VERSION = `"$Version`""
    Set-Content -Path $constantsFile -Value $newContent -Encoding UTF8
}

# 2. Cập nhật file index.html hiển thị
$indexFile = "src\web\index.html"
if (Test-Path $indexFile) {
    Write-Host "[2/5] Cập nhật phiên bản hiển thị trong $indexFile..." -ForegroundColor Yellow
    $content = Get-Content $indexFile -Raw -Encoding UTF8
    $newContent = $content -replace '<span id="app-current-version-label" class="font-bold text-blue-500">.*?</span>', "<span id=`"app-current-version-label`" class=`"font-bold text-blue-500`">$Version</span>"
    Set-Content -Path $indexFile -Value $newContent -Encoding UTF8
}

# 3. Kiểm tra git
Write-Host "[3/5] Kiểm tra Git repository..." -ForegroundColor Yellow
$isGit = Test-Path ".git"
if (-not $isGit) {
    Write-Host "Thư mục chưa khởi tạo git. Đang chạy 'git init'..." -ForegroundColor Cyan
    git init
}

# 4. Commit thay đổi
Write-Host "[4/5] Tạo commit và gắn tag $Version..." -ForegroundColor Yellow
git add .
git commit -m "chore(release): bump version to $Version" --allow-empty
git tag -a "$Version" -m "$Message" -f

# 5. Thông báo hướng dẫn Push
Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " ĐÃ TẠO TAG PHÁT HÀNH $Version THÀNH CÔNG!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Lệnh để đẩy lên GitHub và kích hoạt tự động đóng gói (GitHub Actions):" -ForegroundColor Cyan
Write-Host "   git push origin main" -ForegroundColor White
Write-Host "   git push origin $Version" -ForegroundColor White
Write-Host ""
Write-Host "Hoặc nếu bạn muốn đóng gói trên máy nội bộ ngay bây giờ:" -ForegroundColor Cyan
Write-Host "   .\build_exe.ps1" -ForegroundColor White
