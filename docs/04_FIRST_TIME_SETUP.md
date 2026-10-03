# 4. Hướng dẫn Cài đặt & Khởi tạo Lần đầu (First-Time Setup Guide)

Tài liệu này cung cấp hướng dẫn từng bước chi tiết để cài đặt, thiết lập môi trường và cấu hình hệ thống **VB-Studio Login** trên máy trạm mới.

---

## 4.1. Yêu cầu Hệ thống & Môi trường

1. **Hệ điều hành:**
   - Windows 10 (Build 1809 trở lên) hoặc Windows 11 (64-bit).
2. **Microsoft Edge WebView2 Runtime:**
   - Đã được tích hợp sẵn trên Windows 11.
   - Nếu sử dụng Windows 10 và chưa có, tải bản cài đặt Evergreen Bootstrapper từ trang chính thức của Microsoft.
3. **Môi trường Python (dành cho Nhà phát triển):**
   - Python 3.10 hoặc phiên bản mới hơn (chọn tích hợp `Add python.exe to PATH` trong quá trình cài đặt).
   - Trình quản lý gói `pip` bản mới nhất.

---

## 4.2. Các Bước Cài đặt Môi trường Phát triển

### Bước 1: Sao chép Mã nguồn & Khởi tạo Môi trường Ảo
Mở PowerShell tại thư mục làm việc và chạy các lệnh:
```powershell
# Chuyển vào thư mục dự án
cd d:\VBStudio\vb-login

# Khởi tạo môi trường ảo Python (khuyên dùng)
python -m venv venv

# Kích hoạt môi trường ảo
.\venv\Scripts\Activate.ps1
```

### Bước 2: Cài đặt Danh mục Thư viện Phụ thuộc
```powershell
# Nâng cấp pip lên bản mới nhất
python -m pip install --upgrade pip

# Cài đặt các gói thư viện từ requirements.txt
pip install -r requirements.txt

# Cài đặt trình duyệt Chromium cho thư viện tự động hóa Playwright
playwright install chromium
```

---

## 4.3. Cấu hình Biến Môi trường & Thiết lập Hệ thống

### 1. Tệp cấu hình `.env`
Tạo tệp `.env` tại thư mục gốc của dự án:
```ini
# Chế độ lưu trữ: LOCAL (mặc định) hoặc POSTGRES
STORAGE_MODE=LOCAL

# Tên định danh của nhân sự trên máy tính này (hiển thị khi mở kênh)
CURRENT_USER_NAME=Member_01

# Cấu hình kết nối cơ sở dữ liệu PostgreSQL (chỉ áp dụng khi STORAGE_MODE=POSTGRES)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=vb_login_db
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_SSLMODE=prefer
```

### 2. Cấu hình Dịch vụ Firebase (settings.json)
Thông tin cấu hình Firebase được nạp từ tệp `data/settings.json`:
```json
{
  "general": {
    "app_title": "VB-Studio Login",
    "theme_mode": "Dark",
    "auto_refresh_seconds": 15
  },
  "firebase": {
    "url": "https://vb-studio-login-sync-default-rtdb.asia-southeast1.firebasedatabase.app/",
    "api_key": "AIzaSyCRJzx8Z8--dzQBgxbTsbYaygyifxj4waY",
    "auth_domain": "vb-studio-login-sync.firebaseapp.com",
    "project_id": "vb-studio-login-sync",
    "app_id": "1:81737086298:web:f042b83f2a9b16d91aef63",
    "enabled": true
  }
}
```

---

## 4.4. Cấu hình Ủy quyền Tên miền trên Firebase Console

Để tính năng xác thực tài khoản Google hoạt động ổn định trên các máy trạm, quản trị viên dự án Firebase cần cấu hình danh sách tên miền được phép (Authorized Domains):

1. Truy cập **Firebase Console** -> Chọn dự án `vb-studio-login-sync`.
2. Điều hướng đến mục **Authentication** -> Thẻ **Settings** -> Mục **Authorized domains**.
3. Đảm bảo các tên miền sau đã được thêm vào danh sách:
   - `localhost` (Dành cho tiến trình nhận phản hồi cục bộ của ứng dụng máy trạm).
   - `vb-studio-login-sync.firebaseapp.com` (Tên miền mặc định của dự án).
   - `vb-studio-login-sync.web.app` (Tên miền phụ của dự án).

> **Lưu ý:** Việc thêm `localhost` vào danh sách tên miền được ủy quyền sẽ cho phép tất cả các cổng cục bộ (bao gồm dải cổng từ 52140 đến 52160) hoàn tất quy trình xác thực một cách thông suốt.

---

## 4.5. Khởi chạy Ứng dụng & Xác thực Lần đầu

### Bước 1: Khởi động Ứng dụng
Chạy lệnh khởi động:
```powershell
python src/main.py
```
*(Nếu muốn mở công cụ kiểm tra gỡ lỗi giao diện F12, thêm cờ `--debug`: `python src/main.py --debug`)*.

### Bước 2: Vượt qua Màn hình Khóa Xác thực (Auth Gate)
1. Khi khởi động lần đầu, ứng dụng hiển thị màn hình yêu cầu xác thực tài khoản.
2. Bấm nút **"Đăng nhập với Google"**.
3. Trình duyệt mặc định của hệ điều hành sẽ tự động mở trang đăng nhập bảo mật.
4. Chọn tài khoản Google của bạn (bắt buộc phải là địa chỉ email đã được cấp quyền trong Whitelist).
5. Sau khi xác nhận thành công, màn hình trình duyệt sẽ hiển thị thông báo hoàn tất và bạn có thể đóng tab trình duyệt lại.
6. Ứng dụng Desktop tự động nhận mã phiên, kiểm tra quyền truy cập và mở khóa đưa bạn vào bàn làm việc chính.
7. Phiên đăng nhập này sẽ được ghi nhớ tự động cho các lần khởi động ứng dụng tiếp theo.

---

## 4.6. Thiết lập Phiên Đăng nhập Ban đầu cho Kênh (Initial Setup)

Sau khi vào được bàn làm việc, các kênh mới khởi tạo sẽ ở trạng thái `Chưa Setup` (hiển thị huy hiệu màu vàng cam). Để thiết lập phiên làm việc ban đầu:

```
[Kênh ở trạng thái Chưa Setup]
             │
             ▼
[Bấm nút "Setup Đăng nhập"]
             │
             ▼
[Chromium mở trang đăng nhập gốc của nền tảng (YouTube / TikTok / Meta)]
             │
             ▼
[Thành viên nhập tài khoản, mật khẩu & hoàn tất mã xác thực 2FA]
             │
             ▼
[Trang web chuyển hướng vào giao diện chính của tài khoản thành công]
             │
             ▼
[Thành viên đóng cửa sổ trình duyệt (bấm dấu X)]
             │
             ▼
[Hệ thống tự động bắt Cookies, lưu trữ & đổi trạng thái sang "Sẵn sàng" (Xanh lá)]
```

Từ thời điểm này trở đi, kênh đã sẵn sàng để sử dụng tính năng **1-Click Launch** mà không bao giờ cần nhập lại mật khẩu hay mã 2FA nữa.
