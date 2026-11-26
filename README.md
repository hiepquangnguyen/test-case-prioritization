# HC-FALCON

Ưu tiên test case bằng tối ưu hóa submodular, có xét lịch sử lỗi và thời gian chạy (Đề tài 1).

- Đề bài: [topic1.md](topic1.md)
- Phân tích chi tiết: [phan-tich-de-tai-1.md](phan-tich-de-tai-1.md)
- Paper nền FALCON (ICST 2026): artifact tại [anonymous-ing/falcon-icst-2026](https://github.com/anonymous-ing/falcon-icst-2026)
- Paper LRTS (Cheng et al., ISSTA 2024, "Revisiting Test-Case Prioritization on Long-Running Test Suites"):
  artifact tại [lrtsuser/LRTS](https://github.com/lrtsuser/LRTS)
- Bản PDF của hai paper (`paper-topic1.pdf`, `papers/`) chỉ để ở máy, không đưa lên git vì là tài liệu có bản
  quyền của bên thứ ba.
- Giao thức thực nghiệm (đã chốt): [configs/default.yaml](configs/default.yaml)

## Cài đặt (Windows, Python 3.11+)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m pip install -e . --no-deps
.venv\Scripts\python -m pytest -q
```

Máy local **không cần torch/GPU**. Embedding được tính trên Colab/Kaggle bằng
[notebooks/embed_colab.ipynb](notebooks/embed_colab.ipynb).

## Dữ liệu và artifact (không đưa vào git)

| Thư mục | Nội dung | Cách lấy |
|---|---|---|
| `external/falcon-icst-2026` | Artifact FALCON: input Defects4J, code FALCON/FAST (MIT, ~320 MB) | `git clone https://github.com/anonymous-ing/falcon-icst-2026 external/falcon-icst-2026` |
| `external/LRTS` | Artifact LRTS: code đánh giá, metadata, `eval_outcome` (MIT, ~270 MB) | `git clone https://github.com/lrtsuser/LRTS external/LRTS` |
| `data/lrts/long_running_test_suites/` | Processed LRTS: `dataset.csv`, `processed_test_result/` (kết quả test mức class), `shadata/` (thay đổi code) | Tải từ [Google Drive của LRTS](https://drive.google.com/file/d/13vnCA0tY2BMY9irfn0nV01bJnST6z4kx/view?usp=sharing) (3 GB, giải nén 14.8 GB), giải nén vào `data/lrts/` |
| `data/embeddings/d4j/<Project>/` | Embedding UniXcoder và thứ tự FALCON gốc cho Defects4J | Chạy notebook chế độ (a), giải nén zip vào `data/embeddings/` |

## Tái lập FALCON (tuần 2)

1. Mở `notebooks/embed_colab.ipynb` trên Colab (GPU), chạy các ô chế độ (a), tải `d4j_export.zip`.
2. Giải nén vào `data/embeddings/` để có `data/embeddings/d4j/Chart/...`.
3. Chạy:

```powershell
.venv\Scripts\python -m hcfalcon.d4j.falcon_repro
```

Kết quả nằm ở `results/d4j/`: APFD từng dự án, độ lệch so với Bảng IV của paper, mức trùng khớp với thứ tự do
code FALCON gốc sinh ra. `python scripts/falcon_divergence.py` giải thích chỗ hai thứ tự tách nhau và đo độ nhạy
của APFD với cách phá hòa.

**Kết quả (2026-11-26):**

| | Chart | Closure | Lang | Math | Mockito | Time | Median |
|---|---|---|---|---|---|---|---|
| Paper (Bảng IV) | .726 | .700 | .754 | .622 | .736 | .794 | .731 |
| Artifact FALCON (Colab T4) | .736 | .704 | .738 | .615 | .736 | .799 | .736 |
| `lazy_greedy` của mình | .736 | .696 | .738 | .579 | .742 | .799 | .737 |
| Nhiễu 1e-6, 10 seed (min–max) | .731–.746 | .700–.710 | .736–.756 | .584–.668 | .736–.742 | .794–.799 | |

Hai thứ tự trùng nhau cho tới lần hòa tuyệt đối đầu tiên (vị trí 96–431, gain của hai lựa chọn bằng nhau tới
float64), chủ yếu do test method trùng nội dung (Closure 503, Math 152 method). Giá trị FL của mọi tiền tố bằng
nhau. Phần lệch APFD còn lại là do phá hòa: chỉ nhiễu 1e-6 đã làm APFD của Math dao động 0.08.

Ghi chú về dữ liệu LRTS: `dataset.csv` trên Drive (108.366 TSR, tới 2024-04) là tập mẹ của
`external/LRTS/artifact/metadata/dataset.csv` (57.437 TSR, tới 2023-07, khớp từng dòng). Kiểm tra baseline ở
tuần 3 dùng tập của artifact; các TSR từ 2023-08 trở đi có thể làm tập kiểm tra ngoài thời gian.

## Pipeline LRTS và kiểm tra baseline (tuần 3)

```powershell
.venv\Scripts\python scripts\check_lrts_parity.py --projects activemq jackrabbit-oak hbase
```

Script chạy 10 baseline của LRTS theo đúng trình tự thời gian, rồi so với `eval_outcome` gốc ở ba mức: nhãn lọc,
tập TSR được chấm, và APFDc. Kết quả nằm ở `results/parity/<project>.csv`.

**Kết quả (2026-11-26).** Mỗi dự án có 30 cấu hình (10 baseline × 3 bản dữ liệu):

| Dự án | Nhãn lọc khớp | match (≤ 0.01) | noise (≤ 3 SE) | lrts-leak | FAIL |
|---|---|---|---|---|---|
| ActiveMQ | 100% | 27 | 3 | 0 | 0 |
| Jackrabbit Oak | 100% | 28 | 1 | 1 | 0 |
| HBase | 100% | 26 | 1 | 3 | 0 |
| Karaf (dự phòng) | 100% | 28 | 2 | 0 | 0 |
| Hadoop (dự phòng) | freqfail 97.5% | 20 | 0 | 0 | 10 |

- Các baseline gần như tất định (QTF, +CC, +CCH) lệch tối đa 0.0054. Phần lớn chỉ do LRTS làm tròn mỗi giá trị
  đến 3 chữ số.
- `noise`: Random, hoặc MostFail / LatestFail trên FirstFail. Ở các trường hợp này phá hòa ngẫu nhiên quyết định
  gần hết thứ tự, nên chính số của LRTS (10 seed) đã có sai số lớn hơn 0.01.
- `lrts-leak`: kết quả QTF(Avg) LRTS công bố dùng thời gian trung bình **có tính cả lần chạy đang xếp hạng**.
  Tính lại theo cách đó thì khớp từng TSR ở cả 5 dự án (sai khác tuyệt đối trung bình 0.0003). Mình giữ định
  nghĩa sạch.
- Hadoop: 10 FAIL đều nằm ở DeConf và đều do nhãn freqfail lệch làm thừa 2 TSR (423 so với 421). Giá trị APFDc
  vẫn trong ±0.01.

Chi tiết và lý do xem [paper/decisions.md](paper/decisions.md).

## Mã nguồn test và embedding LRTS (tuần 4)

1. Clone repo dạng bare (một lần cho mỗi dự án):

```powershell
git clone --bare https://github.com/apache/activemq.git data/repos/activemq.git
git -C data/repos/activemq.git fetch origin "+refs/pull/*/head:refs/pull/*/head"
```

2. Ánh xạ mỗi (TSR, test class) sang phiên bản file tại commit của build, tách method, xuất corpus:

```powershell
.venv\Scripts\python -m hcfalcon.lrts.export_blobs --project activemq
```

   Kết quả: `data/lrts/source/activemq/` (ánh xạ, `summary.json`) và
   `data/lrts/corpus/activemq_methods.jsonl.gz` (các method duy nhất).

3. Mở `notebooks/embed_colab.ipynb` trên Colab (GPU), chạy ô kiểm tra GPU và các ô của chế độ (b), tải lên file
   corpus. Tải về `lrts_activemq_export.zip`, giải nén vào `data/embeddings/` để có
   `data/embeddings/lrts/activemq/unixcoder_methods.npz`.
4. `hcfalcon.lrts.embeddings.TSRVectors` ghép vector test class cho từng TSR.

**Kết quả ActiveMQ (2026-11-26):**

| | |
|---|---|
| Có mã nguồn / có vector | 98.1% số cặp (TSR, test class). 444/446 TSR đạt ≥ 95%, 2 TSR còn lại đạt 94.8% (thiếu test từ jar phụ thuộc) |
| Test fail có vector (TSR DeConf) | 344/344 |
| Corpus | 2.198 phiên bản file, 4.456 method, 886k token, 420 method bị cắt ở 512 token |
| Thời gian embed (T4) | 17.0 s cho cả lịch sử |
| Cosine giữa các class (TSR 998 class) | trung vị 0.28, chỉ 0.46% cặp âm |
| Láng giềng gần nhất cùng package | 44% (ngẫu nhiên: 4%) |
| Test fail cùng nhau có giống nhau hơn? | Có: cos trung bình 0.319 so với 0.275 của mọi cặp, ở 63% TSR (Wilcoxon p = 0.001) |

## HC-FALCON và chạy thực nghiệm (tuần 5)

```powershell
.venv\Scripts\python scripts\tune_warmup.py --project activemq --dataset deconf
.venv\Scripts\python scripts\run_experiment.py --project activemq --methods all --tag pilot --tuned configs\tuned\activemq-deconf.yaml
.venv\Scripts\python scripts\explain_tsr.py --project activemq --n 3
```

- `tune_warmup.py` chỉ dùng 20% TSR đầu, tinh chỉnh lần lượt α → bộ ước lượng p → κ → γ, rồi β của RankBlend.
  Kết quả ghi vào `configs/tuned/<project>-<dataset>.yaml`.
- `run_experiment.py` chạy theo trình tự thời gian và ghi một dòng cho mỗi (TSR, bản dữ liệu, phương pháp) vào
  `results/raw/`. Bảng tóm tắt trên phần eval nằm ở `results/summary/`, kèm cấu hình đã dùng.
- `explain_tsr.py` ghi lời giải thích từng vị trí vào `results/explain/<project>/`: gain, phần ngữ nghĩa, phần
  lịch sử/chi phí, p, conf, chi phí, các test được phủ thêm.

Các phương pháp có sẵn: `FALCON`, `History`, `History+Cost`, `FL+History`, `HC-FALCON`, `HC-FALCON-noconf`,
`HC-FALCON-ratio`, `RankBlend`, `RRF`, cùng 10 baseline LRTS.

## Pilot go/no-go (tuần 6)

```powershell
.venv\Scripts\python scripts\pilot.py --project activemq --dataset deconf
```

Script thử các biến thể định nghĩa trước trên warm-up và khóa cấu hình, rồi chạy phần eval. Sau đó kiểm định
Wilcoxon + Holm + Cliff's δ, vẽ đường APFDc theo α (chỉ để chẩn đoán), đo overhead và chẩn đoán FALCON. Kết quả
nằm ở `results/pilot/<project>/`.

ActiveMQ, phần eval DeConf: HC-FALCON 0.854, History+Cost 0.862, LatestFail+CCH 0.865, FALCON 0.494. Pilot chưa
đạt ngưỡng. Xem [paper/pilot-memo.md](paper/pilot-memo.md).

## Cấu trúc code

| Module | Vai trò |
|---|---|
| `src/hcfalcon/similarity.py` | embedding → ma trận similarity không âm |
| `src/hcfalcon/submodular.py` | facility location + thành phần modular, `lazy_greedy` / `standard_greedy` |
| `src/hcfalcon/metrics.py` | APFD, APFDc (FFMapU/S, khớp LRTS), rAPFDc, TTFF, % lỗi theo ngân sách thời gian |
| `src/hcfalcon/d4j/falcon_repro.py` | tái lập FALCON trên Defects4J |
| `src/hcfalcon/lrts/loader.py` | đọc chỉ mục TSR và kết quả test mức class của LRTS |
| `src/hcfalcon/lrts/filters.py` | sinh lại nhãn lọc jira / freqfail / stageunique / first (DeConf, FirstFail) |
| `src/hcfalcon/lrts/source.py` | đọc file test tại commit của build từ repo bare (`ls-tree`, `cat-file`), fetch commit theo SHA |
| `src/hcfalcon/lrts/java_parse.py` | tách method test bằng tree-sitter |
| `src/hcfalcon/lrts/export_blobs.py` | ánh xạ (TSR, test class) → blob, xuất corpus method cho Colab |
| `src/hcfalcon/lrts/embeddings.py` | ghép vector test class từ vector method |
| `src/hcfalcon/history.py` | lịch sử từng test theo (project, stage), chỉ cập nhật sau khi xếp hạng |
| `src/hcfalcon/prioritizers.py` | baseline LRTS: Random, QTF, LatestFail, MostFail, LatestTrans, MostTrans, +CC, +CCH |
| `src/hcfalcon/estimators.py` | p (Beta, decay, stickiness, Wilson), conf, chi phí ước lượng |
| `src/hcfalcon/scoring.py` | q = conf·p/(c̃^γ+ε), các công tắc ablation |
| `src/hcfalcon/hc_falcon.py` | HC-FALCON, FALCON-on-LRTS, các ablation, RankBlend, RRF |
| `src/hcfalcon/explain.py` | bảng và câu giải thích vị trí của từng test |
| `src/hcfalcon/stats.py` | Wilcoxon ghép cặp theo TSR, Holm, Cliff's δ, thay đổi trung vị |
| `src/hcfalcon/rolling.py` | vòng lặp đánh giá theo thời gian, chia warm-up / eval |
| `src/hcfalcon/leakage.py` | kiểm tra rò rỉ: bỏ / xáo trộn tương lai, cố ý rò rỉ |

## Tiến độ

- [x] Tuần 1: skeleton, môi trường, test
- [x] Tuần 2 (code): lõi submodular, metric, script tái lập FALCON, notebook Colab (a)
- [x] Tuần 2 (chạy): embedding Defects4J trên Colab, so APFD với Bảng IV (median .737 so với .731)
- [x] Tuần 3: pipeline LRTS, baseline, kiểm tra với `eval_outcome` của LRTS, leakage v1
- [x] Tuần 4 (code): trích mã nguồn test theo build, corpus method ActiveMQ, notebook chế độ (b)
- [x] Tuần 4 (chạy): embed corpus ActiveMQ trên Colab, `emb_coverage` ≥ 95% ở 444/446 TSR
- [x] Tuần 5: HC-FALCON đầu-cuối (estimators, scoring, prioritizer, giải thích), FALCON-on-LRTS, RankBlend, RRF;
  chạy hết ActiveMQ, leakage đạt
- [x] Tuần 6: pilot ActiveMQ, go/no-go #1 → chưa đạt ngưỡng. Xem [paper/pilot-memo.md](paper/pilot-memo.md);
  đang chờ giảng viên chọn hướng
- [ ] Tuần 7: Jackrabbit Oak, HBase (clone, export, embed), DANTE
