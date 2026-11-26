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

## Cấu trúc code

| Module | Vai trò |
|---|---|
| `src/hcfalcon/similarity.py` | embedding → ma trận similarity không âm |
| `src/hcfalcon/submodular.py` | facility location + thành phần modular, `lazy_greedy` / `standard_greedy` |
| `src/hcfalcon/metrics.py` | APFD, APFDc (FFMapU/S, khớp LRTS), rAPFDc, TTFF, % lỗi theo ngân sách thời gian |
| `src/hcfalcon/d4j/falcon_repro.py` | tái lập FALCON trên Defects4J |
| `src/hcfalcon/lrts/loader.py` | đọc chỉ mục TSR và kết quả test mức class của LRTS |
| `src/hcfalcon/lrts/filters.py` | sinh lại nhãn lọc jira / freqfail / stageunique / first (DeConf, FirstFail) |
| `src/hcfalcon/history.py` | lịch sử từng test theo (project, stage), chỉ cập nhật sau khi xếp hạng |
| `src/hcfalcon/prioritizers.py` | baseline LRTS: Random, QTF, LatestFail, MostFail, LatestTrans, MostTrans, +CC, +CCH |
| `src/hcfalcon/rolling.py` | vòng lặp đánh giá theo thời gian, chia warm-up / eval |
| `src/hcfalcon/leakage.py` | kiểm tra rò rỉ: bỏ / xáo trộn tương lai, cố ý rò rỉ |

## Tiến độ

- [x] Tuần 1: skeleton, môi trường, test
- [x] Tuần 2 (code): lõi submodular, metric, script tái lập FALCON, notebook Colab (a)
- [x] Tuần 2 (chạy): embedding Defects4J trên Colab, so APFD với Bảng IV (median .737 so với .731)
- [x] Tuần 3: pipeline LRTS, baseline, kiểm tra với `eval_outcome` của LRTS, leakage v1
- [ ] Tuần 4: trích mã nguồn test theo build, embedding LRTS trên Colab (chế độ b)
