# Hồ sơ Đính chính và Phả hệ Phiên bản Phase R (Remediation Amendment)

Hồ sơ này ghi nhận chính thức các thay đổi kỹ thuật, sửa chữa sai sót và phả hệ mã băm mật mã (cryptographic hash lineage) giữa các mốc niêm phong trước chạy (`run-freeze.json` tại T03, `bridge/manifest.json` tại T07) và bản niêm phong đóng phase chính thức (`evidence-freeze.json` tại T09) sau quá trình kiểm toán độc lập của người dùng.

---

## 1. Lý do đính chính và Các điểm phát hiện kiểm toán

1. **FINDING-01: Thuần túy hóa phép cắt ngưỡng Bridge Arm B & Minh bạch hóa Hoán vị Ranking**:
   - Trước sửa: Arm B tính lại ma trận cosine và gọi `fill_diagonal(1.0)`, gây sai lệch vi mô ($5.96 \times 10^{-7}$) trên 2.330.202 phần tử so với kernel A.
   - Sau sửa: Arm B nhận trực tiếp `np.clip(kernel_A, 0.0, 1.0)`, bảo đảm tính toán học thuần túy.
   - Bổ sung đối chiếu hoán vị: Làm rõ rằng hoán vị giữa A và B khác nhau tại 42 vị trí; giữa B và C khác nhau tại 24 vị trí. Tuy nhiên, toàn bộ 26 fault IDs đều được phát hiện đầu tiên ở cùng các thứ hạng chính xác, giải thích tại sao APFD bằng nhau tuyệt đối ($0.732278$).

2. **FINDING-02: Siết chặt xác thực Checkpoint Identity Key**:
   - Trước sửa: `key_ok` mặc định `True`, cho phép checkpoint cũ thiếu trường `identity_key` resume nếu số tests và batch size khớp.
   - Sau sửa: Khi caller yêu cầu `identity_key`, nếu checkpoint thiếu hoặc không khớp `identity_key` thì lập tức từ chối và bắt đầu lại sạch sẽ từ batch 0.

3. **FINDING-03: Hoàn thiện Rào chắn Kiểm toán Validator**:
   - Trước sửa: Bỏ sót lỗi nếu `input-manifest.json` không tồn tại; chưa đối chiếu mã băm các file nguồn trên đĩa; biểu thức so sánh APFD bị lọt nếu giá trị lưu là `NaN`; fixture kiểm thử dùng project giả lập thiếu fault matrix và file nguồn không tồn tại nên chưa đi vào nhánh so sánh APFD và kiểm tra sai hash thực sự.
   - Sau sửa: Bắt buộc có manifest đối với full suite; kiểm tra khớp 100% mã băm SHA-256 của `bbox_txt`, `mapping_json`, `fault_matrix_pickle` trên đĩa; kiểm tra số lượng mapping; chặn toàn diện các giá trị `NaN` hoặc không hữu hạn trong APFD. Bộ test được nâng cấp với fixture hợp lệ hoàn chỉnh (có fault matrix, mapping, file nguồn thực tế), xác minh độc lập: (1) baseline đạt 100%, (2) chỉ đổi APFD thành NaN sẽ kích hoạt đúng nhánh so sánh APFD và từ chối, (3) đổi hash của file thực sự tồn tại trên đĩa sẽ phát hiện sai lệch mà không bị lỗi thiếu file.

4. **FINDING-04: Bao phủ Toàn bộ Cây tiến trình (Process Tree) trong Driver**:
   - Trước sửa: Chỉ đo và kill PID trực tiếp, bỏ sót các tiến trình con.
   - Sau sửa: Quét toàn bộ cây tiến trình con qua Windows `CreateToolhelp32Snapshot`, tính tổng WorkingSetSize của toàn bộ cây và áp dụng `taskkill /F /T` khi vi phạm giới hạn. Bổ sung bài test tự động `test_kill_process_tree_terminates_parent_and_children` kiểm chứng việc dừng sạch sẽ cả tiến trình cha và toàn bộ tiến trình con.

5. **FINDING-05: Hồ sơ Nối phiên bản (Amendment Lineage)**:
   - Giữ nguyên các tệp freeze trước chạy làm hồ sơ lịch sử, đồng thời lập tài liệu amendment này để kết nối phả hệ mã băm sang `evidence-freeze.json` cuối cùng.

---

## 2. Bảng đối chiếu Phả hệ Mã băm (Hash Lineage Table)

| Tệp tin | Mã băm trước chạy (Freeze T03 / T07) | Mã băm sau sửa (Final Evidence Freeze) | Lý do thay đổi |
|---|---|---|---|
| [`scripts/stage10_reproduce.py`](../../scripts/stage10_reproduce.py) | `6278209841...` (T03) | `caa8b27dcc...` | Siết chặt xác thực `identity_key` checkpoint, từ chối checkpoint cũ thiếu thông tin. |
| [`scripts/stage10_validate.py`](../../scripts/stage10_validate.py) | `9038e1eccf...` (T03) | `4e79f3cd31...` | Bắt buộc manifest, đối chiếu hash file nguồn, kiểm tra mapping, lọc unixcoder, chặn NaN APFD, hỗ trợ root_dir. |
| [`scripts/stage10_driver.py`](../../scripts/stage10_driver.py) | `e57a4ecd9a...` (T03) | `b79f1c2ef6...` | Giám sát RSS theo toàn bộ process tree, hủy cây tiến trình bằng `taskkill /F /T`. |
| [`tests/test_stage10_reproduction.py`](../../tests/test_stage10_reproduction.py) | `dbf96220e6...` (T03) | `9706325a0b...` | 16 tests: bổ sung fixture hợp lệ hoàn chỉnh, kiểm tra NaN trên nhánh APFD thực, hash mismatch trên file tồn tại, và dừng cây tiến trình. |
| [`scripts/stage10_chart_bridge.py`](../../scripts/stage10_chart_bridge.py) | `a7b58d8065...` (T07) | `7a70cb3e3d...` | Cắt ngưỡng pure clip `np.clip(kernel_A, 0.0, 1.0)`, ghi nhận đối chiếu hoán vị ranking. |

---

## 3. Xác nhận các Thực nghiệm đã chạy lại

1. **Bridge Arms B và C**:
   - Nhánh B và Nhánh C đã được tính toán lại hoàn toàn trên kernel clip toán học thuần túy từ A.
   - Điểm số: A = `0.732278`, B = `0.732278` ($\Delta_{B-A} = 0.000000$), C = `0.732278` ($\Delta_{C-B} = 0.000000$), D = `0.763531` ($\Delta_{D-C} = +0.031253$).
2. **Xác minh 6 bộ Embedding**:
   - Toàn bộ 20.770 methods và 288 faults trên 6 dự án (Chart, Mockito, Lang, Math, Time, Closure) được giữ nguyên vẹn 100%, không re-encode, khớp tuyệt đối với CSV fault matrix và ranking đã lưu.
3. **Kiểm toán lại 6 dự án**:
   - Toàn bộ 6 dự án đã được chạy lại qua validator nghiêm ngặt mới và đạt `overall_valid: true`.
