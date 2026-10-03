# 3. Thiết kế CSDL & Cơ chế Đồng bộ Dữ liệu (Database & Cloud Schema)

Hệ thống **VB-Studio Login** hỗ trợ kiến trúc lưu trữ kép linh hoạt (Dual Storage Architecture), cho phép hoạt động hoàn toàn độc lập ở chế độ Cục bộ (Local JSON) hoặc kết nối đa người dùng thông qua Máy chủ Cơ sở dữ liệu (PostgreSQL) kết hợp dịch vụ Đám mây (Firebase Realtime Database).

---

## 3.1. Thiết kế Cơ sở Dữ liệu Quan hệ (PostgreSQL DDL)

Cơ sở dữ liệu quan hệ được chuẩn hóa theo chuẩn 3NF, phục vụ lưu trữ bền vững, ghi vết lịch sử hoạt động và quản lý khóa truy cập:

```sql
-- Kích hoạt extension hỗ trợ sinh mã UUID (tùy chọn)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Bảng tài khoản quản trị gốc
CREATE TABLE IF NOT EXISTS accounts (
    id VARCHAR(50) PRIMARY KEY,              -- Mã định danh: 'acc_01', 'acc_02'...
    display_name VARCHAR(100) NOT NULL,      -- Tên hiển thị: 'Tài khoản #01'
    email VARCHAR(255) NOT NULL UNIQUE,      -- Email đăng nhập chính
    recovery_email VARCHAR(255),             -- Email khôi phục
    notes TEXT,                              -- Ghi chú nội bộ
    logo TEXT,                               -- Biểu tượng / Avatar tài khoản (URL hoặc Base64)
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 2. Bảng các kênh mạng xã hội phân nhánh
CREATE TABLE IF NOT EXISTS channels (
    id VARCHAR(50) PRIMARY KEY,              -- Mã kênh: 'yt_01', 'tt_01', 'fb_01', 'ig_01'...
    account_id VARCHAR(50) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,           -- 'YOUTUBE_SHORTS', 'TIKTOK', 'FACEBOOK_REELS', 'INSTAGRAM_REELS'
    channel_name VARCHAR(255) NOT NULL,      -- Tên kênh hiển thị
    studio_url TEXT NOT NULL,                -- Đường dẫn trực tiếp vào trang Creator Studio
    login_url TEXT NOT NULL,                 -- Đường dẫn trang đăng nhập gốc
    avatar_url TEXT,                         -- Ảnh đại diện kênh
    status VARCHAR(50) DEFAULT 'NOT_SETUP',  -- Trạng thái: 'NOT_SETUP', 'READY', 'IN_USE', 'EXPIRED'
    pinned BOOLEAN DEFAULT FALSE,            -- Ghim kênh lên đầu danh sách
    pinned_at TIMESTAMPTZ,                   -- Thời điểm ghim
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 3. Bảng lưu trữ Cookies & Quản lý Khóa phiên làm việc
CREATE TABLE IF NOT EXISTS session_cookies (
    channel_id VARCHAR(50) PRIMARY KEY REFERENCES channels(id) ON DELETE CASCADE,
    cookies_data JSONB,                      -- Mảng dữ liệu Cookies chuẩn trích xuất từ trình duyệt
    in_use_by VARCHAR(100) DEFAULT NULL,     -- Tên người dùng đang giữ phiên (NULL = kênh đang rảnh)
    in_use_since TIMESTAMPTZ,                -- Thời điểm bắt đầu mở phiên làm việc
    last_synced_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ,                  -- Thời hạn dự kiến của phiên
    updated_by VARCHAR(100),                 -- Người cập nhật phiên gần nhất
    health JSONB,                            -- Kết quả kiểm tra trạng thái sống của cookies
    last_heartbeat TIMESTAMPTZ               -- Tín hiệu duy trì phiên gần nhất
);

-- 4. Bảng ghi nhận yêu cầu xin cấp quyền mở kênh (Access Requests)
CREATE TABLE IF NOT EXISTS channel_access_requests (
    id VARCHAR(50) PRIMARY KEY,
    channel_id VARCHAR(50) NOT NULL,
    requester VARCHAR(100) NOT NULL,
    message TEXT DEFAULT '',
    status VARCHAR(20) DEFAULT 'pending',    -- 'pending', 'approved', 'rejected'
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_by VARCHAR(100),
    resolved_at TIMESTAMPTZ
);

-- 5. Bảng ghi vết kiểm tra tình trạng phiên (Health Monitor)
CREATE TABLE IF NOT EXISTS health_runs (
    id VARCHAR(50) PRIMARY KEY,
    triggered_by VARCHAR(100) DEFAULT '',
    scope VARCHAR(50) DEFAULT 'ALL',
    total INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running',    -- 'running', 'completed', 'failed'
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    alive INT DEFAULT 0,
    dead INT DEFAULT 0,
    error INT DEFAULT 0,
    skipped INT DEFAULT 0,
    empty INT DEFAULT 0
);

CREATE TABLE IF NOT EXISTS health_results (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) REFERENCES health_runs(id) ON DELETE CASCADE,
    channel_id VARCHAR(50),
    status VARCHAR(20),
    detail TEXT DEFAULT '',
    checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- 6. Bảng Nhật ký Hoạt động (Audit Logs)
CREATE TABLE IF NOT EXISTS session_logs (
    id SERIAL PRIMARY KEY,
    channel_id VARCHAR(50) NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,             -- 'LAUNCH', 'CLOSE_SYNC', 'FORCE_RELEASE'
    ip_address VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Thiết lập chỉ mục (Indexes) nhằm tối ưu tốc độ truy vấn
CREATE INDEX IF NOT EXISTS idx_channels_account_id ON channels(account_id);
CREATE INDEX IF NOT EXISTS idx_channels_platform ON channels(platform);
CREATE INDEX IF NOT EXISTS idx_channels_status ON channels(status);
CREATE INDEX IF NOT EXISTS idx_session_in_use ON session_cookies(in_use_by);
CREATE INDEX IF NOT EXISTS idx_health_results_run ON health_results(run_id);
```

---

## 3.2. Cấu trúc Lưu trữ Tệp Cục bộ (Local JSON Schema)

Khi ứng dụng hoạt động ở chế độ lưu trữ cục bộ (`STORAGE_MODE=LOCAL`), toàn bộ cấu trúc dữ liệu được lưu tại tệp `data/local_db.json` với cấu trúc JSON mô phỏng hoàn chỉnh hệ thống quan hệ:

```json
{
  "accounts": [
    {
      "id": "acc_01",
      "display_name": "Tài khoản #01",
      "email": "channel01@gmail.com",
      "recovery_email": "",
      "notes": "Tài khoản chính",
      "logo": "data:image/png;base64,...",
      "created_at": "2026-10-03T10:00:00.000000",
      "updated_at": "2026-10-03T10:00:00.000000"
    }
  ],
  "channels": [
    {
      "id": "yt_01",
      "account_id": "acc_01",
      "platform": "YOUTUBE_SHORTS",
      "channel_name": "Tech Highlights",
      "studio_url": "https://studio.youtube.com",
      "login_url": "https://accounts.google.com/ServiceLogin?service=youtube",
      "avatar_url": "",
      "status": "READY",
      "pinned": false,
      "pinned_at": null,
      "created_at": "2026-10-03T10:00:00.000000",
      "updated_at": "2026-10-03T10:00:00.000000"
    }
  ],
  "session_cookies": {
    "yt_01": {
      "channel_id": "yt_01",
      "cookies_data": [
        {
          "name": "SID",
          "value": "example_token_value",
          "domain": ".youtube.com",
          "path": "/",
          "expires": 1822550000,
          "httpOnly": true,
          "secure": true,
          "sameSite": "Lax"
        }
      ],
      "in_use_by": null,
      "in_use_since": null,
      "last_synced_at": "2026-10-03T10:05:00.000000",
      "expires_at": null,
      "updated_by": "User_01"
    }
  },
  "session_logs": []
}
```

---

## 3.3. Mô hình Cây Dữ liệu Đám mây (Firebase Realtime Database)

Khi tính năng Cloud Sync được kích hoạt, cây dữ liệu trên Firebase Realtime Database phản chiếu trạng thái tức thì giữa các máy trạm:

```
/
├── accounts/
│   └── {account_id}/
│       ├── id
│       ├── display_name
│       ├── email
│       └── logo
├── channels/
│   └── {channel_id}/
│       ├── id
│       ├── account_id
│       ├── platform
│       ├── channel_name
│       └── status
├── sessions/
│   └── {channel_id}/
│       ├── in_use_by: "Member_01" | null
│       ├── in_use_since: "2026-10-03T11:20:00Z" | null
│       ├── last_synced_at: "2026-10-03T11:20:00Z"
│       ├── updated_by: "Member_01"
│       └── cookies_data: [...]
└── presence/
    └── {user_uid}/
        ├── name: "Bảo Nguyễn"
        ├── current_channel: "yt_01"
        └── last_seen: 1791016500
```

---

## 3.4. Quy tắc Bảo mật Đám mây (Firebase Security Rules)

Để đảm bảo an toàn tuyệt đối, chỉ những người dùng đã xác thực bằng tài khoản Google và có địa chỉ email nằm trong danh sách được ủy quyền mới có quyền đọc hoặc ghi dữ liệu trên đám mây:

```json
{
  "rules": {
    ".read": "auth != null && (
      auth.token.email === 'gamingbao32@gmail.com' ||
      auth.token.email === 'nthaibao1712@gmail.com' ||
      auth.token.email === 'nhatvanwork@gmail.com'
    )",
    ".write": "auth != null && (
      auth.token.email === 'gamingbao32@gmail.com' ||
      auth.token.email === 'nthaibao1712@gmail.com' ||
      auth.token.email === 'nhatvanwork@gmail.com'
    )"
  }
}
```

---

## 3.5. Cơ chế Khóa Phiên Đa Người Dùng (Atomic Session Lock)

Nhằm triệt tiêu nguy cơ tranh chấp tài nguyên (Race Condition) khi hai thành viên mở cùng một kênh tại cùng một tích tắc:

1. **Thao tác Đặt khóa Nguyên tử (Atomic Lock):**
   ```sql
   UPDATE session_cookies
   SET in_use_by = :user_name,
       in_use_since = CURRENT_TIMESTAMP
   WHERE channel_id = :channel_id 
     AND (in_use_by IS NULL OR in_use_by = :user_name);
   ```
   Nếu số dòng bị ảnh hưởng bằng 0, điều đó có nghĩa là một người khác vừa kịp chiếm quyền mở kênh trước. Ứng dụng lập tức từ chối thao tác mở trình duyệt và đưa ra thông báo rõ ràng cho người dùng.

2. **Thao tác Đồng bộ và Giải phóng Khóa khi Hoàn thành:**
   ```sql
   INSERT INTO session_cookies (channel_id, cookies_data, in_use_by, in_use_since, last_synced_at, updated_by)
   VALUES (:channel_id, :cookies_json, NULL, NULL, CURRENT_TIMESTAMP, :user_name)
   ON CONFLICT (channel_id) DO UPDATE SET
       cookies_data = EXCLUDED.cookies_data,
       in_use_by = NULL,
       in_use_since = NULL,
       last_synced_at = CURRENT_TIMESTAMP,
       updated_by = EXCLUDED.updated_by;
   ```

3. **Thao tác Mở khóa Cưỡng chế (Force Unlock):**
   Khi một thành viên đã ngưng làm việc nhưng quên đóng trình duyệt hoặc gặp sự cố tắt máy đột ngột, quản trị viên có thể sử dụng tính năng mở khóa khẩn cấp để đưa `in_use_by` và `in_use_since` về giá trị `NULL`.
