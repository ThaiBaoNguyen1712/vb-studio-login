@echo off
chcp 65001 >nul
title Tạo Shortcut VBLogin ra Desktop
echo ========================================================
echo   Đang tạo Shortcut VBLogin trên Desktop của bạn...
echo ========================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [System.Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut([System.IO.Path]::Combine($desktop, 'VBLogin.lnk')); $exe = [System.IO.Path]::Combine($PSScriptRoot, 'VBLogin.exe'); $s.TargetPath = $exe; $s.WorkingDirectory = $PSScriptRoot; $s.Description = 'VBLogin Manager'; $s.IconLocation = $exe + ',0'; $s.Save();"

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] Đã tạo thành công Shortcut 'VBLogin' ngoài Desktop!
    echo Bạn có thể mở ứng dụng bất cứ lúc nào từ màn hình Desktop.
) else (
    echo.
    echo [THÔNG BÁO] Không thể tự tạo shortcut. Vui lòng click chuột phải vào file VBLogin.exe chọn Send to -> Desktop.
)

echo.
timeout /t 3
