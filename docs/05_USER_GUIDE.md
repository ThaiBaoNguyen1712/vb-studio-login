# 5. Cẩm nang Hướng dẫn Vận hành Dành cho Người dùng (User Manual)

Tài liệu này cung cấp hướng dẫn toàn diện cho nhân sự vận hành và quản trị viên khi sử dụng phần mềm **VB-Studio Login** trong công việc hàng ngày.

---

## 5.1. Màn hình Khóa & Quản lý Đăng nhập (Authentication)

### 1. Đăng nhập Ứng dụng
- Khi khởi động ứng dụng, nếu chưa có phiên đăng nhập hợp lệ, hệ thống sẽ hiển thị màn hình yêu cầu xác thực.
- Bấm nút **"Đăng nhập với Google"**.
- Trình duyệt sẽ mở trang đăng nhập bảo mật của Google. Chọn tài khoản email đã được quản trị viên cấp phép (nằm trong danh sách ủy quyền Whitelist).
- Sau khi xác nhận thành công, ứng dụng tự động mở khóa và đưa bạn vào không gian làm việc chính.

### 2. Tự động Nhớ Phiên làm việc
- Sau khi đăng nhập thành công lần đầu, hệ thống sẽ tự động ghi nhớ phiên xác thực trên máy tính của bạn.
- Trong các lần mở ứng dụng tiếp theo, bạn sẽ được đưa thẳng vào bàn làm việc mà không cần lặp lại thao tác đăng nhập.

### 3. Đăng xuất
- Khi cần bàn giao máy tính hoặc thay đổi tài khoản quản trị, bấm vào ảnh đại diện hoặc nút đăng xuất ở thanh công cụ góc trên để giải phóng phiên đăng nhập.

---

## 5.2. Các Chế độ Xem Bàn làm việc (Display Modes)

Ứng dụng cung cấp 3 chế độ xem linh hoạt tùy theo nhu cầu và thói quen làm việc của bạn:

```
[Chuyển đổi Chế độ Xem trên Thanh Công cụ]
   ├── [1. Grid View (Lưới Thẻ Trực Quan)]
   ├── [2. Horizontal Columns (Cột Ngang Tài Khoản)]
   └── [3. Data Table (Bảng Dữ Liệu Quản Trị)]
```

### 1. Chế độ Lưới Thẻ (Grid View)
- Phù hợp nhất cho công việc vận hành hàng ngày.
- Mỗi kênh được hiển thị dưới dạng một thẻ thông tin (Card) độc lập với đầy đủ: biểu tượng nền tảng, tên kênh, tài khoản chủ quản, huy hiệu trạng thái và nút bấm thao tác trực tiếp.

### 2. Chế độ Cột Ngang Tài khoản (Horizontal Account Columns)
- Phù hợp khi bạn muốn theo dõi cấu trúc phân bổ của từng tài khoản gốc:
  - Các tài khoản được xếp theo từng cột nằm ngang song song nhau.
  - Danh sách kênh trong mỗi cột tài khoản cho phép **cuộn dọc** độc lập bằng con lăn chuột.
  - Bạn có thể **cuộn ngang** để xem các tài khoản tiếp theo bằng cách:
    - Lăn chuột thông thường tại vùng trống hoặc thanh cuộn ngang bên dưới.
    - Nhấn giữ phím `Shift` kết hợp lăn con lăn chuột.
    - Kéo thả thanh cuộn ngang ở đáy giao diện.

### 3. Chế độ Bảng Dữ liệu (Data Table View)
- Phù hợp cho quản trị viên muốn kiểm tra nhanh toàn bộ danh sách kênh theo dạng bảng tính dày dặn.
- Hỗ trợ xem nhanh thời điểm đồng bộ gần nhất, người cập nhật, tình trạng kết nối và hỗ trợ mở kênh trực tiếp từ từng dòng trong bảng.

---

## 5.3. Bộ lọc, Tìm kiếm Nhanh & Thống kê

Thanh công cụ phía trên cung cấp các tiện ích tra cứu tức thì:

1. **Ô Tìm kiếm Thông minh:** Nhập tên kênh, tên tài khoản hoặc mã định danh để danh sách tự động lọc kết quả tức thời mà không cần bấm Enter.
2. **Bộ lọc Nền tảng (Platform Filter):** Chọn hiển thị riêng biệt theo từng mạng xã hội: *Tất cả, YouTube, TikTok, Facebook, Instagram* hoặc nền tảng tùy biến.
3. **Bộ lọc Tài khoản (Account Filter):** Chọn lọc danh sách kênh thuộc về một tài khoản Google cụ thể.
4. **Thẻ Thống kê Tổng quan (KPI Stat Banner):**
   - **Tổng số kênh:** Toàn bộ số lượng kênh đang được quản lý trong hệ thống.
   - **Sẵn sàng (Màu xanh lá):** Các kênh đã có cookies hợp lệ, sẵn sàng mở bằng 1 cú nhấp chuột.
   - **Chưa Setup (Màu vàng cam):** Các kênh mới tạo cần đăng nhập lần đầu để bắt cookies.
   - **Đang dùng (Màu xanh dương / đỏ):** Các kênh hiện đang có thành viên trong đội ngũ mở làm việc.
5. **Nút Làm mới (Refresh) & Bộ định thời Tự động:**
   - Bấm nút xoay tròn để cập nhật dữ liệu ngay lập tức.
   - Tùy chỉnh chu kỳ tự động quét trạng thái khóa phiên của đồng đội: `15s`, `30s`, `60s` hoặc `Tắt` trong phần Cài đặt.

---

## 5.4. Thao tác Vận hành Kênh

### 1. Kênh Chưa Setup (Đăng nhập lần đầu)
- **Dấu hiệu nhận biết:** Thẻ kênh có viền vàng cam và nhãn trạng thái `Chưa Setup`.
- **Thao tác:**
  1. Bấm nút **"Setup Đăng nhập"**.
  2. Cửa sổ trình duyệt Chromium sẽ mở trang đăng nhập gốc của nền tảng tương ứng.
  3. Nhập thông tin tài khoản, mật khẩu và hoàn tất bước xác thực 2FA.
  4. Khi trang web đã vào đến giao diện quản trị chính, bạn chỉ cần đóng cửa sổ trình duyệt (bấm dấu `✕`).
  5. Ứng dụng tự động lưu trữ Cookies và chuyển trạng thái kênh sang `Sẵn sàng`.

### 2. Kênh Đã Sẵn Sàng (Khởi chạy hàng ngày)
- **Dấu hiệu nhận biết:** Thẻ kênh có viền xanh lá và nút màu xanh **"Mở Studio"**.
- **Thao tác:**
  1. Bấm nút **"Mở Studio"**.
  2. Trình duyệt tự động mở và đưa bạn thẳng vào trang quản trị Creator Studio mà không cần nhập mật khẩu.
  3. Thẻ kênh của bạn sẽ chuyển sang trạng thái `Đang mở: [Tên của bạn]`.
  4. Sau khi hoàn thành việc tải video hoặc kiểm tra số liệu, bạn chỉ cần đóng cửa sổ trình duyệt. Hệ thống sẽ tự động cập nhật lại cookies mới và giải phóng trạng thái bận cho kênh.

### 3. Xử lý Kênh Đang Bận & Mở khóa Cưỡng chế (Force Unlock)
- **Dấu hiệu nhận biết:** Kênh hiển thị trạng thái `Đang mở: [Tên đồng đội]`.
- **Nguyên tắc an toàn:** Hệ thống sẽ ngăn bạn bấm mở kênh này để tránh làm mất phiên làm việc hoặc xung đột dữ liệu của đồng đội.
- **Mở khóa khẩn cấp:** Trong trường hợp đồng đội đã về hoặc quên đóng trình duyệt trên máy của họ, người quản trị có thể bấm vào biểu tượng chiếc khóa (`🔓`) trên thẻ kênh để giải phóng kênh về trạng thái rảnh.

### 4. Bảng Chi tiết Kênh (Channel Drawer)
- Bấm vào tên kênh hoặc nút chỉnh sửa để mở thanh trượt chi tiết bên phải màn hình:
  - Xem và chỉnh sửa đường dẫn Studio URL, Login URL.
  - Cập nhật ảnh đại diện của kênh.
  - Kiểm tra trạng thái sống của cookies (Test Cookie Health).
  - Tải lại hoặc làm mới phiên làm việc.

### 5. Cụm Nút Nổi Xả Phiên (Floating Action Button - FAB)
- **Vị trí:** Nằm cố định ở góc dưới cùng bên phải màn hình làm việc.
- **Biến đếm thời gian thực:** Hiển thị chính xác số lượng kênh mà bạn đang mở/giam giữ; khi có phiên đang mở, nút sẽ phát sáng đỏ kèm hiệu ứng nhấp nháy để nhắc nhở.
- **Xác nhận đồng bộ hệ thống:** Khi bấm vào nút Xả phiên, hệ thống sẽ bật hộp thoại xác nhận chuẩn (đồng bộ với các tác vụ khác trong ứng dụng) hiển thị danh sách các kênh bạn đang mở. Bấm **"Xả ngay"** để đóng tất cả các tab trình duyệt và giải phóng toàn bộ khóa phiên về trạng thái sẵn sàng.

---

## 5.5. Trung tâm Cấu hình Hệ thống (Settings Hub)

Truy cập mục Cài đặt thông qua biểu tượng bánh răng trên thanh bên:

1. **Cơ sở Dữ liệu & Kết nối Máy chủ (Database & Sync):**
   - Chuyển đổi giữa chế độ lưu trữ tệp cục bộ (`LOCAL`) và máy chủ cơ sở dữ liệu (`POSTGRES`).
   - Nhập thông số kết nối (Host, Port, DB Name, User, Password) và bấm **"Kiểm tra Kết nối"** để thử nghiệm tức thời trước khi lưu.
2. **Cấu hình Trình duyệt (Browser Settings):**
   - Lựa chọn thư mục lưu trữ hồ sơ trình duyệt (`./profiles` hoặc đường dẫn tùy ý trên ổ đĩa).
   - Tùy chỉnh chế độ hiển thị cửa sổ (Toàn màn hình / Kích thước cố định).
3. **Quản lý Đội ngũ (Team Members):**
   - Thêm mới hoặc loại bỏ tên thành viên trong đội ngũ.
   - Chọn định danh người dùng hiện tại để hiển thị khi bạn mở kênh.
4. **Giao diện & Tiện ích (Appearance & Utilities):**
   - Lựa chọn giao diện Tối (Dark mode) hoặc Sáng (Light mode).
   - Bật hoặc tắt âm thanh thông báo phản hồi thao tác.
   - Quản lý Thùng rác (Trash) để khôi phục tài khoản hoặc kênh đã vô tình xóa.
   - Sao lưu dữ liệu hệ thống ra tệp sao lưu hoặc phục hồi từ bản sao lưu trước đó.
   - Đăng ký thêm các nền tảng mạng xã hội mới trong mục **Danh mục Mạng xã hội**.

---

## 5.6. Các Tình huống Thường gặp (FAQ)

- **Hỏi: Kênh đột nhiên chuyển từ "Sẵn sàng" về "Chưa Setup" hoặc "Hết hạn"?**
  - *Đáp:* Nền tảng mạng xã hội có thể tự động hủy phiên sau một thời gian dài không hoạt động hoặc khi có thay đổi mật khẩu từ quản trị viên chính. Bạn chỉ cần bấm lại nút **"Setup Đăng nhập"**, đăng nhập lại một lần là kênh sẽ hoạt động bình thường trở lại.
- **Hỏi: Tôi bấm "Mở Studio" nhưng trình duyệt không hiện lên?**
  - *Đáp:* Kiểm tra xem Playwright đã được cài đặt Chromium chưa bằng lệnh `playwright install chromium` trong môi trường phát triển, hoặc kiểm tra xem có tiến trình trình duyệt cũ nào đang bị treo trong Task Manager không.
- **Hỏi: Tôi có thể sử dụng ứng dụng khi mất kết nối Internet không?**
  - *Đáp:* Có. Ở chế độ `STORAGE_MODE=LOCAL`, toàn bộ giao diện và dữ liệu cục bộ vẫn khởi chạy bình thường. Bạn chỉ cần kết nối Internet khi trình duyệt cần truy cập vào các nền tảng mạng xã hội trực tuyến.
