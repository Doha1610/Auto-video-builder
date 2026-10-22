// ============ CẤU HÌNH CHUNG ============
const API = window.location.origin;
const $ = (id) => document.getElementById(id);

// Biến lưu trạng thái cho Tab Whisper
let transcribeJobId = null;
let lastTranscribeLog = 0;
let transcribeTimer = null;

// Biến lưu trạng thái cho Tab Tạo Video
let renderJobId = null;
let lastRenderLog = 0;
let renderTimer = null;

// ============ CHUYỂN TAB ============
$("tab-btn-video").addEventListener("click", () => {
    $("tab-btn-video").className = "px-5 py-2 rounded-md font-semibold bg-accent text-white transition-all";
    $("tab-btn-transcribe").className = "px-5 py-2 rounded-md font-semibold text-slate-400 hover:text-white transition-all";
    $("tab-content-video").classList.remove("hidden");
    $("tab-content-transcribe").classList.add("hidden");
});

$("tab-btn-transcribe").addEventListener("click", () => {
    $("tab-btn-transcribe").className = "px-5 py-2 rounded-md font-semibold bg-accent text-white transition-all";
    $("tab-btn-video").className = "px-5 py-2 rounded-md font-semibold text-slate-400 hover:text-white transition-all";
    $("tab-content-transcribe").classList.remove("hidden");
    $("tab-content-video").classList.add("hidden");
});

// ==========================================
// LOGIC TAB 1: TẠO VIDEO
// ==========================================

// Xử lý ẩn/hiện khu vực nhập liệu (Text vs File)
document.querySelectorAll('input[name="audioSource"]').forEach(radio => {
    radio.addEventListener('change', (e) => {
        const textSection = $('textInputSection');
        const fileSection = $('fileInputSection');
        const voiceSelect = $('voiceType');
        
        if (e.target.value === 'text') {
            textSection.classList.remove('hidden');
            fileSection.classList.add('hidden');
            voiceSelect.disabled = false;
            voiceSelect.classList.remove('opacity-50');
        } else {
            textSection.classList.add('hidden');
            fileSection.classList.remove('hidden');
            voiceSelect.disabled = true;
            voiceSelect.classList.add('opacity-50');
        }
    });
});

// Tải danh sách Topic
async function loadTopics() {
    try {
        const res = await fetch(`${API}/api/topics`);
        const data = await res.json();
        const select = $("videoTopic");
        select.innerHTML = '<option value="">-- Chọn Topic --</option>';
        if (data.topics) {
            data.topics.forEach(t => select.innerHTML += `<option value="${t}">${t}</option>`);
        }
    } catch (e) { console.error("Lỗi tải topic:", e); }
}
loadTopics();

// Nút "Tải video mới từ Google Sheet"
$("startDownloadBtn").addEventListener("click", async () => {
    const btn = $("startDownloadBtn");
    btn.disabled = true; btn.textContent = "⏳ Đang tải từ Sheet...";
    
    $("renderProgressSection").classList.remove("hidden");
    $("renderLogBox").textContent = "";
    
    try {
        const res = await fetch(`${API}/api/download-sheet`, { method: "POST" });
        const data = await res.json();
        
        const timer = setInterval(async () => {
            const pRes = await fetch(`${API}/api/progress/${data.job_id}`);
            const pData = await pRes.json();
            
            if (pData.logs) {
                pData.logs.forEach(l => $("renderLogBox").textContent += `[${fmtTime(l.t)}] ${l.msg}\n`);
                $("renderLogBox").scrollTop = $("renderLogBox").scrollHeight;
            }
            
            if (pData.status === "done") {
                clearInterval(timer);
                btn.disabled = false; btn.textContent = "📥 Tải video mới từ Google Sheet";
                alert("Tải video thành công!");
            } else if (pData.status === "error") {
                clearInterval(timer);
                btn.disabled = false; btn.textContent = "📥 Tải video mới từ Google Sheet";
                alert("Lỗi: " + pData.error);
            }
        }, 1000);
        
    } catch (e) {
        alert("Lỗi: " + e.message); btn.disabled = false; btn.textContent = "📥 Tải video mới từ Google Sheet";
    }
});

// Nút "Bắt đầu tạo Video"
$("startRenderBtn").addEventListener("click", async () => {
    const sourceType = document.querySelector('input[name="audioSource"]:checked').value;
    const text = $("scriptText").value.trim();
    const topic = $("videoTopic").value;
    const voice = $("voiceType").value;
    const fileInput = $("audioFileInput");

    // Kiểm tra dữ liệu đầu vào
    if (sourceType === 'text' && !text) { 
        alert("Vui lòng nhập kịch bản!"); 
        return; 
    }
    if (sourceType === 'file' && fileInput.files.length === 0) {
        alert("Vui lòng chọn file audio!");
        return;
    }

    const btn = $("startRenderBtn");
    btn.disabled = true; btn.textContent = "⏳ Đang xử lý (vui lòng đợi)...";

    $("renderProgressSection").classList.remove("hidden");
    $("renderResultSection").classList.add("hidden");
    $("renderProgressBar").style.width = "0%";
    $("renderProgressPct").textContent = "0%";
    $("renderLogBox").textContent = "";
    lastRenderLog = 0;

    try {
        // Đóng gói dữ liệu vào FormData (để gửi được file)
        const formData = new FormData();
        formData.append("source_type", sourceType);
        formData.append("topic", topic);
        
        if (sourceType === 'text') {
            formData.append("text", text);
            formData.append("voice", voice);
        } else {
            formData.append("audio_file", fileInput.files[0]);
        }

        const res = await fetch(`${API}/api/render-video`, {
            method: "POST", 
            body: formData 
        });
        
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Lỗi gọi API");
        
        renderJobId = data.job_id;
        startRenderPolling();

    } catch (e) {
        alert("Lỗi: " + e.message);
        resetRenderBtn();
    }
});

// Hàm kiểm tra tiến độ (Polling) cho Tạo Video
function startRenderPolling() {
    if (renderTimer) clearInterval(renderTimer);

    renderTimer = setInterval(async () => {
        try {
            const res = await fetch(`${API}/api/progress/${renderJobId}?since=${lastRenderLog}`);
            const data = await res.json();

            if (data.logs && data.logs.length > 0) {
                const box = $("renderLogBox");
                data.logs.forEach(l => {
                    box.textContent += `[${fmtTime(l.t)}] ${l.msg}\n`;
                });
                box.scrollTop = box.scrollHeight;
                lastRenderLog = data.log_count;
            }

            if (typeof data.progress === "number") {
                const pct = Math.min(data.progress, 100);
                $("renderProgressBar").style.width = pct + "%";
                $("renderProgressPct").textContent = pct.toFixed(1) + "%";
                $("renderStatusText").textContent = `Đang xử lý... ${pct.toFixed(1)}%`;
            }

            if (data.status === "done") {
                clearInterval(renderTimer);
                $("renderStatusText").textContent = "✅ Hoàn tất!";
                
                $("renderResultSection").classList.remove("hidden");
                $("finalVideoPlayer").src = `${API}${data.result.video_url}`;
                $("downloadVideoBtn").href = `${API}${data.result.video_url}`;
                resetRenderBtn();
                
            } else if (data.status === "error") {
                clearInterval(renderTimer);
                alert("Lỗi xử lý: " + data.error);
                resetRenderBtn();
            }

        } catch (e) {
            console.error("Lỗi polling:", e);
        }
    }, 1000);
}

function resetRenderBtn() {
    const btn = $("startRenderBtn");
    btn.disabled = false;
    btn.textContent = "🚀 Bắt đầu tạo Video";
}


// ==========================================
// LOGIC TAB 2: WHISPER (LẤY VĂN BẢN)
// ==========================================

$("startBtn").addEventListener("click", startTranscribe);
$("openFolderBtn").addEventListener("click", openFolder);
$("spellCheckBtn").addEventListener("click", spellCheck);

$("url").addEventListener("keydown", (e) => {
    if (e.key === "Enter") startTranscribe();
});

async function startTranscribe() {
    const url = $("url").value.trim();
    if (!url) {
        alert("Bạn chưa nhập URL.");
        return;
    }

    const model = $("model").value;
    const language = $("language").value || null;

    $("startBtn").disabled = true;
    $("startBtn").textContent = "⏳ Đang xử lý...";
    $("progressSection").classList.remove("hidden");
    $("logSection").classList.remove("hidden");
    $("resultSection").classList.add("hidden");
    $("logBox").textContent = "";
    $("progressBar").style.width = "0%";
    $("progressPct").textContent = "0%";
    $("statusText").textContent = "Đang khởi động...";
    lastTranscribeLog = 0;

    try {
        const res = await fetch(`${API}/api/process`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, model, language }),
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Lỗi HTTP ${res.status}`);
        }

        const data = await res.json();
        transcribeJobId = data.job_id;
        $("statusText").textContent = `Đang xử lý (job ${transcribeJobId})...`;
        pollProgress();
    } catch (e) {
        alert("Lỗi: " + e.message);
        resetTranscribeUI();
    }
}

function pollProgress() {
    if (!transcribeJobId) return;

    if (transcribeTimer) clearInterval(transcribeTimer);

    transcribeTimer = setInterval(async () => {
        try {
            const res = await fetch(
                `${API}/api/progress/${transcribeJobId}?since=${lastTranscribeLog}`
            );
            if (!res.ok) return;

            const data = await res.json();

            if (data.logs && data.logs.length) {
                const box = $("logBox");
                data.logs.forEach((l) => {
                    box.textContent += `[${fmtTime(l.t)}] ${l.msg}\n`;
                });
                box.scrollTop = box.scrollHeight;
                lastTranscribeLog = data.log_count;
            }

            if (typeof data.progress === "number") {
                const pct = Math.min(data.progress, 100);
                $("progressBar").style.width = pct + "%";
                $("progressPct").textContent = pct.toFixed(1) + "%";
                $("statusText").textContent = `Đang xử lý... ${pct.toFixed(1)}%`;
            }

            if (data.status === "done") {
                clearInterval(transcribeTimer);
                $("statusText").textContent = "✅ Hoàn tất!";
                showTranscribeResult(data.result);
                resetTranscribeUI();
            } else if (data.status === "error") {
                clearInterval(transcribeTimer);
                $("statusText").textContent = "❌ Lỗi";
                alert("Lỗi: " + data.error);
                resetTranscribeUI();
            }
        } catch (e) {
            console.error(e);
        }
    }, 800);
}

function showTranscribeResult(result) {
    if (!result) return;
    $("resultSection").classList.remove("hidden");
    $("downloadTxt").href = `${API}/api/download/${transcribeJobId}/txt`;
    $("downloadSrt").href = `${API}/api/download/${transcribeJobId}/srt`;
    $("resultText").value = result.text || "";
}

function resetTranscribeUI() {
    $("startBtn").disabled = false;
    $("startBtn").textContent = "🚀 Bắt đầu";
}

async function openFolder() {
    try {
        await fetch(`${API}/api/open-output`);
    } catch (e) {
        alert("Không mở được thư mục. Backend đã chạy chưa?");
    }
}

async function spellCheck() {
    if (!transcribeJobId) {
        alert("Chưa có kết quả để kiểm tra.");
        return;
    }

    const btn = $("spellCheckBtn");
    btn.disabled = true;
    btn.textContent = "⏳ Đang sửa...";

    try {
        const res = await fetch(`${API}/api/correct/${transcribeJobId}`, {
            method: "POST",
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || `Lỗi HTTP ${res.status}`);
        }

        const data = await res.json();
        $("resultText").value = data.text || "";
        $("statusText").textContent = "✅ Đã kiểm tra chính tả!";
        btn.textContent = "✅ Đã sửa";

        setTimeout(() => {
            btn.textContent = "✏️ Kiểm tra chính tả";
            btn.disabled = false;
        }, 2000);

    } catch (e) {
        alert("Lỗi: " + e.message);
        btn.textContent = "✏️ Kiểm tra chính tả";
        btn.disabled = false;
    }
}

// Hàm phụ trợ format thời gian
function fmtTime(sec) {
    return new Date(sec * 1000).toLocaleTimeString("vi-VN");
}