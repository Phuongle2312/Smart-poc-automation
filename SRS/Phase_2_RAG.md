# 🟨 ĐẶC TẢ GIAI ĐOẠN 2: TÍCH HỢP RAG ĐỐI CHIẾU TRI THỨC DOANH NGHIỆP

Tài liệu này đặc tả kỹ thuật chi tiết cho Giai đoạn 2, chịu trách nhiệm xây dựng hệ thống Retrieval-Augmented Generation (RAG) để đối chiếu thông tin đơn hàng thu thập được ở Giai đoạn 1 với các văn bản quy chế, SLA, và quy định nội bộ của doanh nghiệp.

---

## 1. ⚙️ Kiến trúc & Công nghệ Sử dụng

### 1.1. Công nghệ Vector Database & Embeddings
*   **Vector Database**: `Qdrant` (Chạy local qua Docker container). Qdrant cung cấp khả năng tìm kiếm vector tương đồng tốc độ cao, hỗ trợ bộ lọc metadata (payload filtering) mạnh mẽ.
*   **Embedding Model**: OpenAI `text-embedding-3-small` (kích thước 1536 chiều) hoặc local model như `bge-small-en-v1.5` để tối ưu chi phí và bảo mật.

### 1.2. AI Orchestration & LLM
*   **RAG Framework**: `LangChain` (hoặc `LlamaIndex`) để quản lý kết nối VectorDB, xây dựng chuỗi truy vấn (chains) và quản lý Prompt Templates.
*   **LLM Model**: OpenAI `gpt-4o` hoặc Google `gemini-1.5-pro` (được cấu hình qua API).
*   **Định dạng đầu ra**: Sử dụng tính năng **Structured Output** (JSON Mode hoặc Pydantic Output Parser) để bắt buộc LLM trả về cấu trúc JSON cố định, triệt tiêu hiện tượng hallucination (ảo tưởng thông tin).

---

## 2. 📝 Quy trình Cài đặt & Triển khai Từng Bước

### Bước 1: Triển khai VectorDB Qdrant bằng Docker
Tạo file `docker-compose.yml` (nếu chưa có) tại thư mục gốc:
```yaml
version: '3.8'
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./qdrant_storage:/qdrant/storage
```
Chạy lệnh khởi động:
```bash
docker-compose up -d qdrant
```

### Bước 2: Cấu hình môi trường và thư viện
```bash
pip install qdrant-client langchain-openai langchain-community langchain
```

### Bước 3: Soạn thảo Tài liệu Tri thức (`rag/knowledge.md`)
Tài liệu được viết dưới dạng Markdown chuẩn hóa:
```markdown
# QUY ĐỊNH GIAO NHẬN VÀ MÃ VẠCH NỘI BỘ

## Điều 1: Tiêu chuẩn Mã vạch (Barcode)
- Tất cả hàng hóa nhập kho phải sử dụng mã vạch chuẩn EAN-13 (gồm đúng 13 chữ số).
- Mã vạch không được mờ, rách hoặc có ký tự lạ.

## Điều 2: SLA Thời gian Giao hàng
- Các đơn hàng thuộc nhóm "Ưu tiên cao" phải được giao trong vòng 24 giờ kể từ lúc xác nhận.
- Đơn hàng thông thường phải được giao trong vòng 3 ngày làm việc.

## Điều 3: Tiêu chuẩn Chất lượng Hàng hóa
- Sản phẩm nhập kho không được có vết nứt, biến dạng, hoặc màu sắc lệch chuẩn quá 10% so với mẫu.
- Mỗi sản phẩm phải kèm theo phiếu kiểm tra chất lượng (QC checklist) do nhà cung cấp cấp.

## Điều 4: Quy trình Xử lý Vi phạm
- Vi phạm mức HIGH (SLA > 24h, barcode lỗi): Tự động từ chối đơn và thông báo nhà cung cấp trong vòng 1 giờ.
- Vi phạm mức MEDIUM (SLA 24h–72h, chất lượng chưa rõ): Chuyển sang hàng đợi kiểm tra thủ công.
- Vi phạm mức LOW: Ghi nhận vào báo cáo tuần và không chặn giao hàng.
```

### Bước 4: Viết script nạp tri thức `src/embed_knowledge.py`
*   Đọc file `rag/knowledge.md`.
*   Sử dụng `RecursiveCharacterTextSplitter` chia nhỏ tài liệu thành các đoạn (chunks) 600 ký tự, overlap 50 ký tự để giữ ngữ cảnh liền mạch.
*   Tạo embeddings cho từng chunk và nạp vào collection tên `knowledge_rules` trên Qdrant.
*   **Xử lý ghi đồng thời (Concurrent Write)**: Khi `embed_knowledge.py` đang chạy (upsert), các instance `analyzer.py` song song **không được** đọc collection cùng lúc. Thực thi bằng cách đặt cờ file-lock (`qdrant.lock`) tại thư mục gốc trước khi upsert và xóa cờ sau khi hoàn thành; `analyzer.py` kiểm tra cờ này trước khi query.

### Bước 5: Viết script phân tích `src/analyzer.py`
*   Đọc dữ liệu đơn hàng từ `data/raw_orders.json`.
*   Với mỗi đơn hàng, lấy các trường thông tin chính (ngày giao, mã vạch, nhà cung cấp) để làm truy vấn tìm kiếm ngữ nghĩa (semantic search) trên Qdrant.
*   Thực hiện semantic search trên Qdrant: lấy **top 3 chunks có score cao nhất**, sau đó **lọc bỏ** bất kỳ chunk nào có `score < 0.7`. Nếu không có chunk nào đạt ngưỡng 0.7, ghi log cảnh báo và bỏ qua đơn hàng đó (không gửi LLM để tránh hallucination do thiếu ngữ cảnh).
*   Truyền thông tin đơn hàng và ngữ cảnh quy chế vào Prompt Template gửi tới LLM.
*   Định nghĩa Schema kết quả trả về bằng Pydantic:
    ```python
    from pydantic import BaseModel, Field
    class DefectReport(BaseModel):
        is_violated: bool = Field(description="Đơn hàng có vi phạm quy định nào không")
        violation_type: str = Field(description="Loại vi phạm: Barcode, SLA, Quality, None")
        clause_violated: str = Field(description="Điều khoản quy định bị vi phạm cụ thể")
        severity: str = Field(description="Mức độ nghiêm trọng: HIGH, MEDIUM, LOW, NONE")
        reason: str = Field(description="Lý do chi tiết chứng minh vi phạm")
    ```
*   Ghi kết quả phân tích cuối cùng vào `data/report.json` và `data/report.txt`.
*   Tích hợp gửi báo cáo: Orchestrator hoặc n8n sẽ đọc file báo cáo và tự động gửi email tổng hợp đính kèm file báo cáo đến hòm thư Admin.

---

## 👥 3. Use Cases (Trường hợp Sử dụng)

### Use Case UC-2.1: Cập nhật Tri thức Quy chuẩn Doanh nghiệp
*   **Tác nhân**: Quản trị viên hệ thống (Admin).
*   **Mục tiêu**: Nạp tài liệu quy chuẩn mới hoặc cập nhật các điều khoản vào VectorDB.
*   **Luồng cơ bản**:
    1. Admin sửa đổi nội dung tệp `rag/knowledge.md`.
    2. Admin (hoặc Agent) chạy script `embed_knowledge.py`.
    3. Script xóa collection cũ trên Qdrant và tạo collection mới (hoặc upsert dựa trên hash).
    4. Hệ thống báo cáo số lượng chunks đã được nạp thành công.

### Use Case UC-2.2: Phân tích và Đối chiếu Đơn hàng
*   **Tác nhân**: Script `analyzer.py` (được kích hoạt bởi n8n hoặc Orchestrator).
*   **Mục tiêu**: Phát hiện các đơn hàng vi phạm quy chuẩn dựa trên tri thức đã nạp và gửi email báo cáo.
*   **Luồng cơ bản**:
    1. Script đọc danh sách đơn hàng trong `data/raw_orders.json`.
    2. Với từng đơn hàng, truy vấn VectorDB để tìm các quy định liên quan.
    3. Gửi thông tin đơn hàng + quy định tương ứng sang LLM API.
    4. Nhận về JSON chứa kết quả đánh giá vi phạm.
    5. Xuất báo cáo tổng hợp ra `data/report.json` và `data/report.txt`.
    6. Agent tự động soạn Email báo cáo đính kèm các tệp kết quả và gửi đến `ADMIN_EMAIL`.

---

## 🧪 4. Test Cases (Kịch bản Kiểm thử)

| Mã Test Case | Tên Kịch bản | Điều kiện đầu vào | Các bước thực hiện | Kết quả mong đợi | Loại kiểm thử |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-2.1.1** | Tìm kiếm ngữ nghĩa trên VectorDB | Đã chạy `embed_knowledge.py`. Qdrant đang hoạt động. | 1. Thực hiện query kiểm tra với từ khóa "quy định mã vạch". | Qdrant trả về các chunks từ `knowledge.md` liên quan đến Điều 1 (mã vạch) với score tương đồng cao (>0.75). | Unit |
| **TC-2.2.1** | Phát hiện đơn hàng vi phạm SLA giao hàng | Đơn hàng có ngày xác nhận 01/06/2026, ngày giao 06/06/2026 (quá 3 ngày làm việc). | 1. Chạy `analyzer.py` với đơn hàng này. | Kết quả trả về `is_violated: true`, `violation_type: "SLA"`, chỉ ra đúng Điều quy định về SLA thời gian giao hàng. | Functional |
| **TC-2.2.2** | Bỏ qua đơn hàng hợp lệ | Đơn hàng có đầy đủ thông tin hợp lệ, đúng SLA, mã vạch 13 số. | 1. Chạy `analyzer.py` với đơn hàng này. | Kết quả trả về `is_violated: false`, `violation_type: "None"`, mức độ nghiêm trọng `NONE`. | Functional |
| **TC-2.2.3** | Khống chế Hallucination bằng Structured Output | API LLM phản hồi chậm hoặc trả về văn bản tự do. | 1. Chạy phân tích hàng loạt đơn hàng. | Hệ thống bắt buộc output trả về đúng định dạng JSON khớp với Pydantic schema đã khai báo, không bị lỗi cú pháp JSON. | Resilience |
| **TC-2.2.4** | Xử lý khi VectorDB không phản hồi | Tắt container Qdrant đột ngột. | 1. Khởi chạy `analyzer.py`. | Script bắt được ngoại lệ kết nối Qdrant, ghi log lỗi kết nối, kích hoạt email alert gửi tới Admin và dừng an toàn. | Exception |

---

## ✅ 5. Acceptance Criteria (Tiêu chí Nghiệm thu)

* `embed_knowledge.py` nạp toàn bộ `rag/knowledge.md` vào Qdrant và báo cáo số chunks đã lưu thành công (> 0 chunks).
* `analyzer.py` phát hiện đúng ≥ 90% vi phạm trên tập 100 đơn hàng mẫu (30 SLA lỗi, 20 barcode lỗi, 50 hợp lệ) — xem KPI-1.
* Khi không có chunk nào đạt `score >= 0.7`, hệ thống **không** gửi LLM và ghi log cảnh báo thiếu ngữ cảnh.
* Output của LLM luôn khớp hoàn toàn với `DefectReport` Pydantic schema (không có lỗi parse JSON).
* Khi Qdrant offline, `analyzer.py` bắt exception, ghi log và gửi email alert mà không crash silently.

---

## ⚠️ 6. Constraints & Assumptions (Ràng buộc & Giả định)

* **Constraints**:
  * Qdrant phải chạy trên Docker local tại `localhost:6333` trước khi khởi chạy `embed_knowledge.py` hoặc `analyzer.py`.
  * Collection `knowledge_rules` phải được tạo mới (hoặc upsert) trước khi chạy phân tích lần đầu.
  * Dữ liệu đầu vào `data/raw_orders.json` phải đã qua validation của Giai đoạn 1 trước khi truyền sang `analyzer.py`.
  * Không chạy `embed_knowledge.py` (upsert) đồng thời với `analyzer.py` (read) — sử dụng file-lock `qdrant.lock`.
* **Assumptions**:
  * Tài liệu `rag/knowledge.md` được cập nhật thủ công bởi Admin khi có thay đổi quy chuẩn nội bộ; hệ thống không tự động cập nhật.
  * LLM API (OpenAI/Gemini) có độ trễ phản hồi trung bình < 10 giây cho mỗi đơn hàng; tổng thời gian phân tích 100 đơn < 20 phút.
  * Embedding model (`text-embedding-3-small`) tạo vector 1536 chiều; thay đổi model sẽ yêu cầu nạp lại toàn bộ knowledge.
