# GreenSegment AI — Website localhost (React + FastAPI)

## Market Explorer — Giai đoạn 3

### Chẩn đoán lỗi tạo báo cáo B2B

#### Kiểm soát số liệu bằng `verified_facts`

Python tạo danh mục facts từ kết quả truy vấn thật với ID, `value` đầy đủ độ chính xác, `display`, `kind`, `scope`, `source` và quy tắc làm tròn. `matching.*` là toàn bộ tập phù hợp, `top.*` là Top N hiển thị; `top.limit` là giới hạn được yêu cầu, có thể khác số thực tế hiển thị. Các facts đô thị chứa thứ hạng theo truy vấn, mã cụm, tỷ trọng, lượng GHG và chênh lệch tỷ trọng với trung bình matching/top. Năm và mã cụm có kiểu riêng, không dùng chung whitelist với số lượng.

Bản kiểm tra hiện tại có `validator_version: verified-facts-v2` trong log, chẩn đoán thành công và response lỗi. Đã sửa trường hợp câu vừa nêu cụm của đô thị vừa nêu tỷ trọng lĩnh vực bị so nhầm với tỷ lệ số đô thị thuộc cụm. Tham chiếu fact đã có ID/kiểu được kiểm tra theo mâu thuẫn ngữ cảnh trực tiếp, không suy đoán lại loại chỉ số từ một từ “Cụm” nằm trước đó. Chấp nhận khoảng trắng quanh ID và các alias `.value`/`.display` hoặc tiền tố `verified_facts.` **chỉ nếu** chúng phân giải tới một ID facts đã biết; không thực thi đường dẫn/biểu thức. Mã cụm sai của đúng đô thị, tráo matching/Top N và fact lạ vẫn bị từ chối.

Nếu sau khi sửa vẫn có lỗi, response có thêm `validation` chứa đường dẫn trường, rule và expected/observed khi xác định được. Thông báo hiển thị trực tiếp trường và hai giá trị này, không còn chỉ có câu lỗi chung. Không đưa toàn bộ báo cáo vào response lỗi. Khi thử lại cần để backend reload/khởi động lại và tạo báo cáo mới; kiểm tra `validator_version` để xác nhận đang chạy code mới.

Gemini ưu tiên diễn giải, không tự chép KPI. Khi cần số trong câu, dùng tham chiếu như `{{matching.city_count}}`, `{{top.city_count}}`, `{{matching.mean_sector_share_percent}}`, `{{dataset.year}}` hoặc `{{cities.<city_id>.rank}}`. Backend kiểm tra ID fact và phạm vi/ngữ cảnh, rồi gắn số cùng đơn vị từ Python vào văn bản. Không thực thi biểu thức và không cho Gemini trả lại/ghi đè `verified_facts`. Frontend hiển thị thêm bảng facts do Python gắn và thông số của từng đô thị minh họa, độc lập với phần diễn giải.

Nếu Gemini viết số trực tiếp, câu cần có ngữ cảnh nhận diện được: năm, cụm, thứ hạng của đúng đô thị, số đô thị/quốc gia trong matching/top, tỷ trọng trung bình hoặc tỷ trọng của đúng đô thị. Số trần mơ hồ và số liệu thị trường không có nguồn bị từ chối, có thể sửa bằng tham chiếu fact cụ thể. Số lượng/mã/năm/thứ hạng phải khớp chính xác; tỷ lệ, GHG và chênh lệch dùng `Decimal` + `ROUND_HALF_UP` theo độ chính xác hiển thị, tối đa hai chữ số. Hỗ trợ dấu phẩy/chấm thập phân và nhóm hàng nghìn theo loại số; sau khi xác minh, giá trị hiển thị lấy lại từ Python, ví dụ `47,1%` hợp lệ được gắn thành `47,06%` từ fact, không phải tự thêm độ chính xác của Gemini.

Response báo cáo bổ sung `verified_facts` và `numeric_references` (đường dẫn trường → ID fact) để truy nguồn. Log sai lệch có `field_path`, `rule`, `fact_id`, `scope`, `expected`, `observed`, `source` khi xác định được. Chỉ ghi số nhận được đã parse có độ dài giới hạn; không ghi cả câu/báo cáo, key, header hoặc ID fact lạ do mô hình tạo.

Lỗi thiết kế đã tái hiện offline của bộ kiểm tra cũ: các giá trị 40 (matching), 10 (Top N), 2024 (năm), 3 (K) cùng nằm trong một tập số cho phép, nên có thể chấp nhận “Top N có 40 đô thị”, “toàn bộ tập phù hợp có 10 đô thị”, “năm 3”. Bộ kiểm tra mới từ chối chúng theo đúng fact ngữ cảnh, không nới whitelist. Không có bản báo cáo/log chi tiết của lần Gemini thật bị từ chối nên không suy đoán token thực tế đã gây lỗi. Phần ngữ nghĩa tự do vẫn cần người dùng kiểm chứng; validator không phải một hệ thống kiểm chứng mọi nhận định thương mại bằng ngôn ngữ tự nhiên.

`POST /api/market/report` có chẩn đoán riêng; các API parse/search và Explorer khác giữ nguyên luồng. Log ra terminal Uvicorn với tiền tố `market_report`, gồm `request_id`, `stage`, `attempt`, loại exception và mã lỗi. Với lỗi schema chỉ log tên trường/rule đã lọc. Sự kiện `received` ghi `raw_word_count` của từng lượt nhận JSON trước validation; `completed` ghi `word_count` sau chuẩn hóa tiếng Việt cùng `within_word_target`. Không log nội dung báo cáo, key, header xác thực, nội dung yêu cầu/phản hồi hoặc chuỗi exception chứa dữ liệu provider. Không tự tạo file log.

**300–450 từ chỉ là mục tiêu hướng dẫn**, không phải điều kiện trả HTTP 200. Báo cáo hợp lệ ngoài khoảng vẫn được giữ nguyên nội dung và trả frontend, không tự cắt hoặc thêm chữ, không gọi Gemini lần hai chỉ vì số từ. Cách đếm dùng `split()` theo khoảng trắng trong các trường văn bản đã định nghĩa; tính cả văn bản so sánh đô thị và các mục thông tin bổ sung, không tính tên trường, mã đô thị trong `city_id` hay metadata. Đây là chỉ số biên tập, không phải phân tách từ tiếng Việt theo ngôn ngữ học.

Phân loại response:

| Mã lỗi | HTTP | Ý nghĩa |
| --- | --- | --- |
| `gemini_http` | 429/502/503 | HTTP từ provider; `provider_status` giữ mã gốc 429, 500, 502, 503… |
| `gemini_connection` | 503 | Lỗi kết nối |
| `gemini_timeout` | 504 | Hết thời gian chờ |
| `gemini_json` | 502 | Không parse được JSON ở lớp HTTP hoặc JSON nội dung Gemini |
| `gemini_response` | 502 | Không có nội dung báo cáo dùng được |
| `gemini_config` | 503 | Chưa đặt key backend |
| `report_schema` | 502 | Sai JSON object/schema/Pydantic hoặc mục rỗng |
| `report_numbers` / `report_city` | 502 | Số không khớp dữ liệu hoặc mã đô thị ngoài đầu vào |
| `report_data` | 422 | Không có kết quả/dữ liệu chưa hợp lệ |
| `report_internal` | 500 | Lỗi logic Python khác, log có vị trí file/hàm/dòng nhưng không có giá trị dữ liệu |

Lỗi trả `detail` dạng chuỗi để giao diện cũ hiển thị, kèm `error_code`, `request_id` và header `X-Request-ID`. Khi thành công, `diagnostics` gồm `request_id`, `correction_attempted`, `word_count`, `within_word_target`, `word_target: {min: 300, max: 450, required: false}` và `attempt_word_counts` (số từ thô từng lượt, số từ sau chuẩn hóa nếu lượt đó được chấp nhận). Header `X-Request-ID` dùng để đối chiếu log. `report_length` đã được bỏ khỏi điều kiện từ chối; lỗi `report_numbers` là vấn đề độc lập và vẫn bị chặn.

Các lỗi validation từng tái hiện được khi debug offline: số `47,1%` bị từ chối dù là làm tròn hợp lệ của trung bình thật `47,06%`; số thứ tự danh sách bị nhận như số liệu. Backend nay đối chiếu fact đúng ngữ cảnh ở độ chính xác được hiển thị, sau đó gắn giá trị Python chuẩn; không làm tròn số lượng đô thị để cho khớp. Các tỷ lệ theo cụm được Python tính sẵn cho Gemini. Đây là lỗi đã xác nhận bằng dữ liệu/mocks, **chưa phải bằng chứng về nguyên nhân lần gọi Gemini thật đã trả 503** vì trước đó không có log phân loại.

Nếu JSON sai schema, mục bắt buộc rỗng, số liệu không khớp hoặc mã đô thị không thuộc đầu vào, backend vẫn yêu cầu Gemini sửa **tối đa một lượt**, rồi chạy lại toàn bộ validation trên cùng dữ liệu gốc; không lấy bản nháp lỗi làm nguồn số liệu. Độ dài không kích hoạt nhánh sửa. Không có báo cáo giả thay thế. Lỗi HTTP, kết nối hoặc parse JSON không kích hoạt lượt sửa; đường báo cáo dùng `retries=0` ở transport để không có các lần HTTP retry ngầm. Một lần nhấn tạo báo cáo hợp lệ chỉ gọi Gemini một lần dù ngoài mục tiêu số từ; tối đa hai lần chỉ khi cần sửa lỗi cấu trúc/dữ liệu.

Để thử lại Gemini thật đúng một lần trên localhost:

1. Nếu backend cũ chưa tự reload, dừng riêng terminal backend, giữ nguyên môi trường có `GEMINI_API_KEY`, chạy `python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000 --log-level info`. Không in key ra terminal.
2. Tải lại `http://127.0.0.1:5173`, mở Market Explorer. Ưu tiên nhập lại nguyên văn yêu cầu và bộ lọc từng gây lỗi; không nhấn phân tích yêu cầu nếu muốn tránh một cuộc gọi Gemini bổ sung. Có thể nhập bộ lọc thủ công mẫu **Công nghiệp, Japan, tối thiểu 30%, GHG lĩnh vực giảm dần, Top 10** rồi xác nhận tìm kiếm. Bước tìm kiếm này không gọi Gemini.
3. Mở DevTools → Network, nhấn **Tạo báo cáo thị trường bằng Gemini** đúng một lần và chờ hoàn tất (có thể có một lượt sửa có kiểm soát).
4. Nếu thất bại, xem `error_code`, `request_id`, `provider_status` nếu có trong response và tìm cùng `request_id` trong terminal. Chỉ cần chia sẻ các trường chẩn đoán này cùng dòng log `market_report` tương ứng; không chia sẻ key, headers, prompt hay toàn bộ phản hồi Gemini.

Kiểm thử tự động dùng mock ở lớp `urlopen` để kiểm tra cả exception chain HTTP/timeout/JSON và không gọi Gemini thật. Các kiểm thử đi qua giá trị giả nhạy cảm để xác nhận chúng không xuất hiện trong log/response lỗi. Kết quả mock không thay thế việc kiểm tra lại provider thật.

Chọn **Market Explorer** trong sidebar. Luồng sử dụng:

1. Nhập yêu cầu tiếng Việt hoặc nhấn **Dùng yêu cầu mẫu**, sau đó **Phân tích yêu cầu**. Gemini chỉ đề xuất JSON tiêu chí, không tự chạy tìm kiếm. Công nghệ bất kỳ có thể được ánh xạ sơ bộ sang một lĩnh vực EDGAR; người dùng cần kiểm tra cách hiểu này.
2. Kiểm tra/sửa lĩnh vực, một hoặc nhiều quốc gia, cụm, ngưỡng tỷ trọng tối thiểu/tối đa, tiêu chí xếp hạng, thứ tự và Top N (1–100). Nhấn **Xác nhận bộ lọc và tìm kiếm**. Có thể dùng bộ lọc thủ công khi chưa đặt API key. Không chọn riêng quốc gia nào nghĩa là toàn bộ quốc gia; ngưỡng trống nghĩa là không áp dụng ngưỡng. Mặc định công khai ban đầu: Công nghiệp, GHG lĩnh vực giảm dần, Top 10.
3. Xem KPI **toàn bộ tập phù hợp**, thống kê riêng **Top N**, bảng, bản đồ và biểu đồ. Nhấn tiêu đề cột số liệu để xếp lại toàn bộ tập trước khi lấy Top N. **Mở hồ sơ** hoặc nhấn điểm bản đồ để sang City Explorer. CSV hỗ trợ Top N và toàn bộ tập phù hợp, theo cùng bộ lọc/thứ tự đã chạy.
4. Nhấn **Tạo báo cáo thị trường bằng Gemini** sau khi có kết quả. Báo cáo hướng tới 300–450 từ, dùng thống kê Python và các đô thị đầu/giữa/cuối Top N để minh họa, không coi đây là mẫu đại diện thống kê. Backend tính lại từ bộ lọc, không tin số liệu gửi lên từ trình duyệt; kiểm tra schema, mục bắt buộc, mã đô thị tham chiếu và các giá trị số trong văn bản. Độ dài chỉ được thống kê, không quyết định chấp nhận báo cáo. Nội dung AI vẫn cần kiểm chứng về ngữ nghĩa.

Market Explorer dùng tỷ trọng gốc của lĩnh vực được chọn, **không dùng điều kiện dominant sector**. Ngưỡng và việc xếp hạng tính trên giá trị đầy đủ độ chính xác; chỉ làm tròn để hiển thị và gửi Gemini. Không dùng danh mục `green_solutions.json`. Các bộ lọc sidebar không áp dụng cho Market Explorer. Nếu chỉnh tiêu chí sau khi tìm kiếm, giao diện đánh dấu kết quả cũ và yêu cầu tìm kiếm lại trước khi xuất hoặc tạo báo cáo.

API mới (POST, JSON):

- `/api/market/parse`: `{ "text": "..." }` → tiêu chí sơ bộ, cách hiểu và các giả định/điều kiện chưa hỗ trợ.
- `/api/market/search`: query gồm `sector`, `countries` (mảng tên từ `/api/countries`), `cluster_id` hoặc null, `min_sector_share_percent`/`max_sector_share_percent` hoặc null, `sort_by`, `sort_order`, `limit`.
- `/api/market/export`: `{ "query": {...}, "scope": "top" }` hoặc scope `matching` → nội dung CSV và tên file, trình duyệt tải xuống; không tạo file trên server.
- `/api/market/report`: `{ "query": {...}, "business_request": "..." }` → báo cáo tiếng Việt và các đô thị minh họa từ dữ liệu thật.

`sort_by` cho phép `sector_share`, `sector_emissions`, `total_ghg`; thứ tự `asc`/`desc`. Quốc gia được chuẩn hóa theo danh sách thật (có một số tên Việt thông dụng). Không chấp nhận trường ngoài schema, SQL/code, nước không tồn tại, tỷ trọng ngoài 0–100 hoặc Top N ngoài 1–100. Khi không có kết quả, KPI số lượng bằng 0, trung bình để trống và không gọi Gemini tạo báo cáo.

Chưa có bảng quốc gia–khu vực đã kiểm tra nên không hỗ trợ lọc châu lục/khu vực, không để Gemini tự mở rộng chúng thành danh sách quốc gia. Với ngưỡng trong yêu cầu tự nhiên, nên ghi rõ `%` hoặc `phần trăm` (hỗ trợ khoảng như `20–60%`). Backend bỏ ngưỡng Gemini đề xuất nếu không xác nhận được con số từ yêu cầu, kèm thông báo để nhập lại. Các điều kiện khác không có dữ liệu được nêu rõ; người dùng phải chấp nhận bỏ qua trước khi tìm kiếm.

Ví dụ đã kiểm tra: Nhật Bản, Công nghiệp từ 30%, GHG Công nghiệp giảm dần, Top 10 → **40 đô thị phù hợp**, phân bố cụm **0: 9, 1: 22, 2: 9**; bảng chỉ hiển thị Top 10. Bản đồ hiển thị toàn bộ tập phù hợp khi có tối đa 5.000 tọa độ hợp lệ; vượt mức này lấy mẫu đều có ghi rõ. CSV toàn bộ vẫn chứa đủ các dòng phù hợp.

Kiểm tra tại localhost theo mục 3–4 phía dưới; đặt `GEMINI_API_KEY` ở backend để phân tích yêu cầu/tạo báo cáo thật. Chạy `python -m unittest discover -s tests -v` và `npm run build` trong `web` để kiểm thử; Gemini được mock, không gọi API thật. API key không nằm trong frontend.

Giới hạn: dữ liệu EDGAR năm 2024, đơn vị GHG gốc chưa xác minh; không chuyển đổi sang tCO₂e. Thứ tự phát thải không phải thứ tự cơ hội kinh doanh; không tạo điểm tiềm năng, dự báo doanh số hay xác nhận nhu cầu mua. Cần bổ sung hạ tầng, ngành hoạt động thực tế, chính sách, ngân sách, đơn vị mua sắm và nhu cầu thực tế. Phiên nghiên cứu chỉ lưu trong bộ nhớ trang; khởi động lại backend nếu thay dữ liệu để làm mới cache. K-Means K=3, dữ liệu và các trang cũ được giữ nguyên.

## City Explorer — Giai đoạn 2

Chọn **Tra cứu đô thị** trong sidebar. Tìm theo tên và lọc quốc gia trong sidebar; chọn kết quả để xem mã/tên/quốc gia, cụm, tổng GHG và phát thải của từng lĩnh vực. Biểu đồ đối chiếu đô thị với **tâm K-Means đã lưu**. Bảng cụm hiển thị riêng trung bình, trung vị, độ lệch chuẩn tổng thể và IQR. Ba lĩnh vực có chênh lệch tuyệt đối lớn nhất với tâm được tô nền, không dùng ngưỡng để kết luận bất thường.

Phần khoảng cách mặc định chỉ hiển thị khoảng cách đô thị, trung vị cụm và phân vị thực nghiệm. Mở **Xem thống kê mở rộng của cụm** để xem các mốc Q1/Q3/P90/P95 và bảng thống kê lĩnh vực. Bảng phát thải hiển thị từng lĩnh vực thành một khối trên mobile; chênh lệch có dấu +/−, hai chữ số thập phân và đơn vị **điểm phần trăm**. Khi in/lưu PDF, bố cục riêng cho City Explorer bỏ sidebar và phần tìm kiếm, cho bảng vừa khổ giấy để không cắt cột chênh lệch.

Báo cáo đô thị dùng tên Nông nghiệp, Năng lượng, Công nghiệp, Quốc tế, Dân cư, Giao thông, Chất thải. Backend bổ sung nhãn tiếng Việt vào đầu vào Gemini và thay tên biến lĩnh vực còn sót trong các trường văn bản trước khi kiểm tra độ dài. Prompt chỉ cho phép diễn giải mô tả, không coi chênh lệch là "đáng kể" hoặc "có ý nghĩa thống kê" khi chưa có kiểm định. Các thay đổi ngôn ngữ này chỉ áp dụng cho báo cáo đô thị.

`GET /api/cities/{city_id}` giữ nguyên các trường cũ, bổ sung `analysis`: tỷ trọng gốc đủ độ chính xác, chênh lệch so với tâm, các ngành nổi bật và vị trí khoảng cách trong cùng cụm. Trường cũ `comparison_percentage_points` vẫn là chênh lệch so với trung bình; trường mới `analysis.comparison_to_centroid_pp` là chênh lệch so với tâm. Không đánh đồng hai giá trị.

Phân vị khoảng cách dùng công thức `100 × count(distance <= city_distance) / số đô thị cùng cụm`, gồm chính đô thị và các khoảng cách bằng nhau. Đây là hàm phân phối thực nghiệm, không phải xác suất, kiểm định thống kê hoặc kết luận ngoại lệ. Phân vị cao hơn mô tả đô thị xa tâm hơn nhiều thành viên. Các mốc Q1/trung vị/Q3/P90/P95 được tính trên toàn cụm, độc lập với bộ lọc tra cứu.

`POST /api/cities/{city_id}/interpret` tạo báo cáo Gemini bằng tiếng Việt 250–400 từ. Backend kiểm tra tổng phát thải, tỷ trọng, hình học K-Means; tính các chênh lệch trước khi làm tròn. Dữ liệu gửi Gemini được làm tròn đến 2 chữ số cho tỷ trọng/chênh lệch/phân vị và 4 chữ số cho khoảng cách. Không đọc `green_solutions.json`, không đề xuất công nghệ và không chuyển đổi đơn vị EDGAR. Báo cáo dùng cùng hợp đồng JSON với Cluster Explorer; City Explorer giữ kiểm tra độ dài 250–400 từ hiện có. Giao diện hiển thị bốn phần diễn giải thay vì JSON thô.

Để kiểm tra, khởi động backend và frontend theo mục 3–4 bên dưới. Tìm **Nagoya — Japan (5213, cụm 2)**, **Shanghai — China (11345, cụm 1)** và **Los Angeles — United States (2007, cụm 0)**. Với backend đã có `GEMINI_API_KEY`, nhấn **Phân tích bằng Gemini** để gọi API thật. Kiểm thử tự động `python -m unittest discover -s tests -v` dùng mock, không gọi Gemini thật.

Giới hạn: đơn vị GHG gốc chưa được xác minh; K=3 và dữ liệu năm 2024 được giữ nguyên. Python kiểm tra số liệu đầu vào và cấu trúc/độ dài đầu ra; ý nghĩa nội dung AI vẫn cần người dùng đối chiếu. Báo cáo chỉ lưu trong bộ nhớ trang; chuyển đô thị bỏ qua yêu cầu đang chờ ở trình duyệt, không đảm bảo hủy yêu cầu đã tới Gemini. Nếu thay dữ liệu cần khởi động lại backend để làm mới cache.

## Cluster Explorer — Giai đoạn 1

Trong sidebar, chọn **Tổng quan**, kéo xuống **Khám phá các cụm đô thị**, rồi chọn Cụm 0, 1 hoặc 2. Khu vực này hợp nhất thẻ “Ba nhóm đô thị”, biểu đồ cơ cấu cụm của Overview và Cluster Explorer thành một biểu đồ cột chồng 100% tại tâm K-Means, hai KPI quy mô của cụm đang chọn, ba lĩnh vực có tỷ trọng cao nhất tại tâm và phần **Gemini diễn giải cụm**. Không hiển thị bảng thống kê chuyên sâu hoặc chỉ số khoảng cách.

Bản đồ và KPI số đô thị ở đầu Tổng quan vẫn áp dụng bộ lọc quốc gia, lĩnh vực và cụm. Khu vực khám phá cụm dùng toàn bộ 11.422 đô thị, không áp dụng các bộ lọc này; tỷ lệ cụm có mẫu số là toàn bộ dữ liệu. Nhãn phạm vi hiển thị ở cả hai khu vực. Bộ chọn Cụm 0/1/2 chỉ thay đổi hồ sơ và báo cáo đang xem. Sidebar không còn mục Cluster Explorer hoặc Giải pháp công nghệ xanh cũ; code và API cũ được giữ lại.

Toàn bộ thống kê trung bình/trung vị, độ lệch chuẩn, IQR, khoảng cách và chênh lệch vẫn được backend tính và trả trong các endpoint hiện có, phục vụ Gemini, City Explorer và các chức năng liên quan. Overview tái sử dụng component `ClusterExplorer` và các API hiện có; biểu đồ cột chồng dùng `basis="centroid"`. Backend không thay đổi.

Tâm đọc từ `reports/cluster_analysis/cluster_centroids_2024.csv`; kiểm tra với metadata và mã huấn luyện cho thấy mô hình dùng tỷ trọng gốc 0–1, không scaling/PCA. Backend kiểm tra lại khoảng cách của đủ 11.422 đô thị, không huấn luyện lại. Tâm có thể lệch nhẹ với trung bình tính lại theo nhãn cuối cùng. Độ lệch chuẩn/IQR tỷ trọng có đơn vị điểm phần trăm; khoảng cách không có đơn vị. Phân vị nội suy tuyến tính, độ lệch chuẩn dùng `ddof=0`.

API mới:

Báo cáo Gemini hướng tới 250–400 từ (đếm theo khoảng trắng), hiển thị bốn phần: Đặc điểm nổi bật; So sánh các cụm; Độ phân tán và tính đại diện; Hạn chế và hướng nghiên cứu. Backend chọn ba lĩnh vực nổi bật và ba khác biệt từ thống kê thật, làm tròn bản dữ liệu gửi Gemini đến hai chữ số cho tỷ trọng/điểm phần trăm và bốn chữ số cho khoảng cách, giữ nguyên thống kê gốc. JSON vẫn dùng các trường hiện có, giới hạn 2–3 mục so sánh và 2–3 câu hỏi nghiên cứu. Phản hồi sai cấu trúc, mục rỗng hoặc vượt giới hạn ký tự của schema vẫn bị từ chối; không có báo cáo giả thay thế. Riêng báo cáo cụm hợp lệ nhưng ngoài mục tiêu số từ vẫn được trả về, không tự gọi thêm Gemini để sửa độ dài. Prompt yêu cầu các câu hỏi ngoài phạm vi năm 2024 nêu rõ dữ liệu cần bổ sung và cấm suy luận nguyên nhân, chất lượng môi trường, thị trường hoặc khả thi công nghệ từ tỷ trọng.

- `GET /api/cluster-explorer`: thống kê Python của cả ba cụm.
- `GET /api/cluster-explorer/{cluster_id}/preview`: dữ liệu đầu vào Gemini, không gọi API ngoài.
- `POST /api/cluster-explorer/{cluster_id}/interpret`: diễn giải bằng Gemini, JSON gồm `summary`, `comparisons`, `dispersion_and_representativeness`, `research_questions`, `limitations`.

Nút **Gemini diễn giải cụm** gọi API thật khi backend có `GEMINI_API_KEY` (cách đặt key ở mục 5). Báo cáo tập trung diễn giải cụm, không yêu cầu đề xuất công nghệ xanh. API key chỉ ở backend. Phản hồi Gemini được kiểm tra cấu trúc; nội dung AI vẫn cần đối chiếu thống kê. Báo cáo được giữ trong bộ nhớ trang theo từng cụm; chuyển cụm sẽ bỏ qua phản hồi cũ đang chờ, nhưng không đảm bảo hủy yêu cầu đã gửi tới nhà cung cấp.

Nếu diễn giải cụm lỗi, thông báo trên web có mã lỗi và mã yêu cầu. Backend ghi log `cluster_report` theo mã này, phân biệt `gemini_config`, `gemini_http` (kèm `provider_status`), `gemini_timeout`, `gemini_connection`, `gemini_json`, `gemini_response`, `report_schema`, `report_data` và `cluster_internal`. Schema ghi tên trường/quy tắc, không ghi nội dung báo cáo, key, URL yêu cầu hay header. Thành công trả thêm `diagnostics` gồm `request_id`, `word_count`, `within_word_target`, `word_target: {min: 250, max: 400, required: false}`. Báo cáo ngoài mục tiêu chỉ ghi log WARNING với `event: accepted` và số từ; không trả lỗi `report_length`. Nếu vẫn thấy lỗi độ dài cũ, khởi động lại FastAPI trong terminal đã cấu hình key rồi tải lại web.

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
2. **Tra cứu đô thị / City Explorer**: tìm kiếm, phân trang, xem phát thải 7 lĩnh vực, so sánh với tâm và thống kê cụm, phân vị khoảng cách, diễn giải hồ sơ bằng Gemini.
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
