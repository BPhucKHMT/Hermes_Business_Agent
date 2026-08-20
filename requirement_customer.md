# Yêu cầu khách hàng

Tài liệu này là bản yêu cầu nghiệp vụ tiếng Việt, cập nhật theo tài liệu thiết kế toàn diện v2 (`docs/Project_Hermes_v2_Build_Doc.docx` - Chuẩn bị bởi Klaus, Tháng 8/2026), thay thế cho bản tóm tắt 2 tuần ban đầu để định hướng toàn bộ quá trình xây dựng hệ thống AI Chief of Staff (Chánh văn phòng AI) và đội ngũ Sub-Agent.

Phạm vi giữ nguyên tắc: tập trung vào mục tiêu kinh doanh, hành vi sản phẩm, 3 workspace nghiệp vụ, 4 mức tự chủ, lớp kiểm chứng bằng chứng, động cơ chủ động, ràng buộc an toàn và tiêu chí nghiệm thu.

## Mục tiêu

Xây dựng **Hermes** thành Chánh văn phòng AI (AI Chief of Staff) nội bộ hai chiều (two-way proactive), chạy trên nền tảng mã nguồn mở Hermes Agent của Nous Research, đứng giữa Klaus (và toàn đội ngũ) với mọi hoạt động vận hành:

- **Giảm tải danh sách công việc cá nhân của Klaus:** Hermes chủ động theo dõi, nhắc nhở, đàm phán trong giới hạn, giải quyết công việc lặp lại hoặc tự động biến chúng thành các hành động theo dõi (follow-ups) có lịch trình rõ ràng.
- **Phục vụ 3 mảng kinh doanh (Workspaces) độc lập và cách ly tuyệt đối:**
  1. **Protein Bar (Thảo Điền, TP.HCM):** F&B ra mắt với mốc cứng khai trương trước **08/12/2026** (kế hoạch 16 tuần, thử nghiệm nhà cung cấp, đàm phán mặt bằng/chủ nhà, giấy phép ĐKKD/ATVSTP/PCCC). Đây là workspace ưu tiên cao nhất, làm nơi thử nghiệm đầu tiên cho mọi cơ chế.
  2. **Client Projects (Dự án khách hàng):** Giao hàng cho khách bên ngoài (vd: dự án xây dựng lại app Train With Jordan - TWJ), theo dõi chat nhóm dev, bản tin cập nhật cho khách, báo giá và quản lý cam kết.
  3. **TITAN AI:** Nền tảng marketing intelligence và agency nội dung/SMM, quản lý đội ngũ VA/Editor, pipeline đối tác/nhà đầu tư (TikTutors), sáng tạo nội dung, xuất hóa đơn và thu hồi công nợ.
- **Xử lý hộp thư và hội thoại chủ động:** Phân loại ≥ 80% email thường nhật, soạn sẵn bản nháp đúng giọng văn của Klaus, theo dõi các luồng hội thoại bị đình trệ (chủ nhà, nhà cung cấp, khách hàng).
- **Báo cáo tiến độ tự động 100%:** Tạo báo cáo tuần cho từng mảng kinh doanh vào 17:00 thứ Sáu mà không cần viết tay, trích xuất chính xác từ sự kiện thực tế trong chat và email.
- **Kế toán & Hóa đơn an toàn:** Lập hóa đơn, theo dõi công nợ theo bậc thang nhắc nợ, ghi nhận chi phí qua ảnh chụp/email; tuyệt đối không tự ý chuyển tiền (Tier 3).
- **Hỗ trợ điều hành chuẩn phong cách ADHD:** Mỗi ngày chỉ tập trung tối đa 3 việc quan trọng nhất ("Top 3 Today"), gắn kèm hành động nhỏ cụ thể 2–15 phút, bản tin sáng 07:30 ICT và tổng kết tối 18:30 ICT, nhắc lại việc bị dừng mà không gây cảm giác trách móc.
- **Kiểm chứng bằng chứng máy (Machine-Verifiable Evidence):** Mọi công việc "đã xong" bắt buộc phải kèm bằng chứng được xác thực độc lập, không chấp nhận việc agent tự tuyên bố hoàn thành.

## Đối tượng sử dụng

- **Klaus (Founder / CEO):** Người dùng chính; nhận bản tin sáng, duyệt các hành động Tier 2 (email đối tác, hóa đơn, bài đăng, đặt chỗ) qua Telegram 1 chạm, điều khiển toàn bộ hệ thống qua chat tự nhiên.
- **Nhân sự nội bộ / VAs / Editors / Dev team:** Nhận giao việc (task briefs), nhận nhắc nhở tiến độ, báo cáo tình trạng công việc qua Telegram/Slack.
- **Đối tác / Nhà cung cấp / Khách hàng:** Giao tiếp qua email, Telegram, WhatsApp với các phản hồi được Hermes soạn thảo đúng văn phong (hoặc gửi tự động khi đã tốt nghiệp mức tự chủ).
- **Chủ nhà (Landlord - Protein Bar):** Luồng đàm phán đặc biệt quan trọng, vĩnh viễn ở chế độ "Chỉ soạn nháp" (Draft-only), không bao giờ gửi tự động.
- **Người vận hành kho tri thức & Kỹ sư triển khai:** Cập nhật tài liệu, theo dõi bảng điểm độ tin cậy (reliability scoreboard), audit log và ngân sách chi phí.

## Yêu cầu chức năng

### Cách ly Workspace và Định tuyến (Workspace Isolation & Routing)

- **REQ-WORKSPACE-01:** Hệ thống phải vận hành dưới mô hình **MỘT agent duy nhất phục vụ 3 workspace** (Protein Bar, Client Projects, TITAN AI) cùng 2 pseudo-workspace (HQ cá nhân và Unsorted), áp dụng 5 lớp cách ly cưỡng chế trong code:
  1. *Binding trước khi xử lý:* Kênh chat, nhóm Telegram, nhãn email và danh bạ được gắn cứng vào đúng 1 workspace.
  2. *Hỏi thay vì đoán (Ask, don't guess):* Khi độ tin cậy định tuyến thấp, bot phải hỏi 1 câu ngắn kèm gợi ý mặc định; cấm tự ý đoán mò.
  3. *Truy xuất giới hạn (Scoped retrieval):* Sub-agent chỉ được phép đọc tài liệu, danh bạ và luồng của đúng workspace đang thực thi; chặn truy xuất chéo.
  4. *Dữ liệu có cấu trúc:* Mọi task, thread, contact, ledger row đều mang trường `workspace`.
  5. *Kiểm toán & kiểm tra:* Vượt qua 20/20 câu hỏi bẫy trộn ngữ cảnh (context-bleed test).
- **REQ-WORKSPACE-02:** Thứ tự ưu tiên xử lý và triển khai phải tuân thủ: 1) Protein Bar (mốc 08/12/2026) ➔ 2) Client Projects ➔ 3) TITAN AI.

### Tri thức công ty và Bộ nhớ 5 lớp (Knowledge & Layered Memory)

- **REQ-KB-01:** Hệ thống phải trả lời câu hỏi dựa trên tài liệu nội bộ, SOP, thông tin sản phẩm, giá cả và kế hoạch tổng thể của từng workspace.
- **REQ-KB-02:** Câu trả lời phải kèm citation (nguồn dẫn, trang, URL) để người dùng kiểm tra nguồn gốc.
- **REQ-KB-03:** Quá trình ingestion phải chạy lại được khi tài liệu thay đổi (rerunnable).
- **REQ-KB-04:** Kho tri thức phải phản ánh dữ liệu mới nhất sau khi ingestion thành công.
- **REQ-MEMORY-01:** Hệ thống phải duy trì bộ nhớ 5 lớp: 1) Bộ nhớ nền tảng (MEMORY.md/USER.md), 2) State DB (9 bảng), 3) Kho tài liệu file theo workspace, 4) Memory Vault Markdown chuẩn Obsidian (đồng bộ Drive + Git), 5) Kho văn phong và sở thích (lưu diff sửa đổi của Klaus để học tập).
- **REQ-MEMORY-02:** Hỗ trợ truy vấn liên tục từ trạng thái tĩnh ("Where were we on X") mà không cần dựa vào lịch sử chat tạm thời.

### Nghiên cứu và Bộ công cụ chuyên gia (Research & Specialist Fleet)

- **REQ-RESEARCH-01:** Hệ thống phải thực hiện web research theo yêu cầu trên cả web mở và mạng xã hội (TikTok, Instagram, Facebook groups, LinkedIn).
- **REQ-RESEARCH-02:** Hệ thống phải hỗ trợ quét đối thủ (competitor scan) và tìm kiếm nhà cung cấp/địa điểm kèm bảng báo giá so sánh.
- **REQ-RESEARCH-03:** Kết quả nghiên cứu phải gồm bản tóm tắt có cấu trúc, phân tích khoảng trống dữ liệu và danh sách nguồn rõ ràng.
- **REQ-RESEARCH-04:** Tự động xây dựng và duy trì các "Expertise Packs" (bộ cẩm nang chuyên gia: offer/creative Hormozi, phễu marketing, đàm phán BATNA) và bắt buộc tải cẩm nang trước khi làm việc chuyên môn.

### Sản phẩm đầu ra (Deliverables Studio & Decks)

- **REQ-DECK-01:** Hệ thống phải nhận chủ đề, kết quả nghiên cứu hoặc báo cáo làm đầu vào.
- **REQ-DECK-02:** Hệ thống phải tạo bản nháp presentation deck, tài liệu một trang, bảng tính tài chính hoặc hình ảnh/video qua Deliverables Studio:
  - Dùng Canva MCP cho slide/tài liệu đối ngoại chuẩn nhận diện thương hiệu (brand kit).
  - Dùng Higgsfield cho hình ảnh/video AI concept nội dung.
  - Dùng Google Slides/Docs/Sheets API hoặc python-pptx/xlsx/pdf cho báo cáo/bảng tính.
- **REQ-DECK-03:** Mọi số liệu trong deck/báo cáo phải giữ liên kết nguồn gốc để kiểm tra.

### Động cơ chủ động và Hỗ trợ điều hành (Proactive Engine & ADHD Support)

- **REQ-PROACTIVE-01:** Tự động phát hiện luồng bị đình trệ:
  - *Waiting-on-them:* Tin nhắn gửi đi quá 3 ngày làm việc chưa có hồi âm ➔ Soạn nhắc nhở/thực hiện bậc thang leo thang.
  - *Waiting-on-us:* Tin nhắn/email đến chưa trả lời quá 24h ➔ Soạn sẵn nháp trình duyệt.
  - *Stalled tasks:* Công việc quá 3 ngày không chuyển biến ➔ Nhắc nhở người phụ trách.
  - *Date radar:* Cảnh báo hạn chót giấy phép, hợp đồng thuê, hóa đơn ở các mốc T-14, T-7, T-2 ngày kèm hành động cụ thể.
- **REQ-PROACTIVE-02:** Bản tin sáng (07:30 ICT) trên Telegram: Top 3 việc trong ngày (kèm ước tính thời gian 2–15 phút), lịch làm việc, việc đã xong đêm qua, các mục chờ duyệt 1 chạm. Tổng kết tối (18:30 ICT) và nhật ký ngày do Scribe phụ trách.
- **REQ-PROACTIVE-03:** Hỗ trợ ra lệnh tự động từ chat (Flow A): Cập nhật báo cáo tiến độ và thêm việc vào to-do list tuần sau chỉ từ 1 câu chat tự nhiên.

### Báo cáo và Vòng lặp tự sinh SOP (Reports & SOP Loop)

- **REQ-REPORT-01:** Tự động tổng hợp báo cáo tiến độ tuần cho từng workspace vào thứ Sáu lúc 17:00 ICT từ sự kiện chat, email, task và sổ cái.
- **REQ-SOP-01:** Hệ thống (SOP Writer) phải theo dõi audit log, phát hiện quy trình lặp lại (≥3 lần), tự động soạn thảo bản nháp SOP, trình Klaus duyệt và nạp vào ngữ cảnh tri thức để thực thi đồng nhất.

### Kế toán, Hóa đơn và Chi phí (AI Accountant)

- **REQ-INVOICE-01:** Lập bản nháp hóa đơn từ dữ liệu yêu cầu hoặc dịch vụ đã thực hiện.
- **REQ-INVOICE-02:** Hiển thị toàn bộ dữ liệu hóa đơn/thư từ để người dùng duyệt (Tier 2) trước khi tạo PDF và gửi qua Make.com.
- **REQ-INVOICE-03:** Quản lý bậc thang nhắc nợ tự động (+0d, +3d, +7d, +14d leo thang cho người).
- **REQ-INVOICE-04:** Phân loại chi phí từ hộp thư dùng chung theo thác nước: 1) Danh bạ nhà cung cấp ➔ 2) Tín hiệu nội dung/địa chỉ ➔ 3) Lịch sử ➔ 4) Nút bấm hỏi 1 chạm trên Telegram khi độ tin cậy thấp; tuyệt đối không tự đoán về tiền bạc.
- **REQ-INVOICE-05:** Mọi hành động chuyển tiền, thanh toán thực tế hoặc ký kết hợp đồng pháp lý vĩnh viễn thuộc **Tier 3 (Chỉ con người thực hiện)**; Hermes không bao giờ tự động chuyển tiền.

### Mức tự chủ và Phê duyệt (Autonomy Tiers)

- **REQ-AUTONOMY-01:** Hệ thống phải cưỡng chế 4 mức tự chủ trong code executor:
  - *Tier 0 (Âm thầm):* Gắn nhãn, nạp dữ liệu, cập nhật bộ nhớ nội bộ.
  - *Tier 1 (Làm & báo cáo):* Nhắc việc, cập nhật task board, soạn nháp nội bộ, bản tin sáng.
  - *Tier 2 (Soạn nháp & chờ duyệt):* Giao tiếp bên ngoài (email/WhatsApp khách, nhà cung cấp), xuất hóa đơn, lịch hẹn đối ngoại, đàm phán chủ nhà, xuất bản SOP.
  - *Tier 3 (Con người làm):* Thanh toán, ký kết, pháp lý, nhân sự.
- **REQ-AUTONOMY-02:** Cơ chế tốt nghiệp mức tự chủ (Trust Graduation): Một hạng mục Tier 2 chỉ được chuyển sang gửi tự động (Tier 1) khi đạt tỷ lệ duyệt không cần sửa ≥ 95% trên tối thiểu 10 lượt trong 2 tuần liên tiếp. Bất kỳ sự cố gửi sai nào sẽ bị giáng cấp về Tier 2 ngay lập tức.

### Kênh giao tiếp và Trợ lý du lịch

- **REQ-CHANNEL-01:** Telegram là cổng giao tiếp chính (DM và group theo workspace, hỗ trợ nút bấm duyệt, voice note).
- **REQ-CHANNEL-02:** Email/Gmail được giám sát liên tục, gắn nhãn phân loại và soạn sẵn phản hồi.
- **REQ-CHANNEL-03:** WhatsApp hỗ trợ cả kết nối trực tiếp (WABA) và pipeline nạp lịch sử xuất chat định kỳ an toàn.
- **REQ-CHANNEL-04:** Hỗ trợ kết nối Slack cho TITAN AI, Fireflies cho biên bản họp, Notion và Google Workspace.
- **REQ-TRAVEL-01:** Trợ lý du lịch (Travel Agent) lập kế hoạch chuyến đi theo mục tiêu: nghiên cứu chuyến bay, khách sạn, lịch trình F&B/đối tác, đề xuất 2–3 phương án kèm chi phí; sau khi duyệt mới đặt chỗ tự động và kiểm chứng bằng mã PNR.

## Yêu cầu phi chức năng

### Bảo mật, Riêng tư và An toàn

- **NFR-SEC-01:** Không đưa customer PII vào prompt gửi cho công cụ bên thứ ba ngoài stack đã duyệt.
- **NFR-SEC-02:** Không lưu trữ API key, token hoặc secret trong git; quản lý qua Azure Key Vault hoặc file `.env` được bảo vệ.
- **NFR-SEC-03:** Cung cấp nút ngắt khẩn cấp (Outbound Kill Switch) để dừng lập tức mọi tin nhắn/hành động gửi ra ngoài.
- **NFR-SEC-04:** Chỉ sử dụng các API chính thức (Telegram Bot, Gmail API, WhatsApp Cloud API); không dùng bot không chính thức (grey automation) trên số cá nhân để tránh nguy cơ bị khóa tài khoản.

### Lớp kiểm chứng độc lập (Verification Layer)

- **NFR-VERIFY-01:** Mọi hành động hoàn thành phải có bằng chứng độc lập (message ID, event ID, file URL, execution ID, PNR).
- **NFR-VERIFY-02:** Bộ kiểm chứng (Verifier) phải là code/script độc lập, đọc lại hệ thống đích để xác nhận; agent thực hiện không được tự chấm điểm công việc của mình.
- **NFR-VERIFY-03:** Quy tắc không bằng chứng = chưa hoàn thành (No evidence ➔ not done); thử lại 1 lần rồi chuyển cho người xử lý.
- **NFR-VERIFY-04:** Đối chiếu cuối ngày (End-of-day reconciliation) so khớp toàn bộ hành động đã thực hiện với hệ thống bên ngoài; kiểm tra ngẫu nhiên 10% công việc Tier 0/1 mỗi ngày.
- **NFR-VERIFY-05:** Mã định danh bất biến (Idempotency keys) trên mọi hành động để đảm bảo khi hệ thống restart không bao giờ gửi tin hay tạo đơn trùng lặp.

### Vận hành và Chi phí

- **NFR-OPS-01:** Hệ thống triển khai trên một máy ảo Azure VM duy nhất chạy nền tảng Hermes Agent với backend sandbox Docker.
- **NFR-OPS-02:** Tài liệu vận hành, README và bản đồ năng lực phải luôn phản ánh trung thực trạng thái thực tế của hệ thống.
- **NFR-COST-01:** Theo dõi chi phí token/credit hằng ngày (Azure, Claude, Make, Higgsfield); cảnh báo khi chạm 80% ngân sách tuần; định tuyến model rẻ cho các tác vụ phân loại/triage.

## Guardrails bắt buộc

1. **Một Agent, Ba Workspace:** Không triển khai 3 bot riêng; giữ 1 não bộ thống nhất với 5 tầng cách ly cưỡng chế trong code.
2. **Không tự ý chuyển tiền hoặc ký kết pháp lý:** Mọi hành động liên quan tiền, chuyển khoản, ngân hàng, hợp đồng, giấy phép thuộc Tier 3 — vĩnh viễn cần con người thực hiện.
3. **Thư từ với chủ nhà (Landlord) luôn chỉ soạn nháp:** Luồng đàm phán mặt bằng Thảo Điền không bao giờ được gửi tự động.
4. **Không có bằng chứng = Chưa xong:** Không chấp nhận câu trả lời "đã làm xong" nếu thiếu bằng chứng máy kiểm tra được.
5. **Hỏi thay vì đoán khi xử lý tiền bạc:** Phân loại chi phí dưới ngưỡng tin cậy bắt buộc phải hiển thị nút bấm hỏi người dùng 1 chạm; cấm đoán mò.
6. **Không lưu secret trong repository:** Toàn bộ khóa bí mật nằm ngoài git.
7. **Bảo toàn nguồn gốc và trích dẫn:** Mọi câu trả lời tri thức và báo cáo nghiên cứu phải kèm bằng chứng/citation.

## Tiêu chí nghiệm thu

- **AC-01 — Company Q&A:** Đặt câu hỏi về 3 workspace và nhận câu trả lời chính xác kèm citation nguồn từ tài liệu nội bộ.
- **AC-02 — Research & Expertise Packs:** Nghiên cứu thị trường/đối thủ trên web và social, xuất tóm tắt kèm nguồn và áp dụng đúng cẩm nang chuyên môn.
- **AC-03 — Deliverables Studio:** Một yêu cầu tạo ra bản nháp slide Canva, mô hình Google Sheets và visual Higgsfield đúng brand kit.
- **AC-04 — Flow A (Cập nhật từ chat):** Chat 1 câu "@hermes, tuần này nhà cung cấp không trả lời..." ➔ Báo cáo tuần cập nhật, to-do tuần sau được tạo, bản nháp nhắc nhở được chuẩn bị kèm nút duyệt.
- **AC-05 — Flow B (Xử lý hộp thư sáng):** Tự động gắn nhãn, digest email FYI, soạn sẵn phản hồi đúng giọng Klaus và đưa vào bản tin sáng.
- **AC-06 — Flow C (Đàm phán chủ nhà):** Nhận email chủ nhà ➔ So sánh với các mốc quy định mặt bằng ➔ Soạn tóm tắt đàm phán và bản nháp phản hồi chờ duyệt.
- **AC-07 — Flow D (Báo cáo tuần tự động):** Tự động tổng hợp báo cáo tuần lúc 17:00 thứ Sáu cho cả 3 workspace từ dữ liệu thật; Klaus sửa ≤ 1 dòng.
- **AC-08 — Flow E (Tự sinh SOP):** Phát hiện quy trình lặp lại ≥3 lần ➔ Tự soạn thảo SOP hoàn chỉnh và trình duyệt.
- **AC-09 — Flow F (Chuyến công tác theo mục tiêu):** Lập kế hoạch đi Singapore gồm vé máy bay, khách sạn, khảo sát quán protein bar, đặt chỗ sau khi duyệt và xuất lịch trình đầy đủ.
- **AC-10 — Context-Bleed Test:** Vượt qua 20/20 câu hỏi bẫy trộn lẫn ngữ cảnh giữa 3 workspace (100% từ chối hoặc hỏi làm rõ).
- **AC-11 — Autonomy & Verification Tests:** Cưỡng chế chặn Tier 3 trong code; bắt được 100% lỗi giả lập khi không có bằng chứng; đối chiếu cuối ngày báo cáo đúng sai lệch.

## Thứ tự tính năng đề xuất

Lộ trình triển khai theo nguyên tắc "Khung lớn chạy trước, tinh chỉnh chi tiết sau" (6 tuần + 2 tuần dự phòng):

1. **Tuần 1 — Nền tảng & Kết nối:** Triển khai Hermes Agent trên Azure VM, cấu hình định tuyến model Claude, mở cổng Telegram & Email, khởi tạo Markdown Vault và SQLite State DB.
2. **Tuần 2 — Khung Workspace & Thí điểm PROTEIN BAR:** Cấu hình cách ly 3 workspace; nạp tri thức Protein Bar (master plan, ngân sách, nhà cung cấp); thiết lập bản tin sáng 07:30 và nhật ký Scribe; chứng minh Flow A.
3. **Tuần 3 — Cổng phê duyệt & Bộ kiểm chứng:** Kích hoạt 4 mức tự chủ, hàng đợi duyệt trên Telegram, Verifier kiểm tra bằng chứng, radar ngày giấy phép/hợp đồng thuê, khóa nháp chủ nhà.
4. **Tuần 4 — Động cơ chủ động & Onboard CLIENT PROJECTS:** Chạy tự động đuổi theo nhà cung cấp Protein Bar; nạp workspace Client Projects (dự án TWJ, chat dev, transcript họp); chạy báo cáo tuần Flow D.
5. **Tuần 5 — Onboard TITAN AI & Kế toán & Deliverables Studio:** Nạp workspace TITAN AI (SMM, VA/Editor); kích hoạt AI Accountant (hóa đơn, nhắc nợ, phân loại chi phí thác nước); kết nối Canva/Higgsfield; chạy Flow C & Flow F.
6. **Tuần 6 — Tinh chỉnh, Đánh giá & Bàn giao:** Vòng lặp tự sinh SOP, bảng thống kê tốt nghiệp mức tự chủ, dashboard theo dõi, chạy toàn bộ bộ test nghiệm thu AC-01 đến AC-11.
7. **Tuần 7–8 — Dự phòng & Mở rộng (Buffer & Stretch):** Mở rộng Video Intelligence v0 (phân tích hook/pacing video ngắn cho TITAN), hoàn thiện WhatsApp hai chiều, tinh chỉnh giọng nói.

## Điểm cần khách hàng xác nhận

1. Thông tin tài khoản và phân quyền kết nối (Google Workspace OAuth, Telegram Bot Token, Make.com, Canva Team, Higgsfield).
2. Danh sách nhà cung cấp Protein Bar, hợp đồng thuê hiện tại và các điều khoản đàm phán không thể nhượng bộ (walk-away points).
3. Hạn mức tiền tối đa cho các giao dịch được phép chuẩn bị nháp và thẩm quyền phê duyệt của từng cá nhân.
4. Ngưỡng thời gian chờ phản hồi mặc định cho từng nhóm đối tượng (khách hàng, nhà cung cấp, nội bộ).
5. Mẫu biểu báo cáo tuần chuẩn cho từng workspace trong Notion/Google Docs.
6. Cấu hình ngân sách chi phí token/API hằng tuần cho hệ thống.

## Nội dung không dùng làm yêu cầu

Các mục sau được xác định rõ ràng là **NGOÀI phạm vi (OUT of scope)** hoặc không ràng buộc thiết kế:

- Tự ý chuyển tiền, thanh toán ngân hàng hoặc ký kết văn bản pháp lý thay con người.
- Sử dụng các giải pháp tự động hóa không chính thức (grey bot) trên tài khoản WhatsApp/mạng xã hội cá nhân.
- Xây dựng lại từ đầu các thành phần mà nền tảng Hermes Agent đã có sẵn (gateways, memory, scheduler, subagents, sandbox).
- Chia tách hệ thống thành 3 bot độc lập hoặc xây dựng kiến trúc microservices phức tạp ngay từ đầu.
