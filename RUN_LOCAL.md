# GreenSegment AI — Website localhost (React + FastAPI)

## Cluster Explorer — Giai đoạn 1

Trong sidebar, chọn **Cluster Explorer**, rồi chọn cụm 0, 1 hoặc 2. Trang hiển thị thống kê toàn bộ cụm, độc lập với bộ lọc sidebar: số lượng/tỷ lệ đô thị, tâm K-Means, trung bình/trung vị tỷ trọng, độ lệch chuẩn tổng thể, IQR và phân bố khoảng cách Euclid. So sánh cơ cấu giữa cả ba cụm dùng trung bình theo đô thị, không gia quyền theo lượng phát thải.

Tâm đọc từ `reports/cluster_analysis/cluster_centroids_2024.csv`; kiểm tra với metadata và mã huấn luyện cho thấy mô hình dùng tỷ trọng gốc 0–1, không scaling/PCA. Backend kiểm tra lại khoảng cách của đủ 11.422 đô thị, không huấn luyện lại. Tâm có thể lệch nhẹ với trung bình tính lại theo nhãn cuối cùng. Độ lệch chuẩn/IQR tỷ trọng có đơn vị điểm phần trăm; khoảng cách không có đơn vị. Phân vị nội suy tuyến tính, độ lệch chuẩn dùng `ddof=0`.

API mới:

Báo cáo Gemini được giới hạn 250–400 từ (đếm theo khoảng trắng), hiển thị bốn phần: Đặc điểm nổi bật; So sánh các cụm; Độ phân tán và tính đại diện; Hạn chế và hướng nghiên cứu. Backend chọn ba lĩnh vực nổi bật và ba khác biệt từ thống kê thật, làm tròn bản dữ liệu gửi Gemini đến hai chữ số cho tỷ trọng/điểm phần trăm và bốn chữ số cho khoảng cách, giữ nguyên thống kê gốc. JSON vẫn dùng các trường hiện có, giới hạn 2–3 mục so sánh và 2–3 câu hỏi nghiên cứu. Phản hồi sai cấu trúc hoặc ngoài giới hạn độ dài sẽ bị từ chối; không có báo cáo giả thay thế. Prompt yêu cầu các câu hỏi ngoài phạm vi năm 2024 nêu rõ dữ liệu cần bổ sung và cấm suy luận nguyên nhân, chất lượng môi trường, thị trường hoặc khả thi công nghệ từ tỷ trọng.

- `GET /api/cluster-explorer`: thống kê Python của cả ba cụm.
- `GET /api/cluster-explorer/{cluster_id}/preview`: dữ liệu đầu vào Gemini, không gọi API ngoài.
- `POST /api/cluster-explorer/{cluster_id}/interpret`: diễn giải bằng Gemini, JSON gồm `summary`, `comparisons`, `dispersion_and_representativeness`, `research_questions`, `limitations`.

Nút **Phân tích bằng Gemini** gọi API thật khi backend có `GEMINI_API_KEY` (cách đặt key ở mục 5). Báo cáo tập trung diễn giải cụm, không yêu cầu đề xuất công nghệ xanh. API key chỉ ở backend. Phản hồi Gemini được kiểm tra cấu trúc; nội dung AI vẫn cần đối chiếu thống kê. Báo cáo được giữ trong bộ nhớ trang theo từng cụm; chuyển cụm sẽ bỏ qua phản hồi cũ đang chờ, nhưng không đảm bảo hủy yêu cầu đã gửi tới nhà cung cấp.

Chạy kiểm thử tại thư mục gốc: `python -m unittest discover -s tests -v` (cần FastAPI và `httpx`), sau đó chạy `npm run build` trong `web`. Kiểm thử dùng mock cho Gemini, không gọi API thật. Không cần cài Vnstock để sử dụng tính năng này.

Backend cache thống kê trong bộ nhớ; nếu thay bộ dữ liệu, cần khởi động lại backend. Dữ liệu và mô hình hiện có được giữ nguyên.

## 1. Giải nén đúng chỗ

Giải nén **nội dung ZIP** trực tiếp vào thư mục hiện tại:

```text
D:\DUE\NAM 2\AI4B\GreenSegment AI\
├── api\                  ← mới
├── web\                  ← mới
├── requirements-web.txt  ← mới
├── RUN_LOCAL.md          ← mới
├── data\                 ← của bạn, KHÔNG nằm trong ZIP
├── models\               ← của bạn, KHÔNG nằm trong ZIP
├── reports\              ← của bạn, KHÔNG nằm trong ZIP
└── src\                  ← của bạn, KHÔNG nằm trong ZIP
```

**Không** để các thư mục mới lồng dưới `GreenSegment-Web-Package` hoặc `GreenSegment AI\GreenSegment AI`. Ví dụ file cần có đường dẫn `GreenSegment AI\api\main.py`.

Không cần tạo lại CSV, JSON, `.joblib`, chạy lại K-Means hoặc thay `src/gemini_advisor.py`.

## 2. Điều kiện môi trường

- Python (khuyến nghị dùng môi trường Python mà bạn đã chạy được `gemini_advisor.py`).
- Node.js + npm. Kiểm tra trong VS Code PowerShell: `node -v` và `npm -v`.
- Cài các thư viện Python bổ sung ở file `requirements-web.txt`.

## 3. Terminal 1 — khởi động backend Python

Mở VS Code tại thư mục gốc `GreenSegment AI`, chạy:

```powershell
python -m pip install -r requirements-web.txt
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Mở `http://127.0.0.1:8000/docs` để kiểm tra các API. Một số API mẫu:

- `http://127.0.0.1:8000/api/health` — kiểm tra dữ liệu đã có.
- `http://127.0.0.1:8000/api/overview` — tổng quan 11.422 đô thị.
- `http://127.0.0.1:8000/api/cities?search=Nagoya` — tìm đô thị.
- `http://127.0.0.1:8000/api/clusters` — hồ sơ 3 cụm.

Nếu `/api/health` trả `ok: false`, kiểm tra vị trí các file dữ liệu gốc. Backend không tạo dữ liệu giả.

## 4. Terminal 2 — khởi động website React

Mở Terminal **mới**, vẫn trong thư mục gốc, chạy:

```powershell
cd web
npm install
npm run dev
```

Mở **http://127.0.0.1:5173** trong trình duyệt.

Hai Terminal phải tiếp tục mở khi dùng localhost. Nhấn Ctrl+C trong mỗi Terminal để dừng.

## 5. Bật tính năng Gemini AI

Website vẫn dùng được bản đồ/biểu đồ/tra cứu khi chưa có API key. Để gọi Gemini, **nhập key trong Terminal 1 trước khi khởi động backend**:

```powershell
$secure = Read-Host "Nhap GEMINI_API_KEY" -AsSecureString
$env:GEMINI_API_KEY = [System.Net.NetworkCredential]::new("", $secure).Password
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Nếu backend đang chạy mà chưa đặt key, nhấn Ctrl+C để dừng, đặt biến môi trường, rồi chạy lại lệnh `uvicorn`.

**Không** đặt key trong `web/`, `.jsx`, `vite.config.js`, `.env` bắt đầu bằng `VITE_`, hoặc commit lên GitHub.

Ở trang **Giải pháp công nghệ xanh**:

- **Xem dữ liệu đầu vào**: không gọi Gemini API, không dùng quota.
- **Phân tích bằng Gemini**: gọi API thật; nếu Gemini bận, backend tự thử lại theo logic hiện có của `src/gemini_advisor.py`.

## 6. Website có những gì?

1. **Tổng quan**: số liệu thật, bản đồ thế giới, điểm đô thị tô màu theo K-Means, tỷ trọng ngành của 3 cụm.
2. **Tra cứu đô thị**: tìm kiếm, phân trang, xem hồ sơ phát thải và so sánh đô thị với trung bình cụm.
3. **Giải pháp công nghệ xanh**: gọi `src/gemini_advisor.py` cho đô thị hoặc cụm, hiển thị giải pháp với điều kiện, giới hạn và nguồn.
4. **Giới thiệu**: dữ liệu, phương pháp và giới hạn dự án.

Bộ lọc sidebar (quốc gia, cụm, lĩnh vực có tỷ trọng lớn nhất) áp dụng cho **Tổng quan** và **Tra cứu đô thị**. Chế độ Advisor độc lập và cho phép chọn mọi đô thị/cụm.

Bản đồ mặc định lấy mẫu tối đa 5.000 điểm để trình duyệt chạy mượt (con số cụ thể được ghi dưới bản đồ), **không phải** chỉ có 5.000 đô thị trong dữ liệu; tra cứu vẫn bao phủ toàn bộ dữ liệu. Nền bản đồ OpenStreetMap cần kết nối Internet dù website chạy localhost.

## 7. Cách xử lý một vài lỗi thường gặp

- **`node`/`npm` không được nhận diện**: cài Node.js bản LTS và mở lại VS Code.
- **`ModuleNotFoundError: fastapi`**: chạy `python -m pip install -r requirements-web.txt` với đúng Python đang dùng.
- **Lỗi Windows Application Control khi cài Python package**: dùng môi trường Python đã chạy được trong dự án; không cần tắt bảo mật hệ thống.
- **`Failed to fetch` / `ECONNREFUSED 8000`**: backend chưa chạy hoặc chạy khác cổng 8000.
- **`404` / dữ liệu trống**: giải nén sai vị trí; kiểm tra `/api/health`.
- **`Gemini 503`**: phía dịch vụ Gemini đang quá tải, đã có retry; đừng liên tục gọi lại.
- **`GEMINI_API_KEY` chưa đặt**: nhập key đúng tại Terminal backend và chạy lại backend.
- **Bản đồ không tải được nền**: kiểm tra Internet/tường lửa đối với OpenStreetMap; các điểm tọa độ vẫn là dữ liệu local.
- **Port 5173 đang dùng**: dừng tiến trình cũ rồi chạy lại. Dùng cổng khác cần cập nhật `vite.config.js` và CORS backend.

## 8. Khi muốn publish sau này

- Tạo bản frontend với `cd web; npm run build` (thư mục `web/dist/`).
- Đưa FastAPI lên dịch vụ chạy Python; thiết lập `GEMINI_API_KEY` trong biến môi trường máy chủ.
- Đưa frontend lên host static; đổi cấu hình proxy/API base URL tương ứng và cấu hình CORS chặt chẽ.
- Đánh giá thêm giới hạn truy cập, rate limiting và ngân sách API trước khi public Gemini endpoint; backend hiện ưu tiên **localhost**.

Dữ liệu gốc, mô hình và danh mục giải pháp đều thuộc quyền kiểm soát của bạn; ZIP này chỉ thêm lớp web mới.
