# Giai đoạn 5 — triển khai HC-FALCON

Ngày 2026-09-14. Lõi HC-FALCON và các đối chứng đã có implementation chạy được,
đủ điều kiện bắt đầu pilot development. Chưa có bằng chứng HC-FALCON tốt hơn
baseline về APFD/APFDc. Tập reserved confirmation của ActiveMQ/Log4j chưa mở.

## Phạm vi đã hoàn thành

Package `hc_falcon/` tách khỏi các module `tcp/` đã đóng băng:

- HC-FALCON-N, biến thể topic raw, FL-only, FL+History, bỏ confidence,
  Borda FL+History và FL+History+cost; dùng lại sáu baseline lịch sử.
- Standard greedy và exact lazy greedy, gain float64, tie FQN, giữ đủ inventory;
  trace lưu semantic/modular/total gain và tổng coverage sau mỗi lựa chọn.
- Java comment scanner giữ string/char/text block; UTF-8 strict, BOM/LF;
  UniXcoder offline ở revision đã khóa, tối đa 16 chunk dài 512 token,
  masked mean và payload-weighted pooling, kernel float32 clip [0,1].
- Cache vector theo source/config/tokenizer/model revision/framework và cache
  kernel theo ordered inventory/mask/vector hashes. Nguồn không dùng được giữ
  test, semantic bằng 0; lỗi nonfinite dừng chạy.
- FAST-pw-LRTS adaptation với 20 seed, local RNG, candidate choice ổn định;
  DANTE-CCH-adapt-r1 dùng lịch sử theo completion, cửa sổ 15 build và 1/3/5,
  TF-IDF relevance từ diff khai báo, cost estimate từ quá khứ.
- Các runner source/diff/technical smoke/verification chạy lại được; kiểm tra
  hash của thiết kế và bằng chứng giai đoạn 4 trước mỗi runner chính.

Đây là các adaptation đã định nghĩa trong protocol, không phải tuyên bố tái lập
nguyên bản FALCON/DANTE trên cùng điều kiện paper.

## Nguồn và diff

Đã xử lý toàn bộ warm-up/development: 1.050 build-stage, 461.050 test observations;
1.279 commit khai báo theo tổng ba repository đều có cục bộ.

| Dự án | Build-stage | Source khớp / observations | Tỷ lệ | Diff dùng được |
|---|---:|---:|---:|---:|
| Karaf | 563 | 119.761 / 120.360 | 99,50% | 563 / 563 |
| ActiveMQ | 223 | 170.412 / 174.539 | 97,64% | 219 / 223 |
| Log4j | 264 | 163.403 / 166.151 | 98,35% | 264 / 264 |

Cả ba vượt source gate 90%. Missing/ambiguous không bị loại khỏi inventory.
Mapping dùng cùng phép kiểm tra path/package/outer declaration ở giai đoạn 4;
không phải Java AST và không chứng minh revision thực sự được CI thực thi.

Bốn diff ActiveMQ không phải UTF-8 nghiêm ngặt thuộc **warm-up**:
PR-263, PR-230, PR-160, PR-126, build 1. DANTE unavailable ở các record này;
không làm mất dữ liệu lịch sử dùng cho build sau, không ảnh hưởng inventory HC.
Tất cả diff development hiện dùng được. Không tự đoán encoding để thay đổi
relevance. Một blob Karaf bị bộ lọc partial clone bỏ qua đã được xác minh thuộc
endpoint được phép và tải bổ sung, khôi phục ba diff.

Diff document hiện được cụ thể hóa thành patch riêng từng Java file,
`git diff --no-ext-diff --no-textconv --no-renames --no-color --unified=3`,
trunk → head, đọc local với lazy fetch tắt. Không checkout/build/chạy Java upstream.

## Kiểm chứng

- **37 unit tests đạt**, gồm 12 test mới: công thức tính tay, biên n=0/1,
  q=0/mask=0, source giống nhau nhưng ID khác nhau, alpha endpoints,
  negative cosine, padding, chunk cap/weighted pooling, cache invalidation,
  lịch sử DANTE và mutation current/future labels/costs.
- 300 trường hợp tổng hợp đối chiếu toàn bộ ranking/trace standard–lazy.
- Một suite tổng hợp 1.025 test, vector dimension 32: toàn bộ trace khớp;
  runtime từng thuật toán lưu trong `verification.json`, kernel 4.202.500 byte.
  Đây không phải benchmark tốc độ end-to-end encoder.
- FAST khớp artifact ở **60 phép đối chiếu** (3 fixtures × 20 seed), sau các
  sửa đổi runtime/determinism khai báo; kiểm tra thêm missing-source tail.
- UniXcoder thật: smoke 16 record đầu theo FQN của build warm-up đầu tiên
  ở ActiveMQ/Log4j, kiểm tra cache round trip và standard/lazy.
- Tích hợp thật: **16 record đầu theo FQN của build development đầu tiên mỗi
  dự án**; snapshot có lần lượt 20/73/21 build lịch sử hợp lệ ở
  Karaf/ActiveMQ/Log4j; các phương pháp semantic, FAST và DANTE chạy được.

Smoke development dùng inventory con 16 record, vì vậy Q và FL được tính trên
inventory con đó. Không xuất APFD/APFDc, không suy diễn thứ tự full suite từ
smoke, không coi kiểm thử tổng hợp 1.025 test là chạy encoder toàn bộ suite.

## Giới hạn và công việc kế tiếp

Source eligibility đã đủ; chưa embed/rank toàn bộ development bằng encoder thật.
Cần pilot giai đoạn 6 để đo chất lượng ưu tiên, overhead, cache hit, truncation,
fallback và các ablation trên full inventory. Thống kê theo physical build;
không coi stage hoặc seed là mẫu độc lập. Reserved confirmation tiếp tục đóng
cho đến khi thỏa điều kiện protocol.

Inventory vẫn lấy từ observed logs; source là revision metadata khai báo;
test dependency/generated hoặc FQN nhiều module còn missing/ambiguous. Comment
scanner không thay thế Java compiler/AST và không diễn giải Unicode escapes ở
giai đoạn lexical translation của Java. Không tuyên bố nghiên cứu đã hoàn tất,
hoặc kết quả này áp dụng cho Defects4J chưa chạy trong giai đoạn này.

## Bằng chứng

- [Tổng kiểm chứng](../../reports/stage5/verification.json)
- [Nhật ký unit tests](../../reports/stage5/unit-tests.txt)
- [FAST đối chiếu](../../reports/stage5/fast-verification.json)
- [Smoke encoder thật](../../reports/stage5/semantic-smoke.json)
- [Karaf](../../reports/stage5/karaf/technical-verification.json),
  [ActiveMQ](../../reports/stage5/activemq/technical-verification.json),
  [Log4j](../../reports/stage5/log4j/technical-verification.json)
- [Tái lập](reproduction.md)
