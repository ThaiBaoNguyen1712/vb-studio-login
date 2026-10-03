# VB-Studio Login

Ứng dụng Desktop chuyên nghiệp quản lý tập trung hệ sinh thái tài khoản đa nền tảng (**YouTube, TikTok, Facebook, Instagram** và các nền tảng tùy biến), phục vụ đội ngũ vận hành nội dung số với cơ chế đồng bộ đám mây và tự động hóa điều hướng phiên làm việc.

---

## 🌟 Điểm nổi bật & Tính năng Cốt lõi

- **Màn hình Xác thực Bảo mật:** Tích hợp xác thực tài khoản Google qua Firebase với cơ chế kiểm soát danh sách người dùng được ủy quyền (Whitelist), ghi nhớ phiên làm việc an toàn trên máy trạm.
- **1-Click Studio Launch:** Khởi chạy thẳng vào trang quản trị Creator Studio (YouTube Studio, TikTok Creator Center, Meta Business Suite, Instagram) mà không cần nhập lại mật khẩu hay mã xác thực 2FA.
- **Tự động Bắt & Đồng bộ Cookies 2 chiều:** Tự động trích xuất toàn bộ cookie hợp lệ khi hoàn thành phiên làm việc và đồng bộ tức thì lên cơ sở dữ liệu (Firebase Realtime Database / VPS PostgreSQL / Local JSON).
- **Hồ sơ Trình duyệt Độc lập (Persistent Context):** Mỗi kênh sở hữu thư mục dữ liệu trình duyệt riêng biệt trong `./profiles/{channel_id}`, cô lập hoàn toàn môi trường, chống chồng chéo dữ liệu và duy trì trạng thái đăng nhập bền vững.
- **Kiểm soát Khóa phiên Đa người dùng (`in_use_by`):** Đảm bảo tại một thời điểm chỉ có duy nhất một thành viên mở một kênh cụ thể, loại bỏ hoàn toàn nguy cơ xung đột phiên làm việc hoặc ghi đè cookies giữa các máy trạm.
- **Đa dạng Chế độ Xem (Multi-View Dashboard):**
  - **Grid View:** Hiển thị thẻ kênh dạng lưới linh hoạt, trực quan.
  - **Horizontal Account Columns:** Hiển thị các tài khoản theo dạng cột ngang song song; mỗi cột cho phép cuộn dọc danh sách kênh; hỗ trợ cuộn ngang linh hoạt bằng con lăn chuột, giữ phím Shift + lăn chuột hoặc thao tác kéo vuốt.
  - **Data Table View:** Bảng quản trị dữ liệu chi tiết, hỗ trợ lọc, tìm kiếm nhanh và xử lý hàng loạt.
- **Đồng bộ Đám mây Thời gian thực (Cloud Sync):** Tự động lan truyền trạng thái hoạt động của kênh, thông tin người đang sử dụng và dữ liệu phiên làm việc qua Firebase Realtime Database.
- **Hệ thống Quản trị & Tiện ích Mở rộng:**
  - Quản lý danh sách tài khoản & kênh (Thêm, Sửa, Đổi tên, Tùy biến icon/avatar).
  - Thùng rác (Recycle Bin / Trash) khôi phục tài khoản và kênh đã xóa an toàn.
  - Sao lưu & Phục hồi (Backup & Restore) cấu hình và dữ liệu hệ thống.
  - Giám sát Trạng thái & Kiểm tra Phiên (Health Monitor).
  - Tùy biến Nền tảng Xã hội (Socials Registry) cho phép bổ sung nền tảng mới ngoài 4 nền tảng mặc định.
  - Tùy biến Giao diện Sáng/Tối (Dark/Light mode) và âm thanh phản hồi.

---

## 📁 Cấu trúc Thư mục Dự án

```
vb-login/
├── docs/                         # Toàn bộ tài liệu kỹ thuật & tài liệu hướng dẫn
│   ├── 01_OVERVIEW.md            # Tổng quan hệ thống, nghiệp vụ & ma trận kênh
│   ├── 02_ARCHITECTURE.md        # Kiến trúc hệ thống, phân tầng & nguyên lý SOLID
│   ├── 03_DATABASE_SCHEMA.md     # Cấu trúc CSDL (PostgreSQL, Local JSON & Firebase)
│   ├── 04_FIRST_TIME_SETUP.md    # Hướng dẫn cài đặt & thiết lập lần đầu
│   └── 05_USER_GUIDE.md          # Hướng dẫn vận hành chi tiết cho người dùng
├── src/
│   ├── core/                     # Cấu hình chung, biến môi trường, logger, bảo mật
│   │   ├── config.py             # Nạp cấu hình từ .env & thiết lập đường dẫn
│   │   ├── constants.py          # Enums platform, trạng thái kênh, metadata
│   │   ├── logger.py             # Hệ thống ghi nhật ký xoay vòng
│   │   └── secure_store.py       # Lưu trữ bảo mật thông tin nhạy cảm
│   ├── domain/                   # Các thực thể nghiệp vụ (Account, Channel, Cookie)
│   │   └── models.py             # Định nghĩa Dataclass & Serialization
│   ├── repositories/             # Tầng truy xuất dữ liệu (Data Access Layer)
│   │   ├── base.py               # Interface trừu tượng BaseRepository
│   │   ├── local_repo.py         # Lưu trữ offline trên file Local JSON
│   │   └── postgres_repo.py      # Lưu trữ máy chủ cơ sở dữ liệu PostgreSQL
│   ├── services/                 # Tầng logic nghiệp vụ (Business Logic Layer)
│   │   ├── account_service.py    # Quản lý tài khoản, kênh và điều phối luồng
│   │   ├── browser_service.py    # Điều khiển Playwright Chromium & cấu hình stealth
│   │   ├── session_service.py    # Quản lý khóa phiên (in_use_by) & lưu trữ cookies
│   │   ├── firebase_auth_service.py # Xác thực tài khoản Google qua Firebase
│   │   ├── platform_service.py   # Quản lý danh mục nền tảng mở rộng
│   │   ├── health_service.py     # Kiểm tra tính hợp lệ của phiên đăng nhập
│   │   ├── backup_service.py     # Xuất/nhập bản sao lưu hệ thống
│   │   ├── trash_service.py      # Thùng rác và cơ chế xóa mềm / phục hồi
│   │   ├── notify_service.py     # Hệ thống gửi thông báo và webhook
│   │   └── settings_service.py   # Quản lý file cấu hình runtime (settings.json)
│   ├── web/                      # Giao diện người dùng trên nền tảng WebView2
│   │   ├── index.html            # Khung giao diện chính (SPA)
│   │   ├── api_bridge.py         # Cầu nối hai chiều Python <-> JavaScript
│   │   ├── css/base.css          # Định kiểu giao diện & hiệu ứng chuyển động
│   │   ├── js/                   # Mã nguồn JavaScript mô-đun hóa
│   │   ├── assets/               # Biểu tượng, logo và hình ảnh giao diện
│   │   └── vendor/               # Thư viện offline (Tailwind CSS, Firebase SDK)
│   └── main.py                   # Điểm khởi động ứng dụng (Dependency Injection)
├── profiles/                     # Thư mục lưu Persistent Context của từng kênh
├── data/                         # Thư mục lưu dữ liệu cục bộ (local_db.json, settings.json)
├── public/                       # Trang web xác thực Firebase Hosting tĩnh
├── schema.sql                    # Script DDL khởi tạo cơ sở dữ liệu PostgreSQL
├── firebase.json                 # Cấu hình triển khai Firebase Hosting
├── requirements.txt              # Danh sách thư viện Python phụ thuộc
├── build_exe.ps1                 # Script đóng gói ứng dụng Windows (.exe)
└── README.md                     # Tài liệu tổng quan dự án
```

---

## 🛠️ Hướng dẫn Cài đặt & Khởi chạy

### 1. Yêu cầu Hệ thống
- Hệ điều hành: Windows 10 / Windows 11 (64-bit).
- Python: Phiên bản 3.10 trở lên.
- Microsoft Edge WebView2 Runtime (đã tích hợp sẵn trên Windows 11; người dùng Windows 10 có thể tải từ trang chính thức của Microsoft nếu chưa có).

### 2. Cài đặt Thư viện Phụ thuộc
Mở PowerShell tại thư mục dự án và chạy các lệnh:
```powershell
# Cài đặt danh sách thư viện Python
pip install -r requirements.txt

# Cài đặt trình duyệt Chromium cho Playwright
playwright install chromium
```

### 3. Cấu hình Môi trường
Tạo file `.env` tại thư mục gốc (hoặc sao chép từ cấu hình mẫu) với các thiết lập mong muốn:
```ini
# Chế độ lưu trữ: LOCAL (mặc định) hoặc POSTGRES
STORAGE_MODE=LOCAL

# Tên định danh của thành viên trên máy trạm này
CURRENT_USER_NAME=Member_01

# Cấu hình CSDL PostgreSQL (chỉ bắt buộc khi STORAGE_MODE=POSTGRES)
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=vb_login_db
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_SSLMODE=prefer
```

### 4. Khởi chạy Ứng dụng
Khởi chạy giao diện chính:
```powershell
python src/main.py
```

Khởi chạy ở chế độ gỡ lỗi (bật công cụ DevTools F12 của WebView2):
```powershell
python src/main.py --debug
```

### 5. Đóng gói Ứng dụng Thành File Thực Thi (.exe)
Dự án cung cấp sẵn kịch bản đóng gói ứng dụng thành file `.exe` độc lập để triển khai cho đội ngũ mà không cần cài đặt môi trường Python:
```powershell
.\build_exe.ps1
```
File thực thi sau khi hoàn tất sẽ được đặt trong thư mục `dist/`.

---

## 🔐 Cơ chế Đăng nhập & Vận hành Phiên

1. **Xác thực Tài khoản Quản trị:**
   - Ứng dụng yêu cầu đăng nhập tài khoản Google khi khởi động.
   - Hệ thống đối chiếu tài khoản với danh sách email được cấp phép (Whitelist) trước khi mở khóa giao diện làm việc chính.
   - Trạng thái đăng nhập được lưu trữ an toàn và tự động phục hồi trong các lần mở ứng dụng tiếp theo.

2. **Thiết lập Kênh Lần đầu:**
   - Kênh chưa có phiên đăng nhập sẽ hiển thị trạng thái `Chưa Setup` (màu vàng cam) kèm nút hành động `Setup Đăng nhập`.
   - Khi bấm, trình duyệt mở trang đăng nhập gốc của nền tảng tương ứng.
   - Thành viên đăng nhập và xác thực 2FA.
   - Khi đóng cửa sổ trình duyệt, hệ thống tự động trích xuất toàn bộ cookies hợp lệ, chuyển trạng thái kênh sang `Sẵn sàng` (màu xanh lá) và đồng bộ dữ liệu lên hệ thống lưu trữ.

3. **Khởi chạy Hàng ngày (1-Click Launch):**
   - Kể từ lần thứ hai, thành viên chỉ cần bấm `Mở Studio`.
   - Trình duyệt nạp cookies tự động và điều hướng thẳng vào trang quản trị Creator Studio.
   - Trạng thái kênh lập tức chuyển sang `Đang mở: [Tên thành viên]` để đồng đội trên các máy trạm khác nhận biết và tránh truy cập đồng thời.

---

## 📚 Tài liệu Chi tiết

Mời bạn tham khảo bộ tài liệu kỹ thuật chi tiết trong thư mục `docs/`:
- [01_OVERVIEW.md](file:///d:/VBStudio/vb-login/docs/01_OVERVIEW.md): Nghiệp vụ chi tiết, luồng hoạt động tổng thể và ma trận tài khoản.
- [02_ARCHITECTURE.md](file:///d:/VBStudio/vb-login/docs/02_ARCHITECTURE.md): Phân tầng kiến trúc, nguyên lý SOLID và mô hình giao tiếp Web-Python.
- [03_DATABASE_SCHEMA.md](file:///d:/VBStudio/vb-login/docs/03_DATABASE_SCHEMA.md): Cấu trúc CSDL PostgreSQL, Local JSON, Firebase Realtime Database và cơ chế khóa phiên.
- [04_FIRST_TIME_SETUP.md](file:///d:/VBStudio/vb-login/docs/04_FIRST_TIME_SETUP.md): Hướng dẫn thiết lập môi trường, cấu hình Firebase OAuth và bắt cookies ban đầu.
- [05_USER_GUIDE.md](file:///d:/VBStudio/vb-login/docs/05_USER_GUIDE.md): Cẩm nang hướng dẫn sử dụng giao diện, phím tắt, các chế độ xem và xử lý tình huống.
