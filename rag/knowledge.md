# QUY ĐỊNH VÀ TIÊU CHUẨN VẬN HÀNH NỘI BỘ (SLA & Barcode Regulations)

Tài liệu này định nghĩa các quy chuẩn hoạt động bắt buộc đối với đơn đặt hàng và nhà cung ứng của công ty. Mọi đơn hàng không tuân thủ các quy định dưới đây đều bị coi là vi phạm SLA.

---

## 1. Quy định về Thời gian Giao hàng (SLA Delivery Timeline)
- **Đơn hàng từ Nhà cung ứng Nước ngoài (Foreign Vendors)**: Thời gian giao hàng thực tế phải nằm trong khoảng tối đa **5 ngày** kể từ ngày đặt hàng (Order Date). Mọi sự chậm trễ quá 5 ngày sẽ bị coi là vi phạm nghiêm trọng (High severity).
- **Đơn hàng từ Nhà cung ứng Trong nước (Domestic Vendors)**: Thời gian giao hàng thực tế phải nằm trong khoảng tối đa **2 ngày** kể từ ngày đặt hàng.
- *Lưu ý*: Ngày giao hàng thực tế được xác định khi hệ thống camera hoặc kho xác nhận nhập hàng (trong PoC này, chúng ta giả định ngày kiểm thử hiện tại là ngày chạy phân tích đơn hàng).

---

## 2. Quy định về Mã vạch Sản phẩm (Product Barcode Regulations)
- Tất cả sản phẩm thuộc đơn hàng của nhà cung ứng **Global Tech Solutions** bắt buộc phải có mã vạch hợp lệ theo đầu số chuẩn quốc tế:
  - Phải bắt đầu bằng đầu số chuẩn **978** (sách quốc tế) hoặc **893** (Việt Nam).
  - Bất kỳ sản phẩm nào có mã vạch không đúng đầu số trên hoặc thiếu mã vạch sẽ bị cảnh báo và từ chối nhập kho (Medium severity).
- Các nhà cung ứng khác phải tuân thủ chuẩn mã vạch chung (chỉ chứa ký tự chữ và số, không chứa ký tự đặc biệt).

---

## 3. Hạn mức Tài chính Đơn hàng (Order Financial Limits)
- Đối với nhà cung ứng **Vina Supply Corp**:
  - Hạn mức tổng số tiền tối đa cho mỗi đơn đặt hàng lẻ là **10,000.00 USD**.
  - Bất kỳ đơn hàng nào vượt quá hạn mức 10,000.00 USD sẽ bị hệ thống tự động gắn cờ vi phạm tài chính để kiểm duyệt thủ công (High severity).
- Đối với nhà cung ứng **Sino Logistics**:
  - Tổng số tiền đơn hàng bắt buộc phải là số dương lớn hơn 0.

---

## 4. Quy trình Xử lý Vi phạm (Violation Handling Process)
- **Vi phạm mức HIGH** (SLA vượt quá giới hạn, barcode sai đầu số): Hệ thống tự động từ chối đơn và gửi thông báo đến nhà cung cấp trong vòng **1 giờ** kể từ khi phát hiện vi phạm.
- **Vi phạm mức MEDIUM** (SLA trong khoảng 24h–72h, chất lượng hàng hóa chưa rõ): Đơn hàng được chuyển sang hàng đợi kiểm tra thủ công; hệ thống gửi email cảnh báo đến Admin.
- **Vi phạm mức LOW**: Ghi nhận vào báo cáo tổng hợp định kỳ và không chặn quá trình giao hàng.
