"""Render the feasibility report from audit evidence, without rerunning experiments."""
import json
from datetime import datetime

from stage1_audit import ROOT, OUT


def read(name):
    return json.loads((OUT/name).read_text(encoding='utf-8'))


def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join('---' for _ in headers)+' |',*['| '+' | '.join(str(v) for v in row)+' |' for row in rows]])


def main():
    archives=read('archives.json')
    falcon=read('falcon-data-audit.json')
    checks=read('falcon-csv-pickle-check.json')
    authors=read('falcon-author-ranking-checks.json')
    projects=read('lrts-project-audit.json')
    coverage=read('lrts-coverage.json')
    source=read('karaf-source-summary.json')
    dante=read('dante-smoke.json')
    small=read('falcon-chart-first-16-smoke.json')
    full=read('falcon-chart-full-smoke.json') if (OUT/'falcon-chart-full-smoke.json').exists() else None
    history=read('karaf-history-crosscheck.json')['builds']
    processed=read('dante-processed-builds.json')
    generated=datetime.now().astimezone().isoformat(timespec='seconds')
    ntests=sum(r['tests'] for r in falcon)
    total=sum(r['tests'] for r in source['builds'])
    matched=sum(r['matched'] for r in source['builds'])
    source_failures=sum(r['failures'] for r in source['builds'])
    source_failing_matched=sum(r['failing_matched'] for r in source['builds'])
    ft=table(['Project','Test methods','Fault IDs','Source version','Mapping lỗi'],[(r['project'],r['tests'],r['faults'],', '.join(r['source_versions']),r['index_list_mismatches']+r['fault_keys_outside_suite']) for r in falcon])
    lt=table(['Project','Metadata rows','Raw có sẵn','Build/stage có fail','Duration = 0','Lệch count metadata','JSON mẫu'],[(r['project'],r['metadata_rows'],r.get('raw_builds',0),r.get('failing_builds',0),r.get('zero_duration',0),r.get('metadata_count_mismatches',0),r['processed_jsons']) for r in projects])
    full_text='Lượt full Chart chưa có kết quả hoàn tất trong bằng chứng hiện tại; không gán trạng thái đạt.'
    run_summary='Đã tự chạy DANTE trên một build và FALCON trên mẫu nhỏ.'
    if full:
        run_summary='Đã tự chạy DANTE trên một build, FALCON trên mẫu 16 test và toàn bộ 2.193 test Chart.'
        measured=read('falcon-chart-full-cold-run.json') if (OUT/'falcon-chart-full-cold-run.json').exists() else full
        comparable=[r for r in authors if r['project']=='Chart' and 'unixcoder-cosine' in r['archive_member']]
        author_score=comparable[0]['author_apfd'] if comparable else None
        full_text=f"""Full Chart: **{full['tests']} test**, APFD tính độc lập **{full['apfd']:.9f}**;
embedding lần đầu {measured['embedding_seconds']:.2f} s (cache hit: {measured['embedding_cache_hit']}),
similarity {measured['similarity_seconds']:.2f} s, ranking {measured['ranking_seconds']:.2f} s.
APFD tác giả trong cấu hình Chart/UniXcoder/cosine: **{author_score}**.
Chênh lệch APFD là **{full['apfd']-author_score:+.9f}** (thang 0–1).
Chạy được pipeline nhưng **chưa tái lập chính xác số của tác giả**. Không diễn
giải chênh lệch là cải tiến phương pháp; chưa xác định nguyên nhân và không
chỉnh preprocessing theo kết quả.
Model revision, dependency và phần cứng không được coi là giống môi trường paper.
Similarity nhỏ nhất {full['similarity_min']:.6f}, số phần tử âm {full['negative_similarities']}.
Đây là vi phạm điều kiện đầu vào similarity không âm của đề xuất HC-FALCON,
không phải chứng minh trực tiếp ranking FALCON hiện tại sai. Cần định nghĩa
biến đổi similarity trong protocol, giữ baseline nguyên bản riêng.
Ranking và gain tự chạy: `work/runs/falcon/chart-full/`. Thời gian lần đầu được
giữ riêng trong `falcon-chart-full-cold-run.json`; lượt kiểm tra lại dùng cache
embedding để xác nhận exit code bằng cách ghi log subprocess trực tiếp."""
    report=f"""# Báo cáo giai đoạn 1 — khả thi dữ liệu và artifact

Sinh từ bằng chứng cục bộ lúc {generated}. Phạm vi: FALCON/Defects4J và
DANTE/LRTS; không triển khai HC-FALCON, không đánh giá giả thuyết hiệu quả.

## Kết luận

**Có thể bắt đầu xây bộ dữ liệu/protocol và lõi HC-FALCON, nhưng chưa đủ điều
kiện dùng nguyên DANTE làm baseline rolling công bằng.** Source Karaf đã truy
cập được tại các commit metadata. Cần khóa xử lý test thiếu/ambiguous, duration
ước lượng, lịch sử theo thời điểm hoàn tất và metric chung trước thực nghiệm.

Đã kiểm tra hai ZIP, {ntests:,} test methods của FALCON, {coverage['metadata_rows']:,}
metadata rows LRTS, {coverage['processed_jsons']} processed JSON và source của 20
build Karaf. {run_summary}
Trạng thái full Chart nằm ở mục FALCON dưới đây, không suy từ kết quả tác giả.

## 1. Artifact và môi trường

- MD5 cả hai ZIP khớp manifest; SHA-256 trong [archives.json](../../reports/stage1/archives.json).
- FALCON ZIP có {archives[0]['entries']:,} entries; DANTE {archives[1]['entries']:,},
  tổng kích thước giải nén DANTE {archives[1]['uncompressed_bytes']/1e9:.2f} GB.
- Hai venv riêng, Python {small['python']}; PyTorch CPU, 4 luồng, không CUDA.
  `pip check` đạt cho cả hai môi trường. Lock: [FALCON](../../reports/stage1/falcon-environment.txt),
  [DANTE](../../reports/stage1/dante-environment.txt).
- DANTE root requirements và pyproject khác nhau; smoke prioritization dùng
  root requirements. Không xác nhận solver selection hoặc ML baseline.
- FALCON root LICENSE là MIT; FAST/lsh có header GPL-3.0-or-later. DANTE và
  LRTS có file MIT riêng. Giữ khai báo từng thành phần, không gán MIT cho tất cả.
- Karaf `LICENSE` tại commit đầu mẫu `a45cb03f411863a1b65757b6c66dfcbaff9117df`
  ghi Apache License 2.0.
- Kết quả gốc giữ trong ZIP; `work/runs/` là kết quả tự chạy. Code upstream
  trích xuất giữ nguyên. Một số stage Kafka có `:`; audit đọc trực tiếp ZIP.

## 2. FALCON / Defects4J

{ft}

Tổng cộng **{sum(r['faults'] for r in falcon)} fault IDs** giữa sáu project.
Mỗi project có một suite trích xuất từ đường dẫn `*_1f` và fault matrix nhiều
cột phiên bản lỗi. Đây là dữ liệu artifact tổ chức ở mức project; chưa chứng
minh quá trình chạy từng phiên bản từ một Defects4J checkout mới.

- Không có dòng bbox rỗng hoặc test identifier trùng. Có source giống nhau ở
  các test ID khác nhau; giữ các ID, không tự deduplicate theo nội dung source.
- Mapping và index list khớp; fault key nằm trong suite.
- So source trích xuất với bbox sau chuẩn hóa whitespace: {sum(r['source_to_bbox_mismatches'] for r in checks)} sai lệch.
- So CSV fault matrix với pickle: {sum(r['csv_to_pickle_mismatches'] for r in checks)} sai lệch.
- {len(authors)} ranking FALCON của tác giả đều là hoán vị đầy đủ; tính lại
  APFD độc lập khớp TSV (sai lệch tối đa {max(r['absolute_difference'] or 0 for r in authors)}).
  Đây là kiểm chứng output có sẵn, không phải tự chạy {len(authors)} thí nghiệm.
- ZIP chỉ có timing JSON cho embedding, không chứa vector `.npy`.

### Tự chạy

Mẫu 16 test dùng encoder pin `5604afdc964f6c53782a6813140ade5216b99006`:
embedding 16×768 hữu hạn, standard/lazy greedy cùng thứ tự; không chấm APFD
full suite cho mẫu này. Gọi hàm artifact trực tiếp qua wrapper CPU để tránh
runner hardcode `python3 --device cuda` và skip vì output đã tồn tại.

{full_text}

Bằng chứng tự chạy: [smoke 16 test](../../reports/stage1/falcon-chart-first-16-smoke.json).
Kết quả full suite nằm trong `reports/stage1/falcon-chart-full-smoke.json` khi
lượt chạy hoàn tất; [verification](../../reports/stage1/verification.json) ghi
trạng thái kiểm tra cuối.

### Điểm cần giữ trong protocol

`submodtcp.py` dùng raw cosine chưa chặn âm; giá trị không âm trên một mẫu
không chứng minh mọi đầu vào đều không âm. Hàm embedding lấy mean trên cả
padding positions. Batch size/padding có thể ảnh hưởng representation; không
âm thầm đổi khi gọi là baseline tái lập. Lazy greedy upstream tính lại coverage
từ subset mỗi lần, chưa lưu vector coverage như lõi HC-FALCON dự kiến.

## 3. DANTE / LRTS

{lt}

Một row là **project + PR + build + stage**; không đồng nhất tổng row với số
build CI độc lập. Bảng thống kê toàn bộ row trong metadata đã cung cấp; chính
dataset đã được upstream lọc, không đại diện mọi build CI ban đầu.

- Raw CSV được kiểm tra outcome, duration, ID trùng, số test/fail so metadata.
  Chi tiết: [project audit](../../reports/stage1/lrts-project-audit.json),
  [build audit](../../reports/stage1/lrts-build-audit.csv).
- Tất cả metadata row có raw CSV tương ứng; không thấy duration âm/không hữu
  hạn hoặc outcome ngoài 0/1 trong raw đã kiểm tra. Có duration bằng 0 ở cả
  mười dự án. Điều này không chứng minh raw giữ đầy đủ skipped/cancelled:
  upstream đã tổng hợp và lọc trước khi đóng gói.
- Quét {sum(r['tests'] for r in projects):,} test observations trong {coverage['metadata_rows']:,}
  CSV được metadata tham chiếu. ZIP còn các raw CSV ngoài metadata; chưa audit
  nội dung các file ngoài tập tham chiếu này.
- TVM có 26.833 row lệch số test/fail giữa raw và metadata; chưa kết luận
  nguyên nhân. TVM không nằm trong ba ứng viên Java và không đưa vào pilot.
- Chỉ có 5 processed JSON mỗi project. Tổng số test records có tokens:
  {sum(r['tokens_available'] for r in processed)}; không coi tokens là source Java.
  Relevance có trong mẫu dùng `tfidf`; mặc định config `bm25` không khớp.
- Không có file Java độc lập trong ZIP. Source cho HC cần lấy đúng commit.
- Không coi `last_outcome` và `last_outcome_N` là cùng semantics: raw giữ
  outcome quan sát gần nhất theo class/stage; augmentation đi qua danh sách
  processed JSON đã lọc và điền 0 khi thiếu test/build.

## 4. Source mapping và chronology Karaf

Quy tắc mẫu: 20 metadata row đầu theo timestamp, PR, build, stage; không lọc
theo fail. Có {source['unique_commits']} commit khác nhau, đều fetch được từ
`apache/karaf`. Không chạy test hoặc build mã Java.

- Mapping xác minh package/class: **{matched}/{total} ({matched/total:.2%})** lượt test.
- Failing records có source: **{source_failing_matched}/{source_failures}**.
- `OsgiLocatorTest` xuất hiện ở hai module (`specs/activator`, `specs/locator`):
  giữ ambiguous; log class-level không đủ để chọn một module tùy ý.
- Failure chưa map là `org.apache.maven.surefire.junit4.JUnit4Provider` ở
  PR-1287/build1. Tên gợi ý lỗi bộ chạy; chưa đủ bằng chứng phân loại chính
  thức, không tự xóa khỏi tập failure.
- Một số class không có trong tree của SHA metadata. Chưa chứng minh SHA
  metadata là chính xác revision thực thi sau merge CI; đây là giới hạn cần
  đối chiếu raw build/test report nếu mở rộng tuyên bố về source.
- Có {sum(r['not_completed_under_start_plus_duration']>0 for r in history)} / 20 row mà ít nhất một build bắt đầu trước
  còn chưa hoàn tất theo `timestamp + duration`. Upstream collector chia
  Jenkins timestamp/duration cho 1000; raw build JSON chưa được kiểm tra vì
  không thấy trong các thư mục metadata/testdata đã đóng gói. Cutoff completion
  vẫn cần xác nhận semantics, xử lý tie và các stage cùng build.
- Các JSON có trong mẫu có {sum(r.get('history_field_disagreements_with_previous_raw_builds') or 0 for r in history)} history lag khác so với chuỗi raw
  start-time. Đây là chênh lệch định nghĩa lịch sử, không tự là chứng minh
  future leakage. Không dùng sẵn history này cho HC-FALCON.

Bằng chứng: [source summary](../../reports/stage1/karaf-source-summary.json),
[mapping từng test](../../reports/stage1/karaf-source-mapping.csv),
[history crosscheck](../../reports/stage1/karaf-history-crosscheck.json).

## 5. Smoke DANTE và các vấn đề đã tái hiện

Chọn PR-1287/build1: processed build Karaf sớm nhất có raw history, 4 history
rows. Runner nguyên bản chạy được với override đường dẫn, một target và
`tfidf`. Không sửa thuật toán của tác giả.

| Kiểm tra | Kết quả |
|---|---|
| Test trong đầu vào | {dante['original_tests']} |
| Test được runner xếp hạng | {dante['ranked_tests']} |
| Test bị loại | {dante['excluded_tests']}, gồm {dante['excluded_failures']} failure |
| APFDc theo artifact, trên universe đã lọc | {dante['artifact_apfdc']:.9f} |
| APFDc midpoint, cùng universe | {dante['midpoint_apfdc']:.9f} |
| Đổi duration hiện tại làm đổi score DANTE | {dante['current_duration_changes_dante_score']} |

Không dùng hai APFDc này làm ước lượng hiệu quả toàn suite. Cả hai chấm trên
206 test còn lại, không trên 212 test ban đầu.

Các vấn đề cụ thể trong `run_prioritization.py`:

1. `calculate_all_scores` lọc test theo `source_file_found` và duration hiện
   tại; `calculate_hybrid_scores` chia score cho duration hiện tại. Đã tái
   hiện việc đổi duration làm đổi score.
2. APFDc dùng midpoint rồi cộng thêm `1/(2n)`; không-failure trả 1. Cần một
   evaluator chung, xử lý NA và tập failure cố định. Báo metric gốc riêng.
3. `groupby(...).shift(1).rolling(...)` áp rolling sau groupby nên có thể
   đi qua ranh giới class. Witness A:[1,0], B:[0,0] khiến quan sát đầu B có
   sticky=1 từ A. Đây là kiểm tra biểu thức code, chưa lượng hóa ảnh hưởng
   trên toàn dataset.
4. `augment_history.py` chỉ đi qua processed builds và dùng 0 khi thiếu;
   không đủ cho semantics unknown và rolling history đầy đủ.
5. LTR output trong smoke là placeholder -100 do fixture không có ML history;
   **không phải baseline LTR đã tái lập**. Không đưa vào bảng so sánh nghiên cứu.

Chi tiết chạy và diagnostics: [dante-smoke.json](../../reports/stage1/dante-smoke.json).

## 6. Dataset pilot và điều kiện chuyển giai đoạn

Đề xuất **Karaf** để hoàn thiện adapter trước: repository nhỏ, đã kiểm tra
20 build và chạy được DANTE. **ActiveMQ và Log4j** là hai ứng viên Java tiếp
theo dựa trên số row vừa phải và raw data có sẵn; chưa xác nhận source mapping
toàn bộ cho hai dự án này. Không chọn vì score HC-FALCON (chưa có score).

20 build Karaf hiện tại chỉ là mẫu feasibility, chưa phải holdout đánh giá.
Mẫu có build ABORTED và inventory thay đổi; cần quy tắc inclusion trước pilot.
Khoảng warm-up/calibration/evaluation sẽ chốt sau khi kiểm tra nguồn đầy đủ,
không lấy best result trên khoảng này rồi gọi là đánh giá độc lập.

| Việc cần làm ở giai đoạn 2 | Tiêu chí |
|---|---|
| Chốt inventory, ID và source fallback | Không làm biến mất test/failure vì thiếu source; ghi riêng framework errors và ambiguous module. |
| Dựng rolling history từ raw | Unknown khác PASS; chỉ dùng outcome đã có tại cutoff, xét stage/branch và rename. |
| Dựng runtime estimate | Dùng quá khứ/fallback, không lấy actual duration hiện tại để ranking. |
| Adapter baseline và metric | Cùng universe/cutoff; giữ kết quả artifact gốc để đối chiếu. |
| Chốt HC-FALCON v1 | Similarity không âm, estimator/confidence/cost/alpha cố định, tuning chỉ trên quá khứ. |

## 7. Tái lập và giới hạn

Lệnh tại [reproduction.md](reproduction.md). Audit có thể chạy lại mà không
download dataset. Model và source fetch cần mạng lần đầu. Không clone đầy đủ
Defects4J, không chạy test Java từng fault version, không kiểm chứng giấy phép
mọi thành phần phụ thuộc và không đánh giá novelty trong giai đoạn này.

Các scripts/report là sản phẩm mới của dự án; bộ reading guide trước đây là
tài liệu lịch sử và có thể còn câu "chưa kiểm tra artifact". Trạng thái hiện
tại lấy theo báo cáo này và evidence JSON, không sửa lại lời giải thích paper.
"""
    (ROOT/'docs/01-feasibility/stage1-report.md').write_text(report,encoding='utf-8')
    manifest=f"""# Artifact manifest

Kiểm tra cục bộ trong giai đoạn 1. Hai ZIP đã có, đã đọc và tính lại MD5/SHA-256.
MD5 khớp giá trị ghi nhận từ Zenodo ngày 2026-09-10; không xác nhận lại metadata
Zenodo trực tuyến trong lần audit này. Sinh báo cáo lúc {generated}.

{table(['Artifact','Bản ghi nhận','Bytes','MD5'],[(a['path'].split('/')[-1] if '/' in a['path'] else a['path'].split(chr(92))[-1],v,a['bytes'],a['md5']) for a,v in zip(archives,['FALCON v1','DANTE v2'])])}

SHA-256:

```text
FALCON {archives[0]['sha256']}
DANTE  {archives[1]['sha256']}
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
"""
    (ROOT/'references/artifact-manifest.md').write_text(manifest,encoding='utf-8')
    print('Wrote report and manifest. Full Chart complete:',full is not None)


if __name__=='__main__':
    main()
