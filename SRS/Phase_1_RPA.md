# 🟦 ĐẶC TẢ GIAI ĐOẠN 1: NỀN TẢNG THU THẬP DỮ LIỆU (CORE-RPA)

Tài liệu này đặc tả kỹ thuật chi tiết cho Giai đoạn 1, chịu trách nhiệm tự động hóa việc đăng nhập, vượt qua các rào cản bảo mật, cào dữ liệu đơn hàng và chuẩn hóa dữ liệu đầu ra để cung cấp cho các giai đoạn tiếp theo.

---

## 1. ⚙️ Kiến trúc & Công nghệ Sử dụng

### 1.1. Công nghệ & Thư viện Backend
*   **Ngôn ngữ**: Python 3.10+ (Đảm bảo hiệu năng async tối ưu).
*   **Thư viện RPA**: `Playwright` (Python Async API) điều khiển Chromium Headless. Playwright được chọn nhờ tốc độ xử lý nhanh, hỗ trợ cơ chế tự động đợi (auto-waiting) và dễ dàng chụp ảnh màn hình để phục vụ self-healing.
*   **Quản lý lỗi & Retry**: `Tenacity` hỗ trợ exponential backoff nhằm giảm thiểu lỗi do gián đoạn mạng hoặc phản hồi chậm từ server đối tác.
*   **Kiểm định Schema**: `Pydantic v2` dùng để khai báo cấu trúc đơn hàng và tự động validate dữ liệu thô.
*   **Quản lý cấu hình**: `python-dotenv` quản lý thông tin đăng nhập trong `.env`.

### 1.2. Công nghệ Tích hợp & Lập lịch
*   **n8n (Community Edition)**: Triển khai thông qua Docker Compose.
*   **Phương thức tích hợp**: n8n sử dụng node `Execute Command` để chạy file `crawler.py` theo lịch trình, hoặc dùng `Webhook` để nhận yêu cầu chạy đột xuất.
*   **Giám sát lỗi**: Node `Error Trigger` trong n8n kết nối trực tiếp với node `Send Email (SMTP)` để gửi thư thông báo ngay lập tức nếu crawler thất bại quá số lần retry.

---

## 2. 📝 Quy trình Cài đặt & Triển khai Từng Bước

### Bước 1: Khởi tạo môi trường ảo
```bash
python -m venv venv
./venv/Scripts/activate  # Trên Windows
pip install playwright python-dotenv tenacity pydantic
playwright install chromium
```

### Bước 2: Cấu hình tệp `.env`
Tạo file `.env` ở thư mục gốc (không commit lên Git):
```env
PARTNER_PORTAL_URL=https://portal.partner-website.com/login
PARTNER_USERNAME=your_username_here
PARTNER_PASSWORD=your_password_here
CAPTCHA_API_KEY=2captcha_api_key_here

# Cấu hình Outlook Mail
OUTLOOK_USER=your_outlook_email@outlook.com
OUTLOOK_PASS=your_app_password_here
SMTP_SERVER=smtp.office365.com
SMTP_PORT=587
IMAP_SERVER=outlook.office365.com
IMAP_PORT=993
ADMIN_EMAIL=admin_account@yourcompany.com
```

### Bước 3: Viết script `src/crawler.py`
*   Khởi tạo trình duyệt Playwright ở chế độ `headless=True` (hoặc `headless=False` khi debug).
*   Áp dụng session storage: Đọc tệp tin cookie `memory/cookies.json` nếu tồn tại để bỏ qua bước đăng nhập.
*   Nếu cookie hết hạn hoặc chưa đăng nhập:
    1. Điền credentials từ `.env`.
    2. Kiểm tra nếu có màn hình CAPTCHA: Gọi API 2Captcha để giải mã; nếu thất bại hoặc không cấu hình API, chụp ảnh màn hình, soạn và gửi Email SOS (đính kèm ảnh chụp màn hình trang lỗi) tới địa chỉ `ADMIN_EMAIL` qua SMTP, sau đó dừng luồng.
    3. Lưu lại cookie mới vào `memory/cookies.json`.
*   Điều hướng đến trang danh sách đơn hàng, lấy dữ liệu bảng hiển thị và lưu thành JSON thô tại `data/raw_orders.json`.

### Bước 4: Viết script `src/validator.py`
*   Định nghĩa cấu trúc đơn hàng bằng Pydantic:
    ```python
    from pydantic import BaseModel, Field
    from typing import List, Optional

    class OrderItem(BaseModel):
        order_id: str = Field(..., min_length=5)
        supplier_name: str
        barcode: str = Field(..., pattern=r'^\d{13}$') # Barcode chuẩn EAN-13
        order_date: str
        delivery_deadline: str
        status: str
    ```
*   Đọc `data/raw_orders.json`, chạy validation và xuất dữ liệu sạch. Ghi nhận log lỗi của bản ghi không hợp lệ vào `logs/crawler_YYYYMMDD.log`.

---

## 👥 3. Use Cases (Trường hợp Sử dụng)

### Use Case UC-1.1: Tự động Thu thập Đơn hàng định kỳ
*   **Tác nhân**: Hệ thống n8n (lập lịch).
*   **Mục tiêu**: Lấy dữ liệu đơn hàng mới từ cổng thông tin đối tác mà không cần can thiệp thủ công.
*   **Luồng cơ bản**:
    1. n8n kích hoạt script `crawler.py` mỗi 30 phút.
    2. Script kiểm tra session lưu trữ và điều hướng thành công vào dashboard.
    3. Trích xuất danh sách đơn hàng mới nhất.
    4. Ghi dữ liệu vào tệp `data/raw_orders.json`.
    5. Ghi log trạng thái thành công.

### Use Case UC-1.2: Vượt CAPTCHA hoặc gửi Email Cảnh báo
*   **Tác nhân**: Script `crawler.py`.
*   **Mục tiêu**: Xử lý rào cản CAPTCHA khi đăng nhập.
*   **Luồng cơ bản**:
    1. Script phát hiện phần tử CAPTCHA trên trang login.
    2. Gọi API giải CAPTCHA tự động (2Captcha/Anti-Captcha).
    3. Nếu giải thành công, điền kết quả và gửi form đăng nhập.
    4. Nếu giải thất bại 3 lần hoặc không có API key:
        *   Chụp ảnh màn hình trang lỗi.
        *   Gửi Email SOS (chứa thông tin lỗi và đính kèm hình ảnh) đến `ADMIN_EMAIL`.
        *   Dừng luồng và ghi nhận trạng thái ERROR.

---

## 🧪 4. Test Cases (Kịch bản Kiểm thử)

| Mã Test Case | Tên Kịch bản | Điều kiện đầu vào | Các bước thực hiện | Kết quả mong đợi | Loại kiểm thử |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-1.1.1** | Đăng nhập thành công bằng Cookie lưu sẵn | Đã có file `memory/cookies.json` hợp lệ. | 1. Chạy `crawler.py`. <br>2. Kiểm tra log đăng nhập. | Không xuất hiện thao tác điền username/password. Vào thẳng trang dashboard. | Integration |
| **TC-1.1.2** | Đăng nhập mới khi Session hết hạn | File cookie trống hoặc hết hạn. Credentials trong `.env` đúng. | 1. Xóa `cookies.json`. <br>2. Chạy `crawler.py`. | Điền credentials -> Đăng nhập thành công -> Tạo mới `cookies.json` -> Trích xuất dữ liệu. | Functional |
| **TC-1.1.3** | Xử lý lỗi nhập sai Credentials | Đổi password trong `.env` thành sai. | 1. Chạy `crawler.py`. | Login thất bại -> Không lưu cookie -> Xuất log lỗi Đăng nhập -> Thoát script với exit code và kích hoạt n8n Email Alert. | Negative |
| **TC-1.1.4** | Tự động Retry khi mất mạng | Cáp mạng bị ngắt tạm thời trong khi chạy. | 1. Chạy `crawler.py`. <br>2. Mô phỏng mất kết nối mạng (hoặc block URL). | Thư viện `Tenacity` thực hiện retry với exponential backoff. Log ghi nhận các lần thử lại 1, 2, 3. | Resilience |
| **TC-1.1.5** | Kiểm tra Schema dữ liệu (Pydantic) | File JSON thô có 1 bản ghi bị sai định dạng Barcode (chỉ có 10 số thay vì 13). | 1. Chạy `validator.py` trên file lỗi. | Bản ghi lỗi bị loại bỏ và ghi chi tiết lỗi vào log. Các bản ghi hợp lệ còn lại được ghi nhận bình thường. | Unit |
