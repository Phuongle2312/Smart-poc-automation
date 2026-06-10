# 🟧 ĐẶC TẢ GIAI ĐOẠN 3: TRIỂN KHAI THỊ GIÁC MÁY TÍNH & PHẦN CỨNG (YOLO + ROBOCLAW)

Tài liệu này đặc tả kỹ thuật chi tiết cho Giai đoạn 3, chịu trách nhiệm xử lý hình ảnh sản phẩm thời gian thực thông qua mô hình học sâu YOLOv8 để phát hiện lỗi sản phẩm và điều khiển thiết bị gạt vật lý (RoboClaw Motor) hoặc chạy ở chế độ mô phỏng.

---

## 1. ⚙️ Kiến trúc & Công nghệ Sử dụng

### 1.1. Công nghệ Thị giác Máy tính (Computer Vision)
*   **Mô hình Nhận diện**: `Ultralytics YOLOv8` (Chọn phiên bản Nano `YOLOv8n` hoặc Small `YOLOv8s` để chạy mượt mà trên CPU/GPU cấu hình trung bình).
*   **Thư viện xử lý ảnh**: `OpenCV (opencv-python)` dùng để đọc luồng camera (webcam hoặc camera IP), vẽ bounding boxes và hiển thị thông tin lên màn hình giám sát.
*   **Deep Learning Framework**: `PyTorch` (Hỗ trợ tăng tốc phần cứng bằng CUDA nếu có card đồ họa NVIDIA).

### 1.2. Tích hợp Phần cứng & Chế độ Mô phỏng
*   **Thư viện điều khiển Motor**: `roboclaw_python` (Dùng để gửi lệnh điều khiển vận tốc/vị trí qua cổng USB-Serial đến mạch cầu H RoboClaw).
*   **Chế độ Simulation Mode (Mô phỏng)**: Khi biến môi trường `HW_MODE=false`, hệ thống sẽ không cố gắng mở cổng Serial mà sẽ in các lệnh điều khiển RoboClaw (`REJECT` / `PASS`) ra console log. Chế độ này bắt buộc phải hoạt động độc lập và hoàn hảo cho môi trường PoC không có thiết bị thật.
*   **Chế độ Hardware Mode (Thực tế)**: Khi `HW_MODE=true`, hệ thống kết nối trực tiếp đến cổng COM (Windows) hoặc `/dev/ttyACM*` (Linux) để gửi tín hiệu điều khiển motor gạt vật lý.

---

## 2. 📝 Quy trình Cài đặt & Triển khai Từng Bước

### Bước 1: Thiết lập môi trường và thư viện
```bash
pip install ultralytics opencv-python torch roboclaw_python
```

### Bước 2: Chuẩn bị Dataset & Huấn luyện (Training)
1. Thu thập tối thiểu 200 ảnh cho mỗi lớp:
   - `class 0: normal` (Sản phẩm đạt tiêu chuẩn).
   - `class 1: defect` (Sản phẩm lỗi: nứt, vỡ, sai màu sắc, mất nhãn).
2. Tải ảnh lên **Roboflow** để tiến hành gán nhãn (bounding box).
3. Chia tập dữ liệu: 70% Train, 20% Val, 10% Test. Thực hiện Augmentation (quay ảnh, thay đổi độ sáng để tăng độ đa dạng).
4. Tải dataset định dạng YOLOv8 về máy local.
5. Chạy mã lệnh huấn luyện (Transfer Learning từ `yolov8n.pt`):
   ```python
   from ultralytics import YOLO
   model = YOLO('yolov8n.pt')
   model.train(data='dataset.yaml', epochs=50, imgsz=640, device='0') # device='0' nếu có GPU
   ```
6. Xuất model tốt nhất (`best.pt`) lưu vào thư mục `models/best.pt`.

### Bước 3: Thiết lập Module Điều khiển Motor (`src/actuator.py`)
*   Viết mã nguồn điều khiển motor RoboClaw:
    ```python
    import os
    import time
    from roboclaw import Roboclaw

    HW_MODE = os.getenv("HW_MODE", "false").lower() == "true"
    PORT = os.getenv("ROBOCLAW_PORT", "COM3")
    BAUD = 115200
    ADDRESS = 0x80

    rc = None
    if HW_MODE:
        rc = Roboclaw(PORT, BAUD)
        rc.Open()

    def trigger_reject_arm():
        """Kích hoạt cánh tay gạt sản phẩm lỗi"""
        if not HW_MODE:
            print("[MOCK] RoboClaw Signal: REJECT - Kích hoạt cánh tay gạt!")
            return True

        # Gửi lệnh điều khiển Motor 1 chạy tiến trong 500ms rồi lùi về vị trí cũ
        rc.ForwardM1(ADDRESS, 64) # Chạy tiến nửa công suất
        time.sleep(0.5)
        rc.BackwardM1(ADDRESS, 64) # Chạy lùi nửa công suất
        time.sleep(0.5)
        rc.ForwardM1(ADDRESS, 0) # Dừng motor
        return True
    ```

### Bước 4: Viết script Giám sát `src/vision_inspector.py`
*   Đọc luồng camera bằng OpenCV.
*   Nạp mô hình `models/best.pt`.
*   Chạy vòng lặp phát hiện vật thể liên tục:
    *   Nếu phát hiện vật thể có nhãn `defect` với Confidence Score >= 80% (0.80):
        *   Chụp và lưu hình ảnh lỗi vào `data/defects/defect_YYYYMMDD_HHMMSS.jpg`.
        *   Ghi log vào `logs/defect_YYYYMMDD.log`.
        *   Gọi hàm `trigger_reject_arm()` trong `actuator.py`.

---

## 👥 3. Use Cases (Trường hợp Sử dụng)

### Use Case UC-3.1: Nhận diện & Loại bỏ sản phẩm lỗi (Simulation Mode)
*   **Tác nhân**: Luồng camera (Ảnh/Video mẫu từ G1 hoặc luồng test).
*   **Mục tiêu**: Phát hiện lỗi trên màn hình giả lập và in lệnh loại bỏ sản phẩm ra log mà không cần kết nối phần cứng.
*   **Luồng cơ bản**:
    1. Chạy `vision_inspector.py` với cấu hình `HW_MODE=false`.
    2. Đưa ảnh chứa sản phẩm lỗi vào webcam hoặc chạy từ file video test.
    3. YOLOv8 gán nhãn `defect` với độ tin cậy > 80%.
    4. Hệ thống lưu ảnh vào `data/defects/` và in log: `[MOCK] RoboClaw Signal: REJECT`.

### Use Case UC-3.2: Vận hành dây chuyền thực tế (Hardware Mode)
*   **Tác nhân**: Camera công nghiệp và Motor RoboClaw kết nối thực tế.
*   **Mục tiêu**: Loại bỏ cơ học sản phẩm lỗi trên băng tải.
*   **Luồng cơ bản**:
    1. Thiết lập `HW_MODE=true` in `.env`.
    2. Camera quét liên tục sản phẩm chạy qua băng tải.
    3. Phát hiện lỗi -> Gửi ngay tín hiệu Serial đến RoboClaw.
    4. Cánh tay gạt đẩy sản phẩm lỗi ra khỏi băng tải trong vòng 500ms.
    5. Ghi log trạng thái phần cứng và lưu vết.

---

## 🧪 4. Test Cases (Kịch bản Kiểm thử)

| Mã Test Case | Tên Kịch bản | Điều kiện đầu vào | Các bước thực hiện | Kết quả mong đợi | Loại kiểm thử |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-3.1.1** | Nhận diện sản phẩm lỗi | Mô hình `best.pt` đã nạp. Ảnh kiểm thử có vết nứt rõ ràng. | 1. Truyền ảnh lỗi vào `vision_inspector.py`. | YOLOv8 phát hiện chính xác khung lỗi, nhãn `defect`, confidence score >= 80%. | Unit |
| **TC-3.1.2** | Nhận diện sản phẩm đạt chuẩn | Ảnh sản phẩm nguyên vẹn, không vết nứt. | 1. Truyền ảnh đạt chuẩn vào `vision_inspector.py`. | YOLOv8 gán nhãn `normal` hoặc không phát hiện lỗi. Không ghi log defect. | Unit |
| **TC-3.2.1** | Kiểm thử Simulation Output | `HW_MODE=false`. Đưa ảnh lỗi con. | 1. Chạy inspector ở chế độ simulation. <br>2. Kiểm tra console output. | Console in ra `[MOCK] RoboClaw Signal: REJECT` đúng thời điểm phát hiện. Ảnh lưu thành công vào `data/defects/`. | Functional |
| **TC-3.2.2** | Lỗi cổng Serial (Hardware Mode) | `HW_MODE=true` nhưng không cắm cáp RoboClaw vào máy tính. | 1. Chạy `vision_inspector.py`. | Hệ thống bắt lỗi `SerialException`, ghi log cảnh báo lỗi kết nối phần cứng, gửi email thông báo sự cố cho Admin và tự động chuyển sang Simulation Mode (fallback). | Resilience |
| **TC-3.2.3** | Độ trễ xử lý (FPS) | Luồng camera 1080p chạy trên CPU thông thường. | 1. Khởi chạy luồng live stream. <br>2. Đo tốc độ xử lý FPS. | Tốc độ xử lý đạt tối thiểu 15 FPS (đáp ứng yêu cầu thời gian thực của dây chuyền). | Performance |
