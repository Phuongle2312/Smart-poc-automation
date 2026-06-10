# 🟩 ĐẶC TẢ GIAI ĐOẠN 4: KỸ SƯ HÓA AGENT ĐIỀU HÀNH HỆ THỐNG (HERMES + ORCHESTRATOR)

Tài liệu này đặc tả kỹ thuật chi tiết cho Giai đoạn 4, đóng vai trò là "Bộ não" trung tâm điều phối toàn bộ hệ thống PoC tự động hóa. Hermes Agent kết hợp với Outlook Mail Gateway quản lý trạng thái, phát hiện lỗi, tự phục hồi lỗi mã nguồn (Self-healing) và giao tiếp trực tiếp với người điều hành qua Email.

---

## 1. ⚙️ Kiến trúc & Công nghệ Sử dụng

### 1.1. Công nghệ Orchestration & Framework
*   **Agent Engine**: Custom Python Orchestrator kết hợp `LangGraph` (Để quản lý các vòng lặp trạng thái phức tạp và điều phối các Tools: `crawler`, `analyzer`, `vision`).
*   **Giao diện điều khiển (Mail Gateway)**: Kết nối Outlook thông qua Microsoft Graph API (sử dụng thư viện `msal` và `requests`) hoặc sử dụng bộ đôi thư viện tiêu chuẩn `imaplib` (đọc email) và `smtplib` (gửi email).
*   **Mô hình LLM chính**: OpenAI `gpt-4o` (Do có khả năng phân tích hình ảnh và viết code cực kỳ chuẩn xác cho tính năng Self-healing).

### 1.2. Hệ thống Bộ nhớ (Memory System)
Hệ thống sử dụng bộ nhớ dạng tệp tin Markdown được cấu trúc để duy trì trạng thái qua các phiên chạy:
1.  **`memory/SYSTEM_STATE.md`**: Ghi nhận trạng thái hoạt động hiện tại (ví dụ: `IDLE`, `RUNNING_CRAWLER`, `ANALYZING_RAG`, `ERROR`).
2.  **`memory/USER.md`**: Lưu cấu hình người dùng, danh sách các địa chỉ Email được whitelist (danh sách trắng) và mức độ phân quyền.
3.  **`memory/MEMORY.md`**: Lưu lịch sử vận hành, danh sách các sự cố đã xử lý và các selector đã tự cập nhật.

---

## 2. 📝 Quy trình Cài đặt & Triển khai Từng Bước

### Bước 1: Chuẩn bị Tài khoản Outlook & Whitelist Admin
1. Tạo một tài khoản Outlook dành riêng cho Agent (ví dụ: `agent_poc_system@outlook.com`).
2. Nếu sử dụng SMTP/IMAP trực tiếp, kích hoạt **Mật khẩu ứng dụng (App Password)** trong phần thiết lập bảo mật tài khoản Microsoft (nếu bật MFA).
3. Cấu hình địa chỉ email của Admin vào danh sách trắng trong `memory/USER.md`.

### Bước 2: Cấu hình thư viện email
```bash
pip install msal requests langgraph
```

### Bước 3: Viết Gateway `src/mail_gateway.py`
*   Khởi chạy tiến trình nền (Background Process) định kỳ 30 giây thực hiện quét thư mục Inbox thông qua IMAP hoặc MS Graph API.
*   Chỉ xử lý các email đến từ các địa chỉ thuộc danh sách trắng (`whitelist_emails`). Mọi email khác bị bỏ qua hoặc di chuyển vào thư mục Junk.
*   Nhận diện các lệnh điều phối thông qua **Tiêu đề Email (Subject)**:
    *   `[CMD] RUN_FULL`: Kích hoạt chạy tuần tự Giai đoạn 1 (RPA) -> Giai đoạn 2 (RAG).
    *   `[CMD] STATUS`: Đọc file `memory/SYSTEM_STATE.md` và gửi Email phản hồi chi tiết trạng thái kèm thông số hệ thống.
    *   `[CMD] REPORT`: Đọc file `data/report.json`, tạo nội dung tóm tắt và gửi lại email đính kèm các tệp báo cáo.
    *   `[CMD] STOP`: Kích hoạt cờ ngắt khẩn cấp, dừng mọi script đang chạy thông qua ngắt tín hiệu OS.
*   Sau khi thực thi xong lệnh, gửi email phản hồi (Reply) cho người gửi để xác nhận trạng thái hoàn thành.

### Bước 4: Thiết lập Cơ chế Tự phục hồi qua Email (Self-healing CSS Selectors)
Khi script `crawler.py` thất bại do lỗi không tìm thấy phần tử DOM (CSS Selector thay đổi):
1.  Bắt ngoại lệ `TimeoutError` hoặc `ElementNotFoundError` từ Playwright.
2.  Chụp ảnh màn hình trang web hiện tại lưu vào `logs/debug_screenshot.png`.
3.  Lấy nội dung HTML DOM của phần tử cha gần nhất.
4.  Gửi Prompt gồm: *[Ảnh chụp màn hình trang web] + [Đoạn mã HTML DOM] + [Selector bị lỗi]* tới GPT-4o.
5.  GPT-4o phân tích và trả về Selector mới chính xác.
6.  **Human-in-the-loop**: Gửi một Email chứa nội dung Diff đề xuất sửa đổi mã nguồn kèm hình ảnh screenshot lỗi đính kèm tới Admin Email:
    ```diff
    - page.click("#old-login-btn")
    + page.click("button.submit-login")
    ```
    *Tiêu đề Email:* `[HEALING_APPROVAL] Đề xuất sửa đổi Selector nút Login`
7.  Admin phê duyệt bằng cách phản hồi lại email này với nội dung chứa từ khóa:
    *   `APPROVED`: Cho phép cập nhật.
    *   `REJECTED`: Từ chối.
8.  Mail Gateway quét email phản hồi từ Admin:
    *   Nếu nhận được `APPROVED`, Agent tự ghi đè Selector mới vào file cấu hình `src/selectors.json` và chạy lại Crawler.
    *   Nếu nhận được `REJECTED`, dừng hệ thống và chuyển trạng thái sang `ERROR`.

---

## 👥 3. Use Cases (Trường hợp Sử dụng)

### Use Case UC-4.1: Điều khiển Hệ thống từ xa qua Email Outlook
*   **Tác nhân**: Người vận hành (Admin).
*   **Mục tiêu**: Kích hoạt và theo dõi toàn bộ hệ thống PoC qua hòm thư điện tử.
*   **Luồng cơ bản**:
    1. Admin gửi email có tiêu đề `[CMD] RUN_FULL` tới địa chỉ email của Agent.
    2. Mail Gateway quét hộp thư, xác thực email người gửi hợp lệ, chuyển trạng thái hệ thống thành `RUNNING_CRAWLER`.
    3. Agent gửi email phản hồi: *"Bắt đầu chạy crawler..."*.
    4. Sau khi hoàn thành toàn bộ luồng, Agent gửi email báo cáo đính kèm file `report.txt` và `report.json` cho Admin.

### Use Case UC-4.2: Tự phục hồi lỗi Selector (Self-healing)
*   **Tác nhân**: Hermes Agent, Crawler & Admin.
*   **Mục tiêu**: Tự động sửa code khi giao diện trang web đối tác thay đổi và duyệt qua email.
*   **Luồng cơ bản**:
    1. Crawler chạy gặp lỗi do Selector nút login bị đổi từ `#login-btn` sang `.btn-submit`.
    2. Agent tự chụp màn hình, trích xuất DOM, nhờ LLM phân tích tìm ra Selector `.btn-submit`.
    3. Agent gửi email đề xuất thay đổi code cho Admin kèm screenshot đính kèm.
    4. Admin phản hồi email với chữ `APPROVED`.
    5. Agent tự động cập nhật file `src/selectors.json` và chạy lại Crawler thành công.

---

## 🧪 4. Test Cases (Kịch bản Kiểm thử)

| Mã Test Case | Tên Kịch bản | Điều kiện đầu vào | Các bước thực hiện | Kết quả mong đợi | Loại kiểm thử |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-4.1.1** | Xác thực Whitelist Email | Địa chỉ email lạ (không nằm trong whitelist) gửi mail chứa tiêu đề `[CMD] STATUS`. | 1. Gửi email từ một hòm thư Gmail/Outlook không có trong whitelist. | Agent di chuyển email vào Junk hoặc bỏ qua không xử lý. Không phản hồi email. | Security |
| **TC-4.1.2** | Thực hiện chuỗi lệnh `RUN_FULL` | Mail Gateway hoạt động. Các module G1, G2 ổn định. | 1. Admin gửi email tiêu đề `[CMD] RUN_FULL`. | Agent quét được email, chạy tuần tự crawler -> validator -> analyzer và tự động phản hồi lại báo cáo trong < 3 phút. | Functional |
| **TC-4.2.1** | Tự động phát hiện lỗi Selector | Sửa selector nút login trong code thành một chuỗi ngẫu nhiên `#invalid_btn`. | 1. Gửi email `[CMD] RUN_FULL` qua Outlook. | Crawler crash tại bước đăng nhập. Agent bắt lỗi, chụp màn hình, gọi LLM phân tích và gửi email đề xuất `[HEALING_APPROVAL]`. | Integration |
| **TC-4.2.2** | Human-in-the-loop approval qua Email | Tiếp tục từ TC-4.2.1 sau khi email đề xuất được gửi đi. | 1. Phản hồi email đề xuất với nội dung "APPROVED". <br>2. Chờ Mail Gateway quét. | Agent cập nhật file `src/selectors.json`, chạy lại Crawler và hoàn thành đăng nhập thành công. | Functional |
| **TC-4.2.3** | Circuit Breaker (Ngắt mạch vòng lặp) | Giả lập lỗi liên tục (LLM cũng không tìm được selector đúng). | 1. Chạy Crawler bị lỗi. <br>2. Phản hồi "APPROVED" selector mới nhưng vẫn lỗi. | Sau 3 lần tự phục hồi thất bại liên tiếp, Agent dừng hẳn luồng chạy, chuyển trạng thái sang `ERROR`, gửi email cảnh báo khẩn cấp cho Admin và dừng vòng lặp. | Resilience |
