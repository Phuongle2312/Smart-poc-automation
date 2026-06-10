# 🚀 KẾ HOẠCH TRIỂN KHAI HỆ THỐNG TỰ ĐỘNG HÓA AI (PoC)

> **Phiên bản:** 1.2 — Chuyển đổi từ Telegram Bot sang Mail Outlook  
> **Trạng thái:** Đang lập kế hoạch  
> **Thời gian tổng thể:** 7+ tuần  

---

## 📋 Tổng quan Kiến trúc

```
[Cổng thông tin / Camera]
        │
        ▼
[Giai đoạn 1: RPA Thu thập Dữ liệu]  ──── Playwright + n8n
        │
        ▼
[Giai đoạn 2: RAG Phân tích Tri thức] ──── LLM + VectorDB (Qdrant/Chroma)
        │
        ▼
[Giai đoạn 3: Giám sát Vật lý]        ──── YOLOv8 + RoboClaw (nếu có HW)
        │
        ▼
[Giai đoạn 4: Agentic Điều phối]      ──── Hermes Agent + Outlook Mail
```

---

## 📊 Bảng Tóm tắt Các Giai đoạn

| Giai đoạn | Tiêu đề | Thời gian | Mục tiêu cốt lõi | Công nghệ áp dụng | Phụ thuộc |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | Nền tảng Luồng Dữ liệu | Tuần 1–2 | Cào dữ liệu tự động, kết nối dòng chảy dữ liệu | Python, Playwright, n8n | Không |
| **2** | Bộ não Tri thức | Tuần 3–4 | Đối chiếu dữ liệu với quy chuẩn nội bộ bằng AI RAG | LLM (OpenAI/Gemini), VectorDB, LangChain | Giai đoạn 1 |
| **3** | Giám sát Vật lý | Tuần 5–6 | Nhận diện sản phẩm lỗi qua camera, điều khiển thiết bị | YOLOv8, OpenCV, RoboClaw (tùy chọn) | Giai đoạn 1 |
| **4** | Agentic Automation | Tuần 7+ | Agent tự trị điều phối toàn bộ luồng vận hành | Hermes Agent, Outlook Mail API/SMTP/IMAP, LangGraph/CrewAI | Giai đoạn 1, 2, 3 |

---

## 🛠️ Chi tiết Các Bước Thực thi & Kịch bản Kiểm thử

---

### 🟦 GIAI ĐOẠN 1: Thiết lập Nền tảng Thu thập Dữ liệu (Core-RPA)

**Mục tiêu:** Tự động hóa thao tác đăng nhập hệ thống, xử lý các rào cản bảo mật và lấy thông tin nhà cung ứng/đơn hàng một cách ổn định.

#### Tác vụ thực hiện

1. **Khởi tạo môi trường**
   - Tạo virtualenv Python 3.10+, cài đặt dependencies: `playwright`, `asyncio`, `python-dotenv`, `tenacity`.
   - Cấu hình tệp `.env` chứa credentials (KHÔNG commit lên git).

2. **Viết mã nguồn `crawler.py`**
   - Điều khiển trình duyệt Chromium headless qua Playwright.
   - Xử lý luồng đăng nhập: nhập username/password, xử lý OTP nếu có.
   - **Xử lý CAPTCHA:** Tích hợp 2Captcha hoặc Anti-Captcha API làm fallback; nếu gặp CAPTCHA thị giác, gửi email alert qua Outlook thay vì crash.
   - **Retry logic:** Dùng `tenacity` với exponential backoff (tối đa 3 lần, delay 5s) cho các request thất bại.
   - **Session management:** Lưu trạng thái cookie/localStorage vào file để tái sử dụng, giảm tần suất đăng nhập.
   - Xuất dữ liệu thô ra `data/raw_orders.json` với timestamp.

3. **Thiết lập n8n bằng Docker**
   - Triển khai n8n nội bộ: `docker-compose up -d n8n`.
   - Cấu hình Webhook trigger kích hoạt `crawler.py` theo lịch (cron: mỗi 30 phút hoặc theo yêu cầu).
   - Thiết lập error node: khi script lỗi, gửi thông báo tự động qua Email (Outlook).

4. **Chuẩn hóa dữ liệu đầu ra**
   - Viết `validator.py` kiểm tra schema của `raw_orders.json` (dùng `pydantic`).
   - Ghi log mỗi lần chạy vào `logs/crawler_YYYYMMDD.log`.

#### Kịch bản Kiểm thử Thành công

- [ ] Chạy `n8n Trigger` → Script thực thi, vượt qua màn hình đăng nhập, không bị block.
- [ ] Khi gặp lỗi mạng, retry tự động tối đa 3 lần trước khi gửi email alert.
- [ ] Xuất tệp `data/raw_orders.json` có cấu trúc đầy đủ (mã đơn, thời gian, nhà cung ứng, mã vạch).
- [ ] Log ghi nhận đầy đủ thời gian bắt đầu, kết thúc, số bản ghi thu thập được.

#### Rủi ro & Phương án Dự phòng

| Rủi ro | Xác suất | Phương án |
|---|---|---|
| Website đối tác thay đổi giao diện/selector | Cao | Giai đoạn 4 có cơ chế self-healing; tạm thời email alert thủ công |
| CAPTCHA chặn bot | Trung bình | Tích hợp CAPTCHA solver API; dùng account có IP whitelist |
| Session hết hạn giữa chừng | Thấp | Lưu và tái sử dụng session; tự đăng nhập lại khi phát hiện redirect |

---

### 🟨 GIAI ĐOẠN 2: Tích hợp RAG Đối chiếu Tri thức Doanh nghiệp

**Mục tiêu:** Giúp hệ thống tự đọc hiểu quy định nội bộ, phát hiện sai sót trong dữ liệu đơn hàng và xuất báo cáo vi phạm.

#### Tác vụ thực hiện

1. **Chuẩn bị tài liệu Tri thức**
   - Soạn thảo và chuẩn hóa các tài liệu: quy chế vận hành, tiêu chuẩn chất lượng hàng hóa, quy định mã vạch, SLA giao hàng tại `rag/knowledge.md`.
   - Chia nhỏ (chunking) tài liệu thành các đoạn 500–800 token với overlap 50 token.

2. **Khởi tạo VectorDB**
   - Cài đặt và cấu hình **Qdrant** (hoặc Chroma) chạy local qua Docker.
   - Viết `embed_knowledge.py`: đọc tài liệu, tạo embedding (OpenAI `text-embedding-3-small` hoặc local model), nạp vào VectorDB.
   - Đảm bảo chạy lại script này mỗi khi tài liệu được cập nhật.

3. **Viết mã nguồn `analyzer.py`**
   - Nhận đầu vào: `data/raw_orders.json` từ Giai đoạn 1.
   - Với mỗi đơn hàng: thực hiện semantic search trên VectorDB để lấy các điều khoản liên quan.
   - Xây dựng prompt gửi LLM (GPT-4o hoặc Gemini 1.5 Pro): `[Dữ liệu đơn hàng] + [Điều khoản liên quan] → Phát hiện vi phạm`.
   - Parse kết quả trả về (JSON structured output) để tránh hallucination.

4. **Xuất Báo cáo**
   - Tạo `data/report.txt` và `data/report.json` với danh sách: mã đơn vi phạm, loại vi phạm, điều khoản bị vi phạm, mức độ nghiêm trọng (cao/trung bình/thấp).
   - Tích hợp vào n8n: sau khi phân tích xong, gửi tóm tắt báo cáo qua Email Outlook.

#### Kịch bản Kiểm thử Thành công

- [ ] Chạy `embed_knowledge.py` → VectorDB có dữ liệu, query test trả về đoạn văn bản liên quan.
- [ ] AI đọc `raw_orders.json` từ G1, chỉ ra chính xác ≥90% mã đơn vi phạm quy định thời gian giao hoặc mã vạch.
- [ ] Kết quả trả về dạng JSON có cấu trúc (không phải free text tự do).
- [ ] Xuất `data/report.txt` và `data/report.json` đầy đủ.

#### Rủi ro & Phương án Dự phòng

| Rủi ro | Xác suất | Phương án |
|---|---|---|
| LLM hallucinate điều khoản không có trong tài liệu | Trung bình | Dùng structured output + yêu cầu trích dẫn chunk nguồn |
| Chi phí API LLM vượt ngân sách | Thấp | Giới hạn token, dùng model nhỏ hơn cho batch lớn |
| Tài liệu quy chuẩn chưa đầy đủ | Cao | Họp với chuyên môn để hoàn thiện `knowledge.md` trước tuần 3 |

---

### 🟧 GIAI ĐOẠN 3: Triển khai Thị giác Máy tính & Phần cứng (YOLO + RoboClaw)

**Mục tiêu:** Mở rộng giám sát thực tế qua xử lý hình ảnh; kích hoạt phản hồi vật lý khi phát hiện sản phẩm lỗi.

> ⚠️ **Lưu ý quan trọng:** Giai đoạn này có hai chế độ vận hành:  
> - **Simulation Mode** (không cần phần cứng): Dùng ảnh/video mẫu, mock tín hiệu RoboClaw ra console.  
> - **Hardware Mode** (cần camera + RoboClaw): Chạy thực tế trên dây chuyền.  
> Nên phát triển và kiểm thử ở Simulation Mode trước.

#### Tác vụ thực hiện

1. **Cài đặt môi trường Computer Vision**
   - Cài đặt `ultralytics` (YOLOv8), `opencv-python`, `torch`.
   - Kiểm tra CUDA khả dụng nếu có GPU; nếu không, chạy CPU mode (chậm hơn nhưng vẫn hoạt động).

2. **Chuẩn bị Dataset**
   - Thu thập ≥200 ảnh mỗi class: sản phẩm đạt chuẩn / sản phẩm lỗi.
   - Gán nhãn bằng **Roboflow** (bounding box), export format YOLO.
   - Chia tập train/val/test theo tỉ lệ 70/20/10.

3. **Training & Validation**
   - Fine-tune YOLOv8n hoặc YOLOv8s trên dataset nội bộ (transfer learning từ COCO).
   - Mục tiêu: mAP@0.5 ≥ 80%, Confidence Score ≥ 80% trên tập test.
   - Lưu model tốt nhất vào `models/best.pt`.

4. **Viết `vision_inspector.py`**
   - Đọc đầu vào: webcam live stream hoặc thư mục ảnh/video batch.
   - Vẽ bounding box, hiển thị confidence score.
   - Khi phát hiện lỗi: ghi log vào `logs/defect_YYYYMMDD.log`, lưu ảnh vào `data/defects/`.
   - **Simulation Mode:** In ra console `[MOCK] RoboClaw signal: REJECT`.
   - **Hardware Mode:** Gửi tín hiệu qua cổng Serial đến RoboClaw.

5. **Tích hợp RoboClaw (Hardware Mode)**
   - Cài đặt thư viện `roboclaw_python`.
   - Viết module `actuator.py` điều khiển motor: kích hoạt cánh tay gạt, bật đèn báo động.
   - Test tín hiệu độc lập trước khi tích hợp với YOLO.

#### Kịch bản Kiểm thử Thành công

**Simulation Mode:**
- [ ] Đưa ảnh sản phẩm lỗi → YOLO gán bounding box chính xác, Confidence ≥ 80%.
- [ ] Console log hiển thị `[MOCK] RoboClaw signal: REJECT` với timestamp.

**Hardware Mode (nếu có phần cứng):**
- [ ] Webcam nhận diện sản phẩm lỗi real-time tại ≥15 FPS.
- [ ] Tín hiệu gửi thành công đến RoboClaw trong ≤500ms sau khi phát hiện lỗi.
- [ ] Đèn báo động / cánh tay gạt kích hoạt đúng như thiết kế.

#### Rủi ro & Phương án Dự phòng

| Rủi ro | Xác suất | Phương án |
|---|---|---|
| Không có phần cứng kịp tiến độ | Cao | Chạy hoàn toàn Simulation Mode trong PoC; Hardware Mode là Phase 2 |
| Dataset không đủ đa dạng, model kém | Trung bình | Data augmentation (rotation, brightness) bằng Roboflow; tăng dataset |
| Độ trễ xử lý cao trên CPU | Trung bình | Dùng YOLOv8n (model nhỏ nhất); giảm resolution đầu vào |

---

### 🟩 GIAI ĐOẠN 4: Kỹ sư hóa Agent Điều hành Hệ thống (Hermes + Orchestrator)

**Mục tiêu:** Đóng gói toàn bộ luồng vận hành G1→G2→G3, để Agent tự động quản lý, phát hiện lỗi, tự phục hồi và báo cáo.

#### Tác vụ thực hiện

1. **Thiết lập Orchestrator**
   - Đánh giá và lựa chọn framework phù hợp: **LangGraph** (nếu cần state machine phức tạp), **CrewAI** (nếu cần multi-agent), hoặc custom Python (nếu đơn giản hơn).
   - Định nghĩa các Tool mà Agent có thể gọi: `run_crawler`, `run_analyzer`, `run_vision`, `generate_report`.
   - Cấu hình vòng lặp điều phối: Agent tự quyết định thứ tự chạy các công cụ dựa trên trạng thái hệ thống.

2. **Cấu hình Hermes Agent**
   - Tạo tệp bộ nhớ dài hạn: `memory/MEMORY.md` (lịch sử vận hành), `memory/USER.md` (cấu hình người dùng), `memory/SYSTEM_STATE.md` (trạng thái hệ thống hiện tại).
   - Cấu hình context window management: tóm tắt lịch sử cũ khi context quá dài.

3. **Kết nối Outlook Mail Gateway**
   - Cấu hình tài khoản email Outlook (SMTP/IMAP hoặc Microsoft Graph API), lưu credentials vào `.env`.
   - Viết `mail_gateway.py`: nhận lệnh qua Email, xác thực người dùng (whitelist email người gửi).
   - Các lệnh hỗ trợ thông qua tiêu đề email: `[CMD] RUN_FULL` (chạy toàn bộ), `[CMD] STATUS` (xem trạng thái), `[CMD] REPORT` (xuất báo cáo), `[CMD] STOP` (dừng khẩn cấp).

4. **Cơ chế Tự phục hồi (Self-healing)**
   - Khi `crawler.py` lỗi do selector CSS thay đổi: Agent tự chụp ảnh màn hình, gửi cho LLM phân tích DOM mới, cập nhật selector trong code.
   - Khi `analyzer.py` lỗi do API timeout: tự retry với exponential backoff.
   - Khi bất kỳ bước nào lỗi quá 3 lần: escalate alert qua Email Outlook, dừng vòng lặp, chờ lệnh thủ công.

5. **Monitoring & Logging**
   - Dashboard đơn giản: ghi `logs/system_YYYYMMDD.log` với trạng thái mỗi bước.
   - Tích hợp n8n để hiển thị lịch sử run dạng timeline.

#### Kịch bản Kiểm thử Thành công

- [ ] Gửi email chứa tiêu đề `[CMD] RUN_FULL` đến tài khoản Outlook → Hermes kích hoạt tuần tự: crawl → analyze → vision → report.
- [ ] Báo cáo kết quả được phản hồi lại Email Admin trong < 3 phút.
- [ ] Giả lập lỗi selector → Agent tự phát hiện, cập nhật, gửi email xác nhận trước khi apply và chạy lại thành công mà không cần can thiệp.
- [ ] Hệ thống chạy vòng lặp định kỳ 24h liên tục mà không crash.

#### Rủi ro & Phương án Dự phòng

| Rủi ro | Xác suất | Phương án |
|---|---|---|
| Self-healing LLM cập nhật selector sai | Trung bình | Human-in-the-loop: gửi diff qua email để admin phản hồi xác nhận trước khi apply |
| Agent vào vòng lặp vô hạn khi gặp lỗi lặp đi lặp lại | Thấp | Circuit breaker: sau 3 lần lỗi → dừng & gửi email alert, không retry thêm |
| Chi phí LLM tăng cao khi Agent gọi API liên tục | Trung bình | Rate limiting, cache kết quả phân tích tương tự, dùng model nhỏ cho tác vụ đơn giản |

---

## 📈 Tiêu chí Đánh giá Thành công PoC (KPIs)

| # | Chỉ số | Mục tiêu | Giai đoạn |
|---|---|---|---|
| 1 | **RAG Accuracy** — Tỷ lệ phát hiện đúng vi phạm quy chuẩn | ≥ 90% | G2 |
| 2 | **Vision Precision** — mAP@0.5 trên tập test sản phẩm lỗi | ≥ 80% | G3 |
| 3 | **End-to-end Performance** — Từ lúc trigger đến khi xuất báo cáo | < 3 phút | G1→G2 |
| 4 | **Automation Rate** — Vận hành không cần can thiệp thủ công (staging) | 100% | G4 |
| 5 | **System Uptime** — Thời gian hoạt động liên tục không crash | ≥ 24h | G4 |
| 6 | **Self-healing Success Rate** — Tỷ lệ tự phục hồi lỗi selector thành công | ≥ 70% | G4 |

---

## 🔗 Ma trận Phụ thuộc Giữa Các Giai đoạn

```
G1 (Hoàn thành) ──────────────────────────────┐
                                                │
G1 (raw_orders.json) ──► G2 (Phân tích RAG)  │
                                                ├──► G4 (Agent điều phối)
G1 (data pipeline) ──► G3 (Vision input)      │
                                                │
G2 + G3 (Kết quả) ────────────────────────────┘
```

**Lưu ý quan trọng:**
- G2 và G3 có thể phát triển **song song** sau khi G1 hoàn thành.
- G4 chỉ bắt đầu khi **cả G1, G2, G3** đã ổn định và pass kiểm thử.
- Nếu G3 bị trễ do phần cứng, G4 vẫn có thể bắt đầu với G3 ở Simulation Mode.

---

## 📁 Cấu trúc Thư mục Dự án

```
project-root/
├── .env                        # Credentials (không commit)
├── docker-compose.yml          # n8n, Qdrant
├── requirements.txt
│
├── data/
│   ├── raw_orders.json         # Output G1
│   ├── report.txt              # Output G2
│   ├── report.json             # Output G2 (structured)
│   └── defects/                # Ảnh sản phẩm lỗi - G3
│
├── logs/
│   ├── crawler_YYYYMMDD.log
│   ├── defect_YYYYMMDD.log
│   └── system_YYYYMMDD.log
│
├── rag/
│   └── knowledge.md            # Tài liệu quy chuẩn nội bộ
│
├── models/
│   └── best.pt                 # YOLO model đã train
│
├── memory/                     # Hermes Agent memory
│   ├── MEMORY.md
│   ├── USER.md
│   └── SYSTEM_STATE.md
│
├── src/
│   ├── crawler.py              # G1: RPA scraping
│   ├── validator.py            # G1: Schema validation
│   ├── embed_knowledge.py      # G2: Nạp VectorDB
│   ├── analyzer.py             # G2: RAG analysis
│   ├── vision_inspector.py     # G3: YOLO detection
│   ├── actuator.py             # G3: RoboClaw control
│   ├── mail_gateway.py         # G4: Outlook Mail Gateway
│   └── agent_orchestrator.py  # G4: Hermes Agent
│
└── tests/
    ├── test_crawler.py
    ├── test_analyzer.py
    └── test_vision.py
```

---

## 🔒 Bảo mật & Tuân thủ

- Tất cả credentials lưu trong `.env`, không được commit lên version control.
- Thêm `.env` vào `.gitignore` ngay từ đầu.
- Whitelist địa chỉ Email được phép gửi lệnh đến Agent.
- Dữ liệu đơn hàng thô được xóa khỏi disk sau 7 ngày (nếu chứa thông tin nhạy cảm).
- Định kỳ rotate API keys LLM và credentials scraping.

---

*Tài liệu này cần được review và xác nhận bởi team kỹ thuật trước khi bắt đầu triển khai.*
