@echo off
chcp 65001 >nul
title Tạo Shortcut VB-Login ra Desktop
echo ========================================================
echo   Đang tạo Shortcut VB-Login trên Desktop của bạn...
echo ========================================================

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ws = New-Object -ComObject WScript.Shell; $desktop = [System.Environment]::GetFolderPath('Desktop'); $s = $ws.CreateShortcut([System.IO.Path]::Combine($desktop, 'VB-Login.lnk')); $exe = [System.IO.Path]::Combine($PSScriptRoot, 'VB-Login.exe'); $s.TargetPath = $exe; $s.WorkingDirectory = $PSScriptRoot; $s.Description = 'VB-Login Manager'; $s.IconLocation = $exe + ',0'; $s.Save();"

if %ERRORLEVEL% equ 0 (
    echo.
    echo [OK] Đã tạo thành công Shortcut 'VB-Login' ngoài Desktop!
    echo Bạn có thể mở ứng dụng bất cứ lúc nào từ màn hình Desktop.
) else (
    echo.
    echo [THÔNG BÁO] Không thể tự tạo shortcut. Vui lòng click chuột phải vào file VB-Login.exe chọn Send to -> Desktop.
)

echo.
timeout /t 3
