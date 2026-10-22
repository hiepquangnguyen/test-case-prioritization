# Artifact manifest

Kiểm tra cục bộ trong giai đoạn 1. Hai ZIP đã có, đã đọc và tính lại MD5/SHA-256.
MD5 khớp giá trị ghi nhận từ Zenodo ngày 2026-09-10; không xác nhận lại metadata
Zenodo trực tuyến trong lần audit này. Sinh báo cáo lúc 2026-10-14T11:28:30+07:00.

| Artifact | Bản ghi nhận | Bytes | MD5 |
| --- | --- | --- | --- |
| falcon.zip | FALCON v1 | 24089023 | a1cfd6c32eb5889c0e08f23872739aae |
| ML_TCSP.zip | DANTE v2 | 3590599893 | b268b21616f6ceb396e8df89d382f298 |

SHA-256:

```text
FALCON d60fa62edf1d1838185edf19e61146f5981895702f6a7afce0ab8c3f65ee36c8
DANTE  a99ffc38d0caf0c9362f6b762483e6bd453fe45ed4f6b981a6dca4464495748d
```

- FALCON: [Zenodo 18897073](https://zenodo.org/records/18897073),
  ZIP `artifacts/falcon/falcon.zip`; repository ghi nhận
  `https://github.com/anonymous-ing/falcon-icst-2026`. Chưa pin/đối chiếu commit
  GitHub; mã audit được pin bằng checksum ZIP. Metadata cũ có câu mô tả paper
  khác; code, README và dữ liệu trong ZIP đã được kiểm tra là gói FALCON.
- DANTE: [Zenodo 18900675](https://zenodo.org/records/18900675),
  ZIP `artifacts/dante/ML_TCSP.zip`; label v2 ghi nhận từ lần kiểm tra metadata.
  Chưa khẳng định đây là phiên bản mới nhất. Có LRTS raw đã xử lý và 50 JSON mẫu.
- Karaf source: `https://github.com/apache/karaf.git`; 18 SHA cho 20 build
  trong `reports/stage1/karaf-pilot-selection.json`.
- Encoder: `microsoft/unixcoder-base`, revision
  `5604afdc964f6c53782a6813140ade5216b99006`.

## License trong file đã đọc

- `falcon/LICENSE`: MIT, 2025 Twumasi Mensah-Boateng.
- `falcon/py/fast.py`, `lsh.py`: header GPL-3.0-or-later; không gán MIT cho toàn gói.
- `ML_TCSP/LICENSE.txt`: MIT, 2026 Simone Reale.
- `ML_TCSP/long_running_test_suites/LICENSE.txt`: MIT, 2024 lrtsuser.
- Karaf `LICENSE` tại `a45cb03f411863a1b65757b6c66dfcbaff9117df`: Apache License 2.0.

Đây là kiểm kê khai báo, không thay thế license riêng của model hoặc source
các dự án Java. Không xuất bản/phân phối lại artifact trong nhiệm vụ này.

## Trạng thái

Đã có audit dữ liệu và tự chạy smoke. Chưa tái lập toàn bộ thí nghiệm paper;
chưa có HC-FALCON. Những khác biệt metric, history, current duration và test
universe được ghi trong [báo cáo](../docs/01-feasibility/stage1-report.md).
Xem [archives.json](../reports/stage1/archives.json) để lấy metadata máy đọc được.
