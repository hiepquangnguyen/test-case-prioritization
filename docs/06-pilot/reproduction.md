# Pilot development HC-FALCON

Runner dùng nguyên implementation đã khóa ở giai đoạn 5. Scope gồm warm-up và
development Karaf/ActiveMQ/Log4j; chỉ development có ranking/metric. Không mở
reserved confirmation và không chạy nhánh Defects4J trong pilot này.

## Chạy

```powershell
$env:PYTHONHASHSEED='0'
& work/envs/falcon/Scripts/python.exe -B scripts/stage6_pilot.py --project karaf
& work/envs/falcon/Scripts/python.exe -B scripts/stage6_pilot.py --project activemq
& work/envs/falcon/Scripts/python.exe -B scripts/stage6_pilot.py --project log4j
& work/envs/falcon/Scripts/python.exe -B scripts/stage6_summary.py
```

Chạy từng project tuần tự để hạn chế nhiễu đo runtime. Không cần mạng: source,
diff và model đã có cục bộ. `PYTHONHASHSEED=0`, PyTorch CPU 4 threads, seed 0.
Runner kiểm tra stage4/stage5 hashes và exact selection/revision trước khi chạy.

Mỗi build development hợp lệ lưu checkpoint gzip gồm full inventory, source
mask/truncation, historical evidence, mọi ranking, metric và runtime.
`complete.json` chỉ xuất hiện sau khi runner xử lý hết cohort. Có thể gọi lại
cùng lệnh để tiếp tục; runner từ chối checkpoint có code/manifest khác.
Không đổi phương pháp giữa các checkpoint để ghép thành một lần chạy.

`stage6_driver.py` chạy tuần tự các bước còn thiếu và ghi `driver-status.json`,
stdout/stderr log. Nếu warm-up bị ngắt trước khi lưu cold-cost ledger,
`stage6_recover_cold.py` đo lại đúng các chi phí cold còn thiếu ở cache riêng;
giữ nguyên vector/ranking gốc và lưu `cold-recovery.json`. Karaf đã hoàn tất
trước lần tiếp tục ActiveMQ; đây không phải chạy lại hoặc tune kết quả Karaf.

## Thời gian và cache

Cache vector giai đoạn 6 tách khỏi cache smoke giai đoạn 5 để đo các cache miss
ban đầu. Warm-up được encode theo thời gian; vector cache được tái sử dụng khi
source không đổi. Các test dùng cùng compilation unit được encode một lần mỗi
build. Chi phí semantic preparation được tính lại vào từng semantic method;
không cho method chạy sau hưởng embedding miễn phí.

FAST signatures được chuẩn bị trước vòng 20 seed, và cùng chi phí đó được tính
cho từng seed; signature cache đi theo source qua các build. Đây là cache
representation, không phải reuse ranking. Runtime baseline lịch sử tính history
snapshot; DANTE tính source/diff/history và thời gian tính score riêng.

Cold overhead trong summary là **ước lượng dựng lại**: model load + source prep
+ tổng cold encoding time từng source riêng biệt đã đo khi cache miss + kernel
+ history + ranking. Không gọi đây là phép đo cold end-to-end trực tiếp cho từng
build. Nếu thời gian cold của một hash không có (ví dụ ngắt chạy trước khi lưu
cost ledger), không đưa build đó vào cold estimate và ghi số thiếu.

Warm overhead là thời gian thực quan sát trong replay, gồm miss khi source đổi.
Một lần resume có thể hưởng cache của phần build đã chạy dở; cần công bố resume
nếu sử dụng số runtime đó. Chi phí tải source/model ban đầu không nằm trong
runtime offline này; không suy thành latency CI thực tế.

Peak RSS lấy `PeakWorkingSetSize` qua Windows API cho cả process replay. Không
phân bổ peak của process chung thành peak độc lập của từng phương pháp.
Khi resume qua nhiều worker, summary lấy maximum của `complete.json` và mọi
development checkpoint để giữ cả đỉnh bộ nhớ của các worker trước. Thay đổi
tổng hợp này được ghi tại `analysis-amendment-v3.json`; ranking không đổi.

## Tổng hợp và kiểm chứng

`stage6_summary.py` kiểm tra lại full permutation và tính APFD/APFDc bằng công
thức độc lập từ checkpoint. No-failure giữ NA. Seed được lấy mean trong stage;
paired delta lấy trên stage có dữ liệu ở cả hai method rồi mean trong physical
build. Không nhân sample size bởi seed/stage.

Chỉ báo kết quả development mô tả và go/no-go đã chốt: median paired APFDc tăng
ít nhất 0,03 so với cả FL-only và History+cost ở ít nhất hai trong ba project;
kèm TTFF/Recall10. Engineering gate: peak RSS ≤8 GiB và p95 warm prep+ranking /
suite execution ≤10%. Không báo kiểm định confirmation trên development.

Engineering percentile cũng dùng physical build: mean seed trong stage, mean
stage ratio trong physical build rồi p95. `analysis-amendment-v2.json` ghi sửa
phép gộp này cho đúng protocol trước lần tạo summary đầu tiên; bản analyzer cũ
được giữ ở `reports/stage6/analysis-v1.py`. Ranking/alpha/cohort không thay đổi.
P95 theo stage vẫn lưu riêng như chẩn đoán, không dùng thay gate chính.

`stage6_replay_check.py` kiểm tra endpoints trên mọi checkpoint và tái dựng
first/last development build với mutation dữ liệu không đủ điều kiện sử dụng.
Alpha=0 có thể khác History+cost khi hai q khác nhau ở bit cuối bị phép chia Q
đưa về cùng float64; khi đó implementation dùng FQN đúng tie rule đã khóa.
Verifier chỉ chấp nhận phân loại này nếu mọi vị trí khác biệt có **w bằng nhau
chính xác**, và lưu metric hai thứ tự để đánh giá ảnh hưởng. Không báo strict
alpha-zero equivalence nếu có ngoại lệ; muốn bảo đảm tương đương tuyệt đối phải
chốt quy tắc số học cho phiên bản tiếp theo trước confirmation.

Alpha sensitivity dùng đủ 0/0,25/0,5/0,75/1; alpha chính vẫn 0,5. Kết quả raw,
normalized, ablation, Borda, FAST, DANTE và sáu baseline đều được giữ. Không tự
chọn alpha mới rồi gọi kết quả cùng development là xác nhận độc lập.
