# 🛡️ ĐẶC TẢ TÍCH HỢP HỆ THỐNG, BẢO MẬT & ĐO LƯỜNG KPIS

Tài liệu này đặc tả cách thức tích hợp toàn bộ các giai đoạn từ G1 đến G4 thành một hệ thống đồng nhất, các giao thức bảo mật thông tin và phương pháp đo lường chi tiết cho 6 chỉ số KPIs thành công của dự án PoC.

---

## 1. 🔗 Quy trình Tích hợp Toàn Hệ thống (E2E Integration)

Hệ thống PoC hoạt động thông qua một chuỗi xử lý liên kết chặt chẽ (Pipeline):

```
[Trigger Email] ──► [G1: Playwright Crawler] ──► [data/raw_orders.json]
                                                        │
                                                        ▼
[data/report.json] ◄── [G2: RAG Analyzer] ◄── [VectorDB Qdrant]
        │
        ▼
[G4: Outlook Mail Gateway] ──► [Gửi email báo cáo cho Admin]
        │
   (Self-healing)
        │
        ▼
[Sửa đổi src/selectors.json] ──► [Chạy lại G1]
```

*   **Lập lịch**: Sử dụng **n8n Workflow** làm bộ điều phối lịch trình (Cron Job: mỗi 30 phút hoặc 24 giờ). n8n sẽ thực thi file `src/agent_orchestrator.py`.
*   **Xử lý bất đồng bộ**: Các tác vụ xử lý hình ảnh sản phẩm lỗi (G3) chạy độc lập dạng luồng (Background Thread/Process) song song với luồng cào dữ liệu đơn hàng và đối chiếu SLA (G1 + G2).

---

## 2. 🔒 Các Giao thức Bảo mật & Tuân thủ (Security & Compliance)

Để bảo vệ thông tin nhạy cảm của doanh nghiệp và đối tác, hệ thống tuân thủ nghiêm ngặt các quy tắc sau:

### 2.1. Quản lý Môi trường & Credentials
*   Tuyệt đối **không commit** các thông tin nhạy cảm như API Keys, Mật khẩu email, Email Whitelist lên Git.
*   Tất cả cấu hình được lưu trong file `.env` tại thư mục gốc. Tệp tin `.gitignore` phải chứa dòng `.env` ngay từ khi khởi tạo dự án.
*   Mẫu file cấu hình công khai được lưu trong `.env.example` để hướng dẫn cài đặt.

### 2.2. Kiểm soát Quyền truy cập Outlook Mail Gateway
*   Trong bộ nhớ lưu trữ `memory/USER.md`, định nghĩa danh sách trắng (`Whitelist`) các địa chỉ Email của quản trị viên được phép gửi lệnh đến Agent:
    ```json
    {
      "whitelist_emails": [
        "admin_account@yourcompany.com",
        "supervisor_account@yourcompany.com"
      ]
    }
    ```
*   Mọi email gửi đến từ các hòm thư nằm ngoài whitelist sẽ bị Mail Gateway bỏ qua và ghi nhận log cảnh báo xâm nhập dạng `WARNING` vào `logs/system_YYYYMMDD.log`.

### 2.3. Quản lý Vòng đời Dữ liệu Nhạy cảm (Data Retention)
*   Để tuân thủ các quy định về bảo vệ dữ liệu (GDPR/quy định bảo mật nội bộ), các tệp tin chứa thông tin thô như `data/raw_orders.json` và ảnh chụp lỗi `data/defects/*.jpg` sẽ tự động bị xóa khỏi ổ đĩa cứng sau **7 ngày**.
*   Một tiến trình Cron siêu nhẹ chạy ngầm (hoặc tích hợp trong Orchestrator) chịu trách nhiệm dọn dẹp các tệp tin cũ quá hạn này.

---

## 📈 3. Định nghĩa và Phương pháp Đo lường 6 KPIs

Dưới đây là đặc tả chi tiết cách đo lường các chỉ số thành công (KPIs) của hệ thống PoC:

### KPI 1: RAG Accuracy — Tỷ lệ phát hiện đúng vi phạm quy chuẩn
*   **Mục tiêu**: `≥ 90%`.
*   **Ý nghĩa**: Đảm bảo AI RAG tìm kiếm và đối chiếu đúng quy định mà không phát hiện sai hoặc bỏ sót lỗi đơn hàng.
*   **Phương pháp đo lường**:
    1. Soạn thảo một tập kiểm thử gồm 100 đơn hàng mẫu (trong đó có 30 đơn hàng chứa lỗi cố ý về SLA, 20 đơn hàng chứa lỗi Barcode, và 50 đơn hàng hoàn toàn hợp lệ).
    2. Chạy `analyzer.py` trên tập mẫu này.
    3. Đếm số lượng kết quả AI đánh giá trùng khớp hoàn toàn với nhãn thủ công (Ground Truth).
    $$\text{RAG Accuracy} = \frac{\text{Số đơn hàng AI đánh giá đúng}}{\text{100 đơn hàng mẫu}} \times 100\%$$

### KPI 2: Vision Precision — mAP@0.5 trên tập test sản phẩm lỗi
*   **Mục tiêu**: `≥ 80%`.
*   **Ý nghĩa**: Độ chính xác của mô hình YOLOv8 trong việc khoanh vùng vết nứt/lỗi sản phẩm trên camera.
*   **Phương pháp đo lường**:
    1. Trích xuất 10% tập dữ liệu ảnh lỗi làm tập Test độc lập (không tham gia vào quá trình Train).
    2. Chạy kiểm thử đánh giá mô hình bằng công cụ Validation của Ultralytics YOLOv8:
       ```bash
       yolo task=detect mode=val model=models/best.pt data=dataset.yaml split=test
       ```
    3. Trích xuất chỉ số `mAP50` từ kết quả xuất ra.

### KPI 3: End-to-end Performance — Thời gian hoàn thành Pipeline
*   **Mục tiêu**: `< 3 phút`.
*   **Ý nghĩa**: Tốc độ xử lý dữ liệu từ khi nhận email lệnh cho đến khi gửi email phản hồi kết quả đến Admin.
*   **Phương pháp đo lường**:
    1. Ghi nhận timestamp bắt đầu ($T_{start}$) khi Mail Gateway quét được email lệnh hợp lệ và bắt đầu thực thi.
    2. Ghi nhận timestamp kết thúc ($T_{end}$) khi Mail Gateway gửi thành công email báo cáo phản hồi cho Admin.
    3. Công thức tính: $\Delta T = T_{end} - T_{start}$. Yêu cầu $\Delta T < 180 \text{ giây}$.

### KPI 4: Automation Rate — Vận hành không cần can thiệp thủ công
*   **Mục tiêu**: `100%` (ở môi trường Staging).
*   **Ý nghĩa**: Hệ thống chạy tự trị liên tục, không cần con người bấm nút chạy hay sửa code thủ công.
*   **Phương pháp đo lường**:
    1. Thiết lập hệ thống chạy tự động định kỳ trong vòng 24 giờ.
    2. Nếu có lỗi xảy ra yêu cầu Admin phải vào sửa code trực tiếp bằng tay thì tỷ lệ này bị giảm. (Lưu ý: Lỗi CSS selector được Agent tự phát hiện và Admin chỉ cần trả lời email Approve để xác duyệt vẫn được tính là tự động hóa).

### KPI 5: System Uptime — Thời gian hoạt động liên tục không crash
*   **Mục tiêu**: `≥ 24 giờ`.
*   **Ý nghĩa**: Hệ thống không bị treo, rò rỉ bộ nhớ (memory leak) hoặc crash ngầm do lỗi thư viện bất đồng bộ.
*   **Phương pháp đo lường**:
    1. Triển khai script giám sát heartbeat (ping) cứ 5 phút một lần ghi log trạng thái.
    2. Đảm bảo tiến trình chính không bị restart ngoài ý muốn trong suốt 24 giờ kiểm thử.

### KPI 6: Self-healing Success Rate — Tỷ lệ tự sửa đổi Selector thành công
*   **Mục tiêu**: `≥ 70%`.
*   **Ý nghĩa**: Khả năng của Agent dùng GPT-4o phân tích ảnh màn hình và DOM để sửa code thành công và được Admin duyệt qua email.
*   **Phương pháp đo lường**:
    1. Giả lập 10 kịch bản lỗi selector khác nhau trên trang đăng nhập mẫu.
    2. Kích hoạt cơ chế Self-healing của Agent.
    3. Admin gửi email duyệt `APPROVED` để Agent áp dụng sửa đổi.
    4. Đếm số lần Selector mới do Agent đề xuất giúp Crawler vượt qua bước lỗi thành công.
    $$\text{Self-healing Success Rate} = \frac{\text{Số lần sửa đổi chạy thành công}}{\text{10 lần chạy giả lập lỗi}} \times 100\%$$
