# 🔧 KẾ HOẠCH GIAI ĐOẠN A: DỌN DẸP & SỬA LỖI CODE

> **Phiên bản:** 1.0  
> **Trạng thái:** Chờ thực thi  
> **Thời gian ước tính:** 1 tuần  
> **Số file cần sửa:** 7 file + 2 file mới  
> **Tiền đề:** Toàn bộ 10 file Python đã hoàn thiện ở mức PoC. Giai đoạn này tập trung dọn dẹp, loại bỏ code thừa và chuẩn hóa cấu hình.

---

## 📋 Tổng quan 7 Nhiệm vụ

| # | Nhiệm vụ | File | Mức độ | Loại |
|---|----------|------|--------|------|
| 1 | Cập nhật `.env.example` | `.env.example` | 🟡 Trung bình | Sửa |
| 2 | Dọn `requirements.txt` | `requirements.txt` | 🟡 Trung bình | Sửa |
| 3 | Fix hardcode date trong analyzer | `src/analyzer.py` | 🟢 Nhẹ | Sửa |
| 4 | Xóa dead code trong crawler | `src/crawler.py` | 🟢 Nhẹ | Sửa |
| 5 | Thêm `__init__.py` cho package | `src/` + `tests/` | 🟡 Trung bình | Tạo mới |
| 6 | Bảo mật `docker-compose.yml` | `docker-compose.yml` | 🟡 Trung bình | Sửa |
| 7 | Chạy & xác nhận toàn bộ test | Toàn bộ `tests/` | 🟠 Quan trọng | Kiểm tra |

---

## NV-1: Cập nhật `.env.example`

### Vấn đề

File `.env.example` hiện tại chỉ có **6 biến** nhưng code sử dụng **15+ biến**. Ngoài ra còn chứa 3 biến `TELEGRAM_*` và 1 biến `OPENAI_API_KEY` không hề được import trong code.

### Biến có trong `.env.example` nhưng KHÔNG dùng trong code

| Biến | Lý do xóa |
|------|-----------|
| `TELEGRAM_BOT_TOKEN` | Không có module Telegram nào trong `src/` |
| `TELEGRAM_ALLOWED_CHAT_IDS` | Tương tự — dấu vết của phiên bản cũ (trước khi chuyển sang Outlook) |
| `DISABLE_OUTBOUND_TELEGRAM` | Tương tự |
| `OPENAI_API_KEY` | Code chỉ import `google-generativeai`, không import `openai` |

### Biến THIẾU trong `.env.example` nhưng code SỬ DỤNG

| Biến thiếu | File sử dụng | Giá trị mặc định trong code |
|------------|-------------|---------------------------|
| `PORTAL_URL` | `src/crawler.py` | `http://localhost:8888` |
| `OUTLOOK_USER` | `src/mail_sender.py`, `src/mail_gateway.py` | `""` (mock mode) |
| `OUTLOOK_PASS` | Tương tự | `""` (mock mode) |
| `SMTP_SERVER` | `src/mail_sender.py` | `smtp.office365.com` |
| `SMTP_PORT` | Tương tự | `587` |
| `IMAP_SERVER` | `src/mail_gateway.py` | `imap.office365.com` |
| `IMAP_PORT` | Tương tự | `993` |
| `ADMIN_EMAIL` | `src/mail_sender.py` | Không có mặc định |
| `DISABLE_OUTBOUND_MAIL` | `src/mail_gateway.py` (dòng 92) | `false` |
| `HW_MODE` | `src/vision_inspector.py`, `src/actuator.py` | `false` |
| `VISION_SIMULATION` | `src/vision_inspector.py` | `true` |
| `ROBOCLAW_SIMULATION` | `src/actuator.py` | `true` |
| `ROBOCLAW_PORT` | `src/actuator.py` | `COM3` |
| `ROBOCLAW_BAUDRATE` | Tương tự | `38400` |
| `YOLO_MODEL_PATH` | `src/vision_inspector.py` | `models/best.pt` |
| `N8N_AUTH_USER` | `docker-compose.yml` | Hardcode `admin` |
| `N8N_AUTH_PASSWORD` | Tương tự | Hardcode `admin_password_here` |

### Thay đổi cần thực hiện

Thay **toàn bộ** nội dung `.env.example` bằng:

```diff
- # Template for Environment variables
-
- # Telegram Bot
- TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
- TELEGRAM_ALLOWED_CHAT_IDS=chat_id_1,chat_id_2
- DISABLE_OUTBOUND_TELEGRAM=true
-
- # LLM APIs
- OPENAI_API_KEY=your_openai_api_key_here
- GEMINI_API_KEY=your_gemini_api_key_here
-
- # Vector Database
- QDRANT_HOST=localhost
- QDRANT_PORT=6333
-
- # RPA Credentials
- CRAWLER_USERNAME=your_username_here
- CRAWLER_PASSWORD=your_password_here
- CAPTCHA_API_KEY=your_captcha_solver_key_here

+ # ==============================================================================
+ # SMART-POC-AUTOMATION — Environment Configuration Template
+ # Copy this file to .env and fill in real values.
+ # ==============================================================================
+
+ # ---------- Phase 1: RPA Crawler ----------
+ PORTAL_URL=http://localhost:8888
+ CRAWLER_USERNAME=admin
+ CRAWLER_PASSWORD=admin123
+ CAPTCHA_API_KEY=                              # Optional: 2Captcha/Anti-Captcha API key
+
+ # ---------- Phase 2: RAG & LLM ----------
+ GEMINI_API_KEY=                               # Optional: Google Gemini API key (falls back to mock embeddings)
+ QDRANT_HOST=localhost
+ QDRANT_PORT=6333
+
+ # ---------- Phase 3: Computer Vision & Hardware ----------
+ HW_MODE=false                                 # true = real camera + motor, false = software only
+ VISION_SIMULATION=true                        # true = skip YOLO, use filename heuristic
+ YOLO_MODEL_PATH=models/best.pt
+ ROBOCLAW_SIMULATION=true                      # true = mock motor signals to console
+ ROBOCLAW_PORT=COM3
+ ROBOCLAW_BAUDRATE=38400
+
+ # ---------- Phase 4: Outlook Mail Gateway ----------
+ OUTLOOK_USER=                                 # Outlook email address (empty = mock mode)
+ OUTLOOK_PASS=                                 # Outlook password or app password
+ SMTP_SERVER=smtp.office365.com
+ SMTP_PORT=587
+ IMAP_SERVER=imap.office365.com
+ IMAP_PORT=993
+ ADMIN_EMAIL=                                  # Email to receive reports and alerts
+ DISABLE_OUTBOUND_MAIL=true                    # true = log emails instead of sending
+
+ # ---------- Docker Services (n8n) ----------
+ N8N_AUTH_USER=admin
+ N8N_AUTH_PASSWORD=change_this_strong_password
```

### Checklist kiểm tra

- [ ] Xóa 4 biến Telegram/OpenAI không dùng
- [ ] Thêm 17 biến mới theo đúng phân nhóm
- [ ] Comment mô tả rõ ràng cho từng biến
- [ ] Giá trị mặc định phù hợp chế độ Simulation/Mock

---

## NV-2: Dọn `requirements.txt`

### Vấn đề

File `requirements.txt` có **6 thư viện** được khai báo nhưng **không import** bất kỳ đâu trong code. Đồng thời thiếu `numpy` (được dùng trong `src/embed_knowledge.py` dòng 64).

### Thư viện THỪA (khai báo nhưng không import)

| Thư viện | Dòng | Lý do xóa |
|----------|------|-----------|
| `langchain>=0.1.0` | L12 | Code dùng `google-generativeai` trực tiếp, không qua LangChain |
| `langchain-community>=0.0.10` | L13 | Tương tự |
| `langchain-openai>=0.0.2` | L14 | Tương tự |
| `openai>=1.10.0` | L16 | Code chỉ dùng Gemini API |
| `langgraph>=0.0.15` | L26 | Orchestrator tự viết bằng Python thuần, không dùng LangGraph |
| `crewai>=0.1.0` | L27 | Không có multi-agent framework nào trong code |

### Thư viện THIẾU

| Thư viện | File sử dụng | Dòng import |
|----------|-------------|-------------|
| `numpy` | `src/embed_knowledge.py` | L64: `import numpy as np` |

### Thay đổi cần thực hiện

```diff
  # ==============================================================================
  # SMART-POC-AUTOMATION DEPENDENCIES
  # ==============================================================================
  
  # Phase 1: RPA & Data Collection
  playwright>=1.40.0
  python-dotenv>=1.0.0
  tenacity>=8.2.0
  pydantic>=2.0.0
  
- # Phase 2: RAG & LLM Integration
- langchain>=0.1.0
- langchain-community>=0.0.10
- langchain-openai>=0.0.2
+ # Phase 2: RAG & Vector Database
  qdrant-client>=1.7.0
- openai>=1.10.0
  google-generativeai>=0.3.0
+ numpy>=1.24.0
  
  # Phase 3: Computer Vision & Hardware
  ultralytics>=8.1.0
  opencv-python>=4.9.0
  torch>=2.1.0
  torchvision>=0.16.0
  
- # Phase 4: Agentic Orchestration & Bot Gateway
- langgraph>=0.0.15
- crewai>=0.1.0
+ # Phase 4: Outlook Mail Gateway (Microsoft Auth)
  msal>=1.20.0
```

**Lợi ích:** Giảm từ **14 dependencies** xuống **11** → cài đặt nhanh hơn, ít xung đột version hơn, `pip install` nhanh hơn đáng kể.

### Checklist kiểm tra

- [ ] Xóa 6 thư viện thừa (`langchain`, `langchain-community`, `langchain-openai`, `openai`, `langgraph`, `crewai`)
- [ ] Thêm `numpy>=1.24.0`
- [ ] Cập nhật comment section headers
- [ ] Chạy `pip install -r requirements.txt` trong venv sạch — không lỗi

---

## NV-3: Fix hardcode date trong `analyzer.py`

### Vấn đề

Tại `src/analyzer.py` dòng 79, ngày phân tích bị hardcode cứng thành `"2026-05-25"`. Điều này khiến kết quả phân tích vi phạm SLA **luôn sai** khi chạy vào ngày khác.

### Mã hiện tại

```python
# Line 78-79 (src/analyzer.py)
# Assume analysis date (current date) is 2026-05-25 for testing consistency
analysis_date = datetime.strptime("2026-05-25", "%Y-%m-%d")
```

### Thay đổi cần thực hiện

```diff
- # Assume analysis date (current date) is 2026-05-25 for testing consistency
- analysis_date = datetime.strptime("2026-05-25", "%Y-%m-%d")
+ # Use current date for SLA delay calculation
+ analysis_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
```

**Tại sao `.replace(hour=0, ...)`?** Để đảm bảo so sánh ngày chỉ tính chênh lệch theo NGÀY, không bị ảnh hưởng bởi giờ/phút hiện tại.

### Tác động

- Kết quả SLA delay sẽ chính xác theo ngày chạy thực tế
- Tests cần kiểm tra lại vì kết quả có thể thay đổi theo ngày chạy

### Checklist kiểm tra

- [ ] Sửa dòng 78–79 trong `src/analyzer.py`
- [ ] Chạy `python -m pytest tests/test_analyzer.py` — vẫn pass
- [ ] Xác nhận `data/report.json` có ngày phân tích đúng

---

## NV-4: Xóa dead code trong `crawler.py`

### Vấn đề

Hàm `extract_orders_from_html()` tại `src/crawler.py` dòng 172–175 là **dead code** — function thân rỗng (return `[]`), không được gọi bất kỳ đâu trong toàn bộ codebase. Code thực tế sử dụng hàm `parse_orders_table()`.

### Mã cần xóa

```python
# Lines 172-175 (src/crawler.py)
async def extract_orders_from_html(html_content: str) -> list:
    """Parses orders table from HTML page content."""
    logger.info("Parsing orders from HTML content...")
    return []
```

### Thay đổi cần thực hiện

```diff
      raise AuthException("Login failed for unknown reason.")
          
      logger.info("Login successful.")
      await save_session(context)
  
- async def extract_orders_from_html(html_content: str) -> list:
-     """Parses orders table from HTML page content."""
-     logger.info("Parsing orders from HTML content...")
-     return []
- 
  # Selector configuration file for self-healing
  SELECTORS_FILE = "data/selectors.json"
```

### Xác nhận dead code

```bash
# Kiểm tra không file nào gọi function này
grep -rn "extract_orders_from_html" .
# Kết quả mong đợi: chỉ nên thấy chính dòng khai báo (L172) — không có nơi nào gọi
```

### Checklist kiểm tra

- [ ] Xóa 4 dòng (172–175) trong `src/crawler.py`
- [ ] Xác nhận `grep` không tìm thấy `extract_orders_from_html` ở nơi nào khác
- [ ] Chạy `python -m pytest tests/test_crawler.py` — vẫn pass

---

## NV-5: Thêm `__init__.py` cho package structure

### Vấn đề

Hiện tại cả `src/` và `tests/` đều **thiếu `__init__.py`**, khiến Python không nhận diện chúng là package chuẩn. Code phải dùng hack `sys.path.append()` ở **10 file**:

- `src/crawler.py:17`
- `src/analyzer.py:19`
- `src/agent_orchestrator.py:17`
- `src/mail_gateway.py:17`
- `src/vision_inspector.py:17`
- `tests/test_crawler.py:23`
- `tests/test_analyzer.py:14`
- `tests/test_integration.py:19`
- `tests/test_mail_gateway.py:14`
- `tests/test_vision.py:12`

### Thay đổi cần thực hiện

**Tạo file mới: `src/__init__.py`**
```python
"""
Smart-POC-Automation source package.
Contains modules for RPA, RAG, Vision, and Agentic Orchestration.
"""
```

**Tạo file mới: `tests/__init__.py`**
```python
"""
Smart-POC-Automation test package.
"""
```

### ⚠️ Lưu ý quan trọng

> Việc xóa các dòng `sys.path.append` khỏi 10 file **có thể gây lỗi import** tùy cách chạy (chạy trực tiếp file vs chạy từ project root).
>
> **Khuyến nghị:** Ở Giai đoạn A, chỉ **tạo `__init__.py`** mà **CHƯA xóa** `sys.path.append`. Điều này đảm bảo tương thích ngược. Việc refactor import sẽ thực hiện ở giai đoạn sau khi cấu trúc lại toàn bộ project.

### Checklist kiểm tra

- [ ] Tạo `src/__init__.py`
- [ ] Tạo `tests/__init__.py`
- [ ] Chạy `python -m pytest tests/` từ project root — vẫn pass
- [ ] Chạy `python src/mock_server.py` — vẫn khởi động được

---

## NV-6: Bảo mật `docker-compose.yml`

### Vấn đề

File `docker-compose.yml` hiện **hardcode mật khẩu n8n** (`admin_password_here`) trực tiếp trong file. File này được commit lên Git → lộ credential.

### Mã hiện tại

```yaml
# Lines 19-22 (docker-compose.yml)
environment:
  - N8N_BASIC_AUTH_ACTIVE=true
  - N8N_BASIC_AUTH_USER=admin
  - N8N_BASIC_AUTH_PASSWORD=admin_password_here
```

### Thay đổi cần thực hiện

```diff
      environment:
        - N8N_BASIC_AUTH_ACTIVE=true
-       - N8N_BASIC_AUTH_USER=admin
-       - N8N_BASIC_AUTH_PASSWORD=admin_password_here
+       - N8N_BASIC_AUTH_USER=${N8N_AUTH_USER:-admin}
+       - N8N_BASIC_AUTH_PASSWORD=${N8N_AUTH_PASSWORD:-change_this_strong_password}
        - GENERIC_TIMEZONE=Asia/Ho_Chi_Minh
```

Cú pháp `${VAR:-default}` nghĩa là: dùng giá trị từ `.env`, nếu không có thì dùng giá trị mặc định. Docker Compose tự đọc file `.env` cùng thư mục.

### Checklist kiểm tra

- [ ] Sửa 2 dòng trong `docker-compose.yml`
- [ ] Đảm bảo `.env.example` đã có `N8N_AUTH_USER` và `N8N_AUTH_PASSWORD` (NV-1)
- [ ] Chạy `docker-compose config` — không lỗi syntax

---

## NV-7: Chạy & Xác nhận toàn bộ Test

### Quy trình kiểm tra

#### Bước 1: Chuẩn bị môi trường

```bash
# Từ project root
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

#### Bước 2: Chạy unit tests (không cần Docker)

```bash
# Chạy toàn bộ test suite
python -m pytest tests/ -v --tb=short

# Hoặc chạy từng file
python -m pytest tests/test_crawler.py -v
python -m pytest tests/test_analyzer.py -v
python -m pytest tests/test_vision.py -v
python -m pytest tests/test_mail_gateway.py -v
python -m pytest tests/test_integration.py -v
```

#### Bước 3: Chạy demo E2E thủ công

```bash
# Terminal 1: Khởi động mock server
python src/mock_server.py

# Terminal 2: Chạy pipeline
python src/agent_orchestrator.py
```

#### Bước 4: Kiểm tra output

| File output | Kiểm tra |
|------------|----------|
| `data/raw_orders.json` | Có dữ liệu, format JSON hợp lệ |
| `data/report.json` | Có danh sách vi phạm, cấu trúc đúng |
| `data/report.txt` | Có nội dung text, đọc được |
| `logs/system_*.log` | Ghi nhận đầy đủ các bước |
| `memory/SYSTEM_STATE.md` | Trạng thái `Idle` sau khi hoàn thành |
| `memory/MEMORY.md` | Có log execution mới |

### Tiêu chí PASS Giai đoạn A

- [ ] **13+ test cases** pass (0 failures, 0 errors)
- [ ] E2E demo chạy thành công: mock_server → crawler → analyzer → vision → report
- [ ] Không còn warning nào liên quan đến import hoặc missing dependency
- [ ] `.env.example` đầy đủ, copy sang `.env` là chạy được ngay
- [ ] `requirements.txt` sạch — chỉ chứa thư viện thực sự import

---

## 📊 Tóm tắt tổng thể Giai đoạn A

| # | Nhiệm vụ | Thời gian | Rủi ro |
|---|----------|-----------|--------|
| 1 | `.env.example` | 15 phút | Thấp |
| 2 | `requirements.txt` | 10 phút | Thấp |
| 3 | Fix date `analyzer.py` | 5 phút | Thấp (cần check test) |
| 4 | Xóa dead code `crawler.py` | 5 phút | Rất thấp |
| 5 | Thêm `__init__.py` | 5 phút | Rất thấp |
| 6 | Bảo mật `docker-compose.yml` | 10 phút | Thấp |
| 7 | Chạy toàn bộ test | 30–60 phút | Trung bình (có thể phát sinh lỗi) |

> **Tổng thời gian thực hiện code: ~50 phút**  
> **Tổng thời gian kiểm tra + fix lỗi phát sinh: ~2–3 giờ**

---

*Tài liệu này cần được review trước khi bắt đầu thực thi.*
