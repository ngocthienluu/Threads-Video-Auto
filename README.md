# Threads Video Studio

## Reply screenshots

For a Thread reply screenshot that contains only the new reply, enable **Image contains only the new reply** in **Comment / Voice**. Review spelling then updates automatic TTS. Leave this off for cumulative screenshots; manually edited TTS stays protected. Check that the question comes before its replies.

## Visual editor V1 (2026-09-14)

1. Import screenshots; select a comment in **Scenes**. Use **Comment / Voice** for the existing OCR and narration controls.
2. Return to **Canvas**. Click and drag the screenshot or watermark; drag a blue corner to resize proportionally. **Inspector > Transform / Style** edits exact coordinates, size, rotation, opacity and watermark font size.
3. **Layers** selects objects and controls visibility, locking and front/back order. **Delete** removes only the selected overlay, keeping its comment/audio; Undo restores it. Gameplay geometry is fixed and locked.
4. **Project** contains compact OCR, Gameplay, Music, Watermark and timing sections. Screenshot width/Y settings are defaults for new objects (or Reset Transform), not overrides of an edited object.
5. Generate current narration for every comment to populate the **AUTO timeline**. Click/drag the playhead to scrub; click a clip to select it. Zoom changes pixels per second; long timelines scroll horizontally. Without valid audio, the canvas remains usable for authoring and the timeline stays pending.
6. **Ctrl+S** saves object transforms in project JSON. **Ctrl+Z**, **Ctrl+Shift+Z / Ctrl+Y** undo/redo canvas edits. Delete is scoped to the canvas so text editing remains safe. Undo history is session-only and clears on project load.
7. Export reads the same object position, scale, rotation, opacity and layer order. Safe-area/snap guides are editor-only. Existing JSON projects acquire default objects when opened; save to retain them. Older app versions may reject these new fields.

**Preview boundary:** this is a layout/state editor, with an explicitly labelled gameplay placeholder. It does not play gameplay, music or narration in sync. Open the exported MP4 to review motion/audio. Manual clip move/trim/split, keyframes, meme/SFX/text creation, waveform and realtime playback remain V2 work; the empty Meme/SFX track contains no fabricated clips. Auto Generate Text still makes no paid TTS requests.

## Xuất video MP4

1. Chuẩn bị audio cho **tất cả comment**; item còn pending/error phải Generate Voice trước.
2. Bên phải, **Gameplay → Browse** chọn video nền. Loop bật mặc định; Volume = 0 để tắt tiếng gameplay.
3. Tùy chọn bật **Music**, chọn nhạc; chỉnh watermark, kích thước/vị trí ảnh và khoảng nghỉ.
4. Bấm **EXPORT**, chọn file `.mp4` (mặc định trong `output/`). Có **Cancel Export**; hủy/lỗi giữ nguyên bản xuất cũ.

Export uses local FFmpeg and does not call TTS. Default output is 1080x1920 at 30 fps, H.264/AAC. Canvas previews object layout and timeline state; open the MP4 for actual gameplay/audio playback.


## Tạo giọng đọc

1. Dùng **Tesseract**, đọc ảnh rồi kiểm tra **TTS Text** (reply chỉ giữ phần lời mới).
2. Điền `ELEVENLABS_API_KEY` vào `.env` trên máy, không gửi key qua chat. Có thể đặt `ELEVENLABS_VOICE_ID` làm giọng mặc định. Mở lại app sau khi đổi cấu hình.
3. Bấm **Refresh Voices**, tìm theo tên/ngôn ngữ/accent và chọn giọng; chọn tốc độ 0.7–1.2. Nếu cần nhập ID, mở **Advanced voice settings → Voice ID**.
4. Bấm **Generate Voice (ElevenLabs)**. Khi chưa có cache, app gửi TTS Text tới ElevenLabs và có thể sử dụng credits của tài khoản. OCR/import/Auto Generate Text không tự tạo giọng.
5. **Open generated audio** mở file bằng trình nghe mặc định. Khi mọi item có audio hợp lệ, timeline hiển thị tổng thời lượng và lưu mốc thời gian.

**Kiểm tra quyền dùng giọng:** danh sách giọng không bảo đảm tài khoản được phép tạo audio qua API. Bấm **Test Voice** để gửi mẫu ngắn “Xin chào”; mỗi lần bấm có thể dùng credits. Test không thay audio hoặc lời đọc của comment. Trạng thái ban đầu là **API access not confirmed**; sau một yêu cầu tạo giọng mới thành công trong phiên hiện tại sẽ hiện **Available via API**. Dùng lại audio cache không xác nhận quyền API hiện tại. Một số giọng có giới hạn theo tài khoản/gói; [hướng dẫn ElevenLabs](https://help.elevenlabs.io/hc/en-us/articles/33569002955153-Why-can-t-I-use-some-voices-from-the-Voice-Library).

**Giọng mặc định:** chọn giọng rồi bấm **Set selected as project default**. Mỗi comment có thể chọn **Use Default** hoặc giọng riêng. Bấm Save để lưu vào project; không phải sửa `.env` mỗi lần đổi giọng. `.env` ở cùng cấp README.md/run.bat, được tạo bằng cách sao chép `.env.example`; key chỉ điền trong `.env`. API Key trên UI chỉ báo Configured/Not configured.

**Cache danh sách:** `cache/tts/elevenlabs_voices.json` lưu metadata và thời điểm tải, không chứa key. App mở danh sách cache khi khởi động; nếu Refresh thất bại, danh sách cũ vẫn dùng được kèm cảnh báo. Trạng thái quyền dùng giọng trở về chưa xác minh khi mở lại app hoặc đổi model.

**Tạo lại:** Generate Voice dùng lại cache nếu đầu vào giống nhau. Muốn yêu cầu tạo audio mới, mở **Advanced voice settings → Regenerate Voice (new API request)**; thao tác này có thể dùng credits. Nếu thất bại, audio cũ vẫn còn. Sau khi đổi giọng/tốc độ/model, audio cũ chỉ dùng để nghe lại, không tính vào timeline cho đến khi tạo audio phù hợp.

Lỗi 402 báo giới hạn tài khoản/gói/quyền API; 401 báo key không hợp lệ; 403 báo không đủ quyền; 429 báo giới hạn request/quota. Chi tiết hướng dẫn được giữ ở khu vực Voice, không chỉ hiện popup. App không tự retry hoặc thử toàn bộ giọng. **Iteration chọn/test giọng: integration test not performed**; kiểm thử dùng HTTP giả lập và UI offscreen.

```dotenv
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id
ELEVENLABS_MODEL_ID=eleven_flash_v2_5
FFPROBE_PATH=ffprobe
```

Mỗi dòng `.env` là `KEY=value`, có thể bao giá trị bằng dấu nháy; chưa hỗ trợ nội suy/comment ở cuối dòng. Biến môi trường có ưu tiên cao hơn. Flash v2.5 hỗ trợ tiếng Việt theo [tài liệu ElevenLabs](https://elevenlabs.io/docs/overview/models); chưa kiểm chứng chất lượng phát âm với tài khoản thật.

Máy hiện tại đã có ffprobe ở `tools/ffmpeg/bin/`, được app tìm tự động. Checkout mới: xem [hướng dẫn công cụ](tools/ffmpeg/README.md) hoặc đặt FFPROBE_PATH tới ffprobe.exe. App kiểm tra công cụ trước khi gửi yêu cầu tạo giọng.

Cache nằm ở `cache/tts/`, phân biệt text, giọng, tốc độ, model và định dạng. Bấm lại cùng đầu vào dùng cache. Đổi text/giọng/tốc độ làm audio item trở về pending. Cache hỏng báo lỗi, không tự gọi lại API. Cancel Voice giữ text/audio cũ, có thể chờ network timeout (20 giây); yêu cầu đã tới dịch vụ có thể vẫn bị tính phí. Không tự retry API. Đóng cửa sổ khi đang tạo giọng sẽ hủy và đợi worker kết thúc.

Text rỗng hoặc OCR/reply chưa chắc chắn bị chặn; kiểm tra và chỉnh TTS Text để đánh dấu đã sửa tay. Tạo giọng không ghi đè text đã sửa.

Ứng dụng desktop Windows tạo video dọc từ screenshot bình luận, gameplay và giọng đọc. **Hiện tại:** Tesseract là OCR mặc định; app tách comment/reply, chuẩn bị TTS Text và tích hợp tạo giọng ElevenLabs, cache audio và timeline theo thời lượng ffprobe. EXPORT MP4 đã được triển khai với gameplay, nhạc và watermark.

Validation: **134 tests pass**, including local OCR, offscreen UI, mocked TTS, actual ffprobe and FFmpeg exports. Editor tests compare rendered MP4 pixels with Qt canvas transforms. No live ElevenLabs call or human listening review was performed for this iteration.

## Cài đặt

Python **64-bit 3.11–3.13**, Windows 10/11, môi trường ảo và PySide6. OCR dùng Pillow + tesserocr Windows wheel có sẵn thư viện Tesseract, không cần cài tesseract.exe riêng. Từ thư mục dự án:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m app.services.ocr.setup
Copy-Item .env.example .env
.\run.bat
```

Hoặc chạy `.\.venv\Scripts\python.exe -m app.main`. OCR không cần API key. Tạo giọng cần ElevenLabs và ffprobe; `.env` hiện được đọc cho cấu hình TTS, biến môi trường có ưu tiên cao hơn. Không đưa key vào JSON dự án.

**Máy hiện tại đã cài dependency và dữ liệu OCR:** đóng app cũ rồi chạy lại `run.bat`. Lệnh setup chỉ cần khi cài mới hoặc dữ liệu bị thiếu/hỏng. Setup tải `vie`/`eng` từ kho Tesseract chính thức theo commit cố định và kiểm SHA-256; OCR sau đó chạy offline, không gửi ảnh ra ngoài. Dữ liệu ở `assets/ocr/tessdata/`, kết quả cache ở `cache/ocr/`. Windows wheels được cố định phiên bản/hash theo [nguồn được tesserocr hướng dẫn](https://github.com/sirfz/tesserocr#windows).

## Sử dụng hiện tại

**Dọn audio thừa:** mở **Tools → Dọn audio thừa**. App kiểm tra project đang mở (kể cả chưa Save), các file JSON trong `projects/` và những project đã Save/Open qua app từ phiên bản này. Danh sách hiện số file/dung lượng; bấm **Xóa audio thừa** để dọn. Audio vẫn được bất kỳ project nào tham chiếu sẽ được giữ, kể cả bản giọng cũ đang gắn với item. Mẫu Test Voice và các bản tạo thử không còn tham chiếu có thể được dọn.

Nếu có project lưu ở nơi khác từ trước, dùng **Thêm project ở nơi khác** trước khi dọn. Project lỗi/không đọc được sẽ chặn việc xóa. Chỉ xóa MP3 cache do app tạo; giữ OCR, danh sách voice và media gốc. Xóa audio cache rồi muốn dùng lại có thể cần tạo giọng lại và dùng credits. Dọn này giải phóng dung lượng ổ đĩa; không tự chạy khi đóng app.

- IMPORT / Add Single: mỗi ảnh tạo một Single Scene.
- Add Thread: chọn screenshot câu hỏi trước; Add Thread Item thêm ảnh chứa câu hỏi và reply kế tiếp. Move Up/Down sắp xếp scene hoặc reply; role được cập nhật theo thứ tự.
- Chọn item → **READ IMAGE → Detect comment → TTS text**. App tự loại header/footer theo vị trí và điền **Detected Comment**, sau đó làm sạch thành **TTS Text**. Trường hợp bình thường không cần select text.
- **AUTO GENERATE TEXT** xử lý toàn bộ scene theo thứ tự, chỉ chuẩn bị text; chưa tạo voice. Chọn reply rồi Read Image sẽ xử lý cả các item trước đó để có ngữ cảnh.
- Thread giữ nội dung tích lũy ở Detected Comment, nhưng TTS Text chỉ nhận reply mới qua fuzzy prefix diff. Không tìm được overlap đáng tin cậy thì để lời reply tự động trống và báo **Review detected text**, không đọc lại câu hỏi.
- Confidence >=80%: Comment detected; 60–79%: có cảnh báo ở Advanced; <60% hoặc không có reply mới: cần review. Đây là điểm heuristic, không đảm bảo dấu/chính tả OCR đúng. Có thể sửa Detected Comment hoặc TTS Text khi cần.
- Text sửa tay được bảo vệ, kể cả text cố ý để trống. Read Image/Auto Generate không ghi đè body/TTS thủ công. Sửa body sẽ cập nhật TTS tự động nếu TTS chưa sửa tay.
- **Advanced / Show raw OCR** chứa raw text chỉ đọc, method/warnings, **Manual Selection → TTS**, Clean và **Re-run extraction**. Re-run cho phép thay body thủ công của item đang chọn nhưng vẫn giữ TTS thủ công. Muốn thay TTS thủ công bằng Clean/Selection phải bật checkbox cho phép riêng.
- Trong lúc xử lý, editor/project tạm khóa; **Cancel OCR** vẫn hoạt động. Đóng cửa sổ hủy tác vụ rồi hỏi lưu. Khi hủy batch, kết quả đã hoàn thành vẫn được giữ; lời tự động phụ thuộc có thể được tính lại. Text thủ công luôn được giữ.
- Save/Open lưu JSON UTF-8 có version và đường dẫn tương đối với file dự án khi cùng ổ đĩa. Giữ các file media bên ngoài; ứng dụng báo khi chúng bị thiếu.
- PREVIEW remains a static screenshot view. EXPORT writes composed MP4 with gameplay, screenshots, narration, optional music and watermark.
- Delete/Move Up/Move Down thao tác trên dòng được chọn. App hỏi lưu trước khi đóng hoặc mở dự án khác nếu có thay đổi.

## Media và render tương lai

Đặt video ở `assets/backgrounds/`, nhạc ở `assets/music/`, meme ở `assets/memes/`, SFX ở `assets/sfx/`, font ở `assets/fonts/`. `input/comments/` là nơi tùy chọn để giữ screenshot; `projects/` chứa JSON; `output/` dành cho MP4. Cache và logs là dữ liệu runtime.

Final export uses local FFmpeg/ffprobe from tools/ffmpeg/bin or PATH. This machine has verified FFmpeg 9.0.1; see tools/ffmpeg/README.md for setup. FFMPEG_PATH/FFPROBE_PATH environment variables can override discovery.

## Kiểm thử và xử lý lỗi

```powershell
.\.venv\Scripts\python.exe -m unittest discover -v
$env:QT_QPA_PLATFORM = 'offscreen'
.\.venv\Scripts\python.exe -m app.main --smoke-test
```

Xóa biến `QT_QPA_PLATFORM` trước khi chạy GUI bình thường (`Remove-Item Env:QT_QPA_PLATFORM`). Thiếu PySide6: cài requirements bằng đúng Python trong `.venv`. Ảnh lỗi/không đọc được sẽ bị từ chối. JSON lỗi không thay thế dự án đang mở. Lỗi quyền ghi cần chọn thư mục có quyền ghi. Xem `logs/app.log`; không log API key hoặc nội dung TTS.

OCR thiếu dữ liệu: chạy lại setup. Lỗi dependency: cài requirements với Python Windows 64-bit 3.11–3.13. OCR timeout 60 giây, giới hạn 20 megapixels. Layout lạ, ảnh nhỏ/mờ, header/timestamp bị OCR sai hoặc thread bị crop mất câu hỏi có thể cần chỉnh tay. Lỗi dấu vẫn có thể tồn tại dù điểm layout cao. Không có LLM/API parsing.

ROI/thresholds ở `ExtractionSettings` trong `app/core/config.py`, lưu theo project; vùng mặc định là prior có thể mở rộng theo layout, không crop cứng. `ocr_debug_save_regions` mặc định false; bật trong config/project sẽ lưu debug body crop ở cache/ocr. Raw view mặc định ẩn. Project cũ được nạp với defaults; body/TTS thủ công được giữ. Các test OCR thật tự skip nếu chưa có engine/model, nên luôn kiểm tra số skip.

## Tài liệu

[Đặc tả](docs/PRODUCT_SPEC.md) · [Kiến trúc](docs/ARCHITECTURE.md) · [Lộ trình](docs/ROADMAP.md) · [Tiến độ thực tế](docs/PROGRESS.md) · [TODO](docs/TODO.md) · [Quyết định](docs/DECISIONS.md) · [Hướng dẫn phát triển](docs/DEVELOPMENT_GUIDE.md). Đọc AGENTS.md trước khi sửa code.

## OCR media screenshots and spelling review (2026-09-08)
Restart the app, select cmt4/cmt5 and press READ IMAGE (or AUTO GENERATE TEXT) to refresh OCR using the new cache version. Re-run extraction alone reuses stored OCR. Detected Comment now includes the caption above the attachment. Use **S?a ch?nh t? / Review spelling** to preview local phrase suggestions, edit additional mistakes and Save or Cancel. Saving marks the body as manual and updates automatic TTS only; manually edited TTS remains protected. This is a limited phrase helper, not a general Vietnamese grammar model. Raw OCR remains available in Advanced.

## PaddleOCR alternative (current provider configuration)

The application now selects OCR through `app/services/ocr/settings.py`:

```python
ocr_provider: str = "tesseract"          # or "paddle"
ocr_fallback_provider: str = "tesseract" # "" disables fallback
paddle_language: str = "vi"
paddle_enable_mkldnn: bool = False       # CPU compatibility on this Windows setup
paddle_timeout_seconds: float = 300.0
```

Use the **OCR Engine** dropdown at the top of the right settings panel to switch between PaddleOCR and Tesseract without restarting. The selection lasts for the current app session; startup still uses runtime config. Press READ IMAGE or AUTO GENERATE TEXT to run the selected engine. Switching alone does not modify text or run OCR. The selector is disabled while OCR is busy. Re-run extraction reuses previously stored OCR and does not compare engines. Manual body/TTS protection is unchanged.

Install the updated requirements in the project environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

The added versions are official `paddleocr==3.7.0` and CPU `paddlepaddle==3.3.1`. A Windows x64 CPython 3.13 wheel is available and selected by pip on this machine (Python 3.13.1 AMD64). Other Python/OS/CPU combinations have not been integration-tested here; consult the [official Windows installation guide](https://www.paddlepaddle.org.cn/documentation/docs/zh/install/pip/windows-pip_en.html) before changing environments. GPU/CUDA is not required. These dependencies are substantially larger than the original Tesseract setup.

First Paddle use initializes PP-OCRv5 with Vietnamese (`vi`) and may download detector/Latin recognition models. Allow network access and extra startup time (default timeout 300 seconds, including download). Models are cached under `cache/ocr/paddlex`; `PADDLE_PDX_CACHE_HOME` can override this location. PaddleX's SDK manages its model downloads; `app.services.ocr.setup` continues to set up **Tesseract only**. Images are processed locally. The model process is reused for subsequent images and stopped on cancel, failure or application exit. Paddle result caching is not implemented yet.

Missing package/model, timeout or native-process errors are reported and logged (`logs/app.log`, `logs/paddle.log`). If enabled, Tesseract fallback runs on technical failure only; the result's Advanced warnings and batch status identify fallback. A low-confidence or empty Paddle result is sent for review, not replaced silently. To test Paddle alone, disable fallback or use the comparison command:

```powershell
.\.venv\Scripts\python.exe -m app.services.ocr.compare input/comments/cmt4.png input/comments/cmt5.png --output cache/ocr/comparison.json
```

The UTF-8 JSON report includes each engine's raw text, block count, mean confidence, extracted body and errors. Counts/confidences are not directly equivalent: Tesseract emits word boxes, Paddle emits detected text-span boxes. See PROGRESS.md for actual installation/inference evidence; package installation alone does not prove working OCR.

Both real providers ran on cmt4/cmt5, and Paddle completed an offscreen UI job without fallback. The [comparison report](docs/OCR_COMPARISON.md) shows Tesseract preserves Vietnamese better on these two images. Tesseract is now the default; Paddle remains selectable for experiments.

Windows notes from this integration: Paddle's default MKL-DNN inference raised `NotImplementedError`, so it is disabled by default (CPU inference may be slower). PaddlePaddle itself also creates a dataset cache under the Windows user profile on import, independently of the configured PaddleX model cache; restricted accounts/sandboxes need permission for that directory. Missing `ccache` prints an upstream warning but is not required for the installed CPU wheel. No system HOME/USERPROFILE override is used.
