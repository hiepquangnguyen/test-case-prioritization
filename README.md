# HC-FALCON — Test Case Prioritization

Dự án nghiên cứu kết hợp semantic facility location, failure history và execution
cost cho bài toán TCP (Test Case Prioritization). Trải qua **12 giai đoạn**:
từ kiểm tra artifact, triển khai lõi HC-FALCON, pilot diện rộng trên 3 dự án
LRTS (596 stage, 519 physical build, 33.972 ranking), đến tái lập 100% FALCON
trên 6 dự án Defects4J (20.770 methods, 288 faults), phân tích forensic và
thử nghiệm biến thể cải tiến.

**Trạng thái khoa học**: HC-FALCON không vượt qua được baseline `history_cost` trên tập dữ liệu Long-Running Test Suites (LRTS). Cả bốn thế hệ thử nghiệm trên tập Development đều không đạt Effect Gate ($\ge +3.0\%$ pts):
- **Stage 6 (`hc_falcon_normalized_v1`)**: Thua −1.27% (Karaf), −1.41% (ActiveMQ), −0.12% (Log4j) $\rightarrow$ **0/3 NO-GO**.
- **Stage 8 (`restricted_v1`)**: Khóa không gian hoán đổi quanh head, vẫn thua −0.02% đến −0.15% $\rightarrow$ **0/3 NO-GO**.
- **Stage 11 (`hc_cns_v1` - CNS-Greedy)**: Chuẩn hóa chi phí vào marginal semantic gain giúp giảm 60% mức thua và kéo Mean delta sang dương (+1.7% đến +3.5%), nhưng **Median paired $\Delta$APFDc vẫn âm** (−0.40% Karaf, −0.61% ActiveMQ, −0.19% Log4j) $\rightarrow$ **0/3 NO-GO**.
- **Stage 12 (`hc_ugcs_v2`)**: Bảo vệ semantic bằng cận bất định Bayes, nhưng Median paired $\Delta$APFDc vẫn âm (−0.059% Karaf, −0.224% ActiveMQ, −0.002% Log4j); đồng thời P95 runtime overhead vượt xa ngưỡng $10\%$ $\rightarrow$ **Effect 0/3 và Engineering NO-GO**.

**Nguyên nhân gốc rễ**: Hiệu ứng *"Heavy Predecessors"* — thuật toán greedy ngữ nghĩa ban đầu phi chi phí (cost-agnostic) đưa các test class nặng (chạy 100–150s, không chứa lỗi) lên đầu danh sách chỉ để tối ưu đa dạng ngữ nghĩa, gây trễ tích lũy lũy kế ròng tới **+39.099,3 giây (~10.8 giờ)** trên 161 build lỗi. Đồng thời, tín hiệu lịch sử lỗi kết hợp chi phí thực thi ($q_b(t)$) là một baseline cực kỳ mạnh trong CI thực tế.

**Ranh giới và Phạm vi Kết luận**:
- Kết luận âm chỉ áp dụng trong bối cảnh: hệ sinh thái Java/Maven, kiểm thử mức lớp (**Class-level TCP** với chi phí thực thi phân tán mạnh từ vài mili-giây tới hàng trăm giây), ba dự án Apache (Karaf, ActiveMQ, Log4j2), và mô hình thực thi tuần tự tuyến tính đo bằng metric APFDc.
- Kết luận này **không tuyên bố semantic TCP thất bại trong mọi bối cảnh** (ví dụ: trên Defects4J method-level với chi phí đồng đều, FALCON gốc đã được tái lập thành công 100% với APFD 0.7260 vs 0.7223 tác giả).
- Toàn bộ tập dữ liệu xác nhận (**Reserved Confirmation Dataset**) tiếp tục được **khóa niêm phong 100%**. Tuyệt đối không tiếp tục dò tham số ($p$-hacking) trên tập Development.

**Hướng Nghiên cứu Mới trong Tương lai**:
Mọi phát triển kế tiếp cần được thực hiện như một công trình nghiên cứu mới độc lập với protocol, dataset, metric và gate được đăng ký trước (pre-registered):
1. **Method-level TCP** trên CI để tránh loãng embedding khi gộp nhiều methods vào class.
2. **Cold-start-only Semantic Prioritization**: Chỉ kích hoạt semantic cho các test mới ($N=0$).
3. **Parallel / Sharded CI Metrics**: Đánh giá trên hạ tầng CI phân tán nhiều luồng hoặc song song theo module.
4. **Đa dạng hóa Hệ sinh thái**: Thử nghiệm trên các ngôn ngữ thông dịch (Python, JS) hoặc biên dịch hệ thống (Rust, Go).

## Cài đặt và Tái lập (Clean Clone)

### 1. Khởi tạo môi trường từ Clean Clone

```powershell
git clone https://github.com/hiepquangnguyen/test-case-prioritization.git
cd test-case-prioritization

python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[all,dev]"
```

Hoặc dùng `requirements.txt`: `.venv\Scripts\python.exe -m pip install -r requirements.txt`

### 2. Bootstrap artifact FALCON

Tập tin ZIP artifact FALCON không được đưa vào Git do dung lượng và chính sách phân phối. Mã nguồn kiểm thử tích hợp và tái lập Defects4J/Bridge Chart cần một số file upstream từ gói FALCON v1.

Trước khi bootstrap, lệnh verifier sẽ báo lỗi rõ ràng có chủ đích chỉ dẫn người dùng cần bootstrap.

Tải archive `falcon.zip` từ bản ghi nhận đã pin: [Zenodo Record 18897073](https://zenodo.org/records/18897073) (kích thước 24.089.023 bytes, SHA-256 `d60fa62edf1d1838185edf19e61146f5981895702f6a7afce0ab8c3f65ee36c8`).

Chạy kịch bản bootstrap an toàn (kiểm tra SHA-256, chống Zip Slip, chỉ giải nén whitelist vào thư mục cục bộ `work/artifacts/falcon/`, thao tác mang tính idempotent):

```powershell
.venv\Scripts\python.exe scripts\bootstrap_falcon.py --archive C:\path\to\falcon.zip
```

*Lưu ý:*
- Thư mục `work/` được loại trừ hoàn toàn bởi `.gitignore`.
- Archive DANTE (~3,4 GB) không cần thiết cho quá trình kiểm thử hoặc chạy verifier chuẩn.
- Tuyệt đối không hardcode đường dẫn cục bộ cá nhân vào repository.

### 3. Chạy kiểm thử tự động

Sau khi bootstrap, chạy toàn bộ bộ kiểm thử tự động (đếm động qua discovery):

```bash
python -m pytest -q
```

Hoặc chạy qua `unittest`:

```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 4. Xác minh toàn diện hệ thống (Verifier tổng hợp)

Dự án cung cấp entry point duy nhất để xác minh toàn bộ tính toàn vẹn kỹ thuật, hash mật mã và các bất biến khoa học:

```bash
python scripts/verify_all.py --verbose
```

## Tài liệu theo giai đoạn

### Giai đoạn 12: HC-FALCON v2 và development screening
- [Bài toán và giả thuyết v2](docs/12-hc-falcon-v2/problem-statement.md)
- [Đặc tả UGCS v2](docs/12-hc-falcon-v2/specification.md)
- [Protocol đánh giá đã đăng ký trước](docs/12-hc-falcon-v2/evaluation-protocol.md)
- [Kết quả development screening](reports/stage12/development-screen.json)

### Báo cáo Nghiên cứu Kỹ thuật & Lý thuyết (Phase W / T10)
- [Bản thảo báo cáo nghiên cứu hoàn chỉnh](docs/research-report/report.md)
- [Cơ sở lý thuyết, chứng minh submodular và độ phức tạp](docs/research-report/theory.md)
- [Giới hạn nghiên cứu và Threats to Validity](docs/research-report/limitations.md)

### Giai đoạn 11: Forensic & biến thể cải tiến
- [Phân tích forensic LRTS](docs/11-improvement/forensic-report.md)
- [Giả thuyết và thiết kế thí nghiệm](docs/11-improvement/hypothesis-and-design.md)
- [Kết quả thử nghiệm CNS/Knapsack/Tiered](docs/11-improvement/phase3-report.md)

### Giai đoạn 10: Tái lập Defects4J & Bridge Chart
- [Quyết định đóng Phase R](docs/10-reproduction/decision.md)
- [Báo cáo tái lập 6 dự án](docs/10-reproduction/reproduction-report.md)
- [Phân tích Bridge Chart A/B/C/D](docs/10-reproduction/bridge-report.md)
- [Protocol tái lập](docs/10-reproduction/protocol.md)
- [Đính chính và phả hệ mã băm](docs/10-reproduction/amendment.md)
- [Bàn giao cho AI agent](docs/10-handoff/README.md)

### Giai đoạn 9: Đánh giá độ tin cậy
- [Đối chiếu fidelity và kế hoạch tiếp](docs/09-fidelity/review-and-next-plan.md)

### Giai đoạn 8: Biến thể Restricted
- [Kết quả restricted semantic/cost](docs/08-revision/implementation-report.md)
- [Đặc tả và tái lập](docs/08-revision/specification-and-reproduction.md)
- [Báo cáo cache policy](docs/08-revision/cache-policy-report.md)

### Giai đoạn 7: Chẩn đoán sau pilot
- [Phân tích và đề xuất](docs/07-diagnosis/diagnosis-and-proposal.md)

### Giai đoạn 6: Pilot development diện rộng
- [Báo cáo kết quả pilot và quyết định no-go](docs/06-pilot/implementation-report.md)
- [Tái lập giai đoạn 6](docs/06-pilot/reproduction.md)

### Giai đoạn 5: Triển khai và kiểm chứng
- [Báo cáo triển khai](docs/05-implementation/implementation-report.md)
- [Tái lập giai đoạn 5](docs/05-implementation/reproduction.md)

### Giai đoạn 4: Đa dự án và thiết kế
- [Báo cáo thiết kế](docs/04-design/implementation-report.md)
- [Đặc tả HC-FALCON v1 và biến thể chuẩn hóa](docs/04-design/hc-falcon-v1.md)
- [Protocol đánh giá đa dự án](docs/04-design/evaluation-protocol.md)

### Giai đoạn 3: Chuẩn hóa dữ liệu và pilot Karaf
- [Báo cáo pilot Karaf](docs/03-pilot/implementation-report.md)
- [Protocol v2 và semantic fallback](docs/03-pilot/protocol-v2.md)
- [Tái lập pilot baseline](docs/03-pilot/reproduction.md)

### Giai đoạn 2: Triển khai protocol v1
- [Báo cáo triển khai](docs/02-protocol/implementation-report.md)
- [Quy tắc protocol v1](docs/02-protocol/protocol-v1.md)
- [Chạy kiểm thử và replay](docs/02-protocol/reproduction.md)

### Giai đoạn 1: Khả thi và artifact
- [Báo cáo khả thi](docs/01-feasibility/stage1-report.md)
- [Đặc tả đề tài](topic1.md)
- [Manifest artifact](references/artifact-manifest.md)
- [Hướng dẫn tái lập](docs/01-feasibility/reproduction.md)
- [Đọc hiểu bài toán, FALCON, DANTE và đề tài HC-FALCON](docs/00-foundations/doc-hieu-de-tai.md)
- [Thuật toán, công thức và lý thuyết](docs/00-foundations/thuat-toan-va-ly-thuyet.md)

## Cấu trúc

| Thư mục | Nội dung |
|---|---|
| `tcp/` | Data model, adapter LRTS, history, baseline, evaluator và replay. |
| `hc_falcon/` | Encoder/cache, standard/lazy greedy, HC variants, FAST và DANTE adaptations. |
| `scripts/` | Kịch bản tự động hóa từ stage 1 đến 12 (audit, run, verify, report). |
| `tests/` | Kiểm thử công thức, cutoff, ranh giới dữ liệu và trường hợp biên. |
| `configs/` | Cấu hình đóng băng có phiên bản (HC-FALCON, protocol, bridge, reproduction). |
| `docs/` | Báo cáo, thiết kế, protocol và hướng dẫn tái lập theo từng giai đoạn. |
| `reports/` | Bằng chứng thực nghiệm có niêm phong SHA-256 (JSON, CSV, log, hình). |
| `reports/figures/` | 4 biểu đồ báo cáo khoa học (Defects4J reproduction, Bridge, LRTS gate, Heavy predecessors). |
| `references/artifacts/` | ZIP gốc FALCON, DANTE và README tác giả. |
| `docs/00-foundations/` | Hai tài liệu nền tảng: đọc hiểu đề tài và thuật toán/lý thuyết, tổng hợp từ Topic 1 cùng hai paper gốc. |
| `work/` | Dữ liệu cục bộ: môi trường venv, cache mô hình, embedding, kết quả chạy. |

`work/` là dữ liệu cục bộ có thể tái tạo; không đưa vào quản lý phiên bản.
Kết quả tác giả trong ZIP được giữ riêng với kết quả tự chạy.
