# Yêu cầu khách hàng

Tài liệu này là bản yêu cầu nghiệp vụ tiếng Việt, trích từ `docs/Hermes Project.docx` để định hướng các feature tiếp theo.

Phạm vi chỉ giữ mục tiêu, hành vi sản phẩm, ràng buộc và tiêu chí nghiệm thu. Không dùng phần kiến trúc, công nghệ, nhà cung cấp, credit, lịch triển khai hoặc tài liệu học tập được đề xuất trong tài liệu nguồn.

## Mục tiêu

Xây trợ lý AI giúp nhân viên giảm thời gian cho công việc thủ công, lặp lại bằng cách:

- Trả lời câu hỏi dựa trên tri thức công ty.
- Thực hiện nghiên cứu web và phân tích đối thủ, có nguồn dẫn.
- Biến chủ đề hoặc kết quả nghiên cứu thành bản nháp presentation deck.
- Trả lời câu hỏi sản phẩm và hỗ trợ sàng lọc lead.
- Soạn bản nháp hóa đơn và hỗ trợ back-office an toàn.
- Cho phép đồng đội không chuyên kỹ thuật sử dụng qua giao diện chat và Slack.

Sản phẩm hỗ trợ con người ra quyết định; không tự thay thế phê duyệt nghiệp vụ tài chính.

## Đối tượng sử dụng

- **Nhân viên nội bộ:** hỏi thông tin công ty, yêu cầu nghiên cứu, deck và hóa đơn.
- **Người không chuyên kỹ thuật:** sử dụng mà không cần terminal hoặc hướng dẫn chi tiết.
- **Lead/khách hàng tiềm năng:** hỏi về sản phẩm và tham gia hội thoại sales/discovery.
- **Người phê duyệt:** cho phép hoặc từ chối hành động liên quan hóa đơn, thanh toán hoặc tiền.
- **Người vận hành kho tri thức:** cập nhật tài liệu và chạy lại quá trình ingestion.
- **Người nhận bàn giao:** khởi động, kiểm tra và demo hệ thống.

## Yêu cầu chức năng

### Tri thức công ty

- **REQ-KB-01:** Hệ thống phải trả lời câu hỏi dựa trên tài liệu nội bộ, SOP, thông tin sản phẩm và giá.
- **REQ-KB-02:** Câu trả lời phải kèm citation để người dùng kiểm tra nguồn.
- **REQ-KB-03:** Quá trình ingestion phải chạy lại được khi tài liệu thay đổi.
- **REQ-KB-04:** Kho tri thức phải phản ánh dữ liệu mới sau lần ingestion thành công.

### Nghiên cứu

- **REQ-RESEARCH-01:** Hệ thống phải thực hiện web research theo yêu cầu.
- **REQ-RESEARCH-02:** Hệ thống phải hỗ trợ competitor scan.
- **REQ-RESEARCH-03:** Kết quả phải gồm bản tóm tắt và danh sách nguồn.

### Presentation deck

- **REQ-DECK-01:** Hệ thống phải nhận một chủ đề hoặc kết quả nghiên cứu làm đầu vào.
- **REQ-DECK-02:** Hệ thống phải tạo first-draft presentation deck từ đầu vào đó.
- **REQ-DECK-03:** Khi deck dùng dữ liệu nghiên cứu, nguồn phải được giữ để người dùng kiểm tra.

### Sales và lead qualification

- **REQ-SALES-01:** Hệ thống phải hỗ trợ hội thoại sales/discovery.
- **REQ-SALES-02:** Hệ thống phải trả lời câu hỏi sản phẩm bằng dữ liệu được phép sử dụng.
- **REQ-SALES-03:** Hệ thống phải thu thập thông tin cần thiết để sàng lọc lead.
- **REQ-SALES-04:** Kết quả qualification phải phân biệt dữ liệu người dùng cung cấp với đánh giá của hệ thống.

### Hóa đơn và back-office

- **REQ-INVOICE-01:** Hệ thống phải tạo bản nháp hóa đơn từ dữ liệu người dùng cung cấp.
- **REQ-INVOICE-02:** Hệ thống phải hiển thị dữ liệu hóa đơn để người dùng kiểm tra trước bước có tác động bên ngoài.
- **REQ-INVOICE-03:** Mọi hành động gửi, thanh toán hoặc tác động tới tiền phải chờ human approval.
- **REQ-INVOICE-04:** Từ chối, hết thời gian chờ hoặc thiếu phê duyệt không được coi là đồng ý.

### Kênh sử dụng và vận hành

- **REQ-CHANNEL-01:** Người dùng phải có giao diện chat.
- **REQ-CHANNEL-02:** Hệ thống phải truy cập được qua Slack.
- **REQ-OPS-01:** Người nhận bàn giao phải khởi động dịch vụ bằng một lệnh.
- **REQ-OPS-02:** README phải phản ánh đúng trạng thái thực tế của hệ thống.

## Yêu cầu phi chức năng

### Bảo mật và riêng tư

- **NFR-SEC-01:** Không đưa customer PII vào prompt gửi cho công cụ bên thứ ba.
- **NFR-SEC-02:** Không commit secret, token hoặc API key vào repository.
- **NFR-SEC-03:** Chỉ cấp quyền tool cần thiết cho từng luồng nghiệp vụ.
- **NFR-SEC-04:** Dữ liệu nhạy cảm không được xuất hiện trong log, trace hoặc thông báo phê duyệt.

### Khả dụng

- **NFR-USE-01:** Đồng đội chưa được hướng dẫn vẫn hoàn thành được các luồng chính.
- **NFR-USE-02:** Người không dùng terminal vẫn truy cập được hệ thống.
- **NFR-USE-03:** Thông báo lỗi phải nêu lỗi và bước khắc phục có thể thực hiện.

### Truy xuất nguồn

- **NFR-SOURCE-01:** Knowledge answer và research output phải có nguồn.
- **NFR-SOURCE-02:** Citation phải đủ thông tin để người dùng mở và kiểm tra nguồn gốc.

### Bảo trì và bàn giao

- **NFR-MAINT-01:** Ingestion phải rerunnable.
- **NFR-MAINT-02:** Tài liệu vận hành phải cập nhật cùng thay đổi hành vi.
- **NFR-MAINT-03:** Người xây dựng phải giải thích được code đã bàn giao.

### Đánh giá và chi phí

- **NFR-EVAL-01:** Có evaluation sheet gồm 10 câu hỏi knowledge-base và 5 task runs.
- **NFR-EVAL-02:** Ghi điểm trước và sau cải tiến để thấy thay đổi chất lượng.
- **NFR-COST-01:** Có cost log theo từng dịch vụ hoặc capability sử dụng.

## Guardrails bắt buộc

1. Không gửi customer PII cho công cụ bên thứ ba qua prompt.
2. Không lưu secret trong repository.
3. Không thực hiện hành động liên quan invoice, payment hoặc money khi chưa có human approval rõ ràng.
4. Deny, timeout hoặc thiếu phản hồi không bao giờ được chuyển thành approval.
5. Knowledge answer và research result phải giữ provenance/citation.
6. Mọi feature phải có acceptance behavior và verifier trước khi chuyển sang `passing`.
7. Ưu tiên lát cắt nhỏ chạy end-to-end; không mở nhiều feature dở dang cùng lúc.

## Tiêu chí nghiệm thu

- **AC-01 — Company Q&A:** Đồng đội đặt câu hỏi về công ty và nhận câu trả lời dựa trên tài liệu, kèm citation.
- **AC-02 — Research:** Đồng đội gửi chủ đề và nhận tóm tắt nghiên cứu có nguồn.
- **AC-03 — Research to deck:** Đồng đội gửi chủ đề hoặc research result và nhận first-draft deck.
- **AC-04 — Sales:** Lead hỏi câu hỏi sản phẩm, cung cấp thông tin qualification và nhận phản hồi phù hợp.
- **AC-05 — Invoice:** Đồng đội yêu cầu hóa đơn và nhận bản nháp; không có hành động tài chính trước approval.
- **AC-06 — Không cần hướng dẫn:** Người dùng mới hoàn thành company Q&A, research/deck và draft invoice qua giao diện cung cấp.
- **AC-07 — Slack:** Các luồng được phê duyệt cho Slack có thể bắt đầu và trả kết quả trong đúng conversation/thread.
- **AC-08 — One-command start:** Người nhận bàn giao khởi động dịch vụ bằng một lệnh được ghi trong README.
- **AC-09 — Rerunnable ingestion:** Tài liệu thay đổi, chạy lại ingestion, câu trả lời sử dụng dữ liệu mới.
- **AC-10 — Evaluation artifact:** Có kết quả 10 knowledge questions và 5 task runs, gồm điểm trước/sau.
- **AC-11 — Cost artifact:** Có cost log phân loại theo dịch vụ hoặc capability.

## Thứ tự tính năng đề xuất

Đây là thứ tự triển khai suy ra từ phụ thuộc nghiệp vụ, không phải lịch triển khai trong tài liệu nguồn:

1. **Nền bảo mật và vận hành:** secret handling, PII boundary, logging/redaction, one-command start.
2. **Knowledge ingestion và Q&A có citation:** tạo nền dữ liệu cho internal Q&A và product Q&A.
3. **Web research có nguồn:** reuse cơ chế citation/provenance.
4. **Research-to-deck:** dùng output research đã có nguồn để tạo first draft.
5. **Slack end-to-end:** đưa các luồng đã verified lên kênh người dùng thật.
6. **Sales/product Q&A và lead qualification:** reuse knowledge layer; thêm schema/rule qualification sau khi khách hàng chốt.
7. **Draft invoice và human approval:** chỉ làm sau khi chốt invoice schema, approver và approval boundary.
8. **Evaluation và cost reporting:** chạy xuyên suốt từ feature đầu tiên, hoàn thiện dashboard/report khi các luồng chính ổn định.

Mỗi mục phải được tách thành feature nhỏ, có verifier riêng và giữ `WIP=1`.

## Điểm cần khách hàng xác nhận

1. Ngưỡng pass/accuracy cho 10 knowledge questions và 5 task runs.
2. Citation format, số nguồn tối thiểu và quy tắc nguồn được chấp nhận.
3. Danh sách tài liệu/SOP/product/pricing được phép ingest.
4. Authentication, authorization và nhóm người được truy cập từng loại tài liệu.
5. Định nghĩa customer PII, retention period, deletion và audit policy.
6. Lead fields cần thu thập, câu hỏi discovery và tiêu chí qualified lead.
7. Nơi lưu lead và ai được truy cập dữ liệu đó.
8. Các trường bắt buộc của invoice, currency, tax và numbering rules.
9. Chính xác bước nào cần approval: tạo draft, gửi, ghi sổ hay thanh toán.
10. Ai có quyền approve; approval có hết hạn, threshold hoặc yêu cầu nhiều người hay không.
11. Template, brand guideline và rubric chất lượng của presentation deck.
12. Slack workspace, channel/thread behavior và quyền truy cập bot.
13. Latency, availability và concurrency kỳ vọng.
14. Cost ceiling và nhịp báo cáo chi phí; tài liệu nguồn nhắc cả daily tracking và Friday logging.

## Nội dung không dùng làm yêu cầu

Các phần sau trong tài liệu nguồn không ràng buộc implementation:

- Kiến trúc kỹ thuật được đề xuất.
- Lựa chọn framework, SDK, model provider hoặc dịch vụ cụ thể.
- Danh sách credit/tài nguyên nhà cung cấp.
- Lịch triển khai theo ngày.
- Learning resources.
- Stretch goals chưa được khách hàng chốt.

Mọi quyết định implementation phải dựa trên code hiện có, acceptance criteria và lựa chọn được phê duyệt sau này.