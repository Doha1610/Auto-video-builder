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
        
        // Polling log tiến trình tải
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
        alert("Lỗi: " + e.message); btn.disabled = false;
    }
});

// Nút "Bắt đầu tạo Video"
$("startRenderBtn").addEventListener("click", async () => {
    const text = $("scriptText").value.trim();
    const topic = $("videoTopic").value;
    const voice = $("voiceType").value;

    if (!text) { alert("Vui lòng nhập kịch bản!"); return; }

    const btn = $("startRenderBtn");
    btn.disabled = true; btn.textContent = "⏳ Đang xử lý...";

    $("renderProgressSection").classList.remove("hidden");
    $("renderResultSection").classList.add("hidden");
    $("renderProgressBar").style.width = "0%";
    $("renderLogBox").textContent = "";
    lastRenderLog = 0;

    try {
        const res = await fetch(`${API}/api/render-video`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text, topic, voice })
        });
        
        const data = await res.json();
        renderJobId = data.job_id;
        
        renderTimer = setInterval(async () => {
            const pRes = await fetch(`${API}/api/progress/${renderJobId}?since=${lastRenderLog}`);
            const pData = await pRes.json();

            if (pData.logs && pData.logs.length > 0) {
                pData.logs.forEach(l => $("renderLogBox").textContent += `[${fmtTime(l.t)}] ${l.msg}\n`);
                $("renderLogBox").scrollTop = $("renderLogBox").scrollHeight;
                lastRenderLog = pData.log_count;
            }

            if (typeof pData.progress === "number") {
                $("renderProgressBar").style.width = pData.progress + "%";
                $("renderProgressPct").textContent = pData.progress.toFixed(1) + "%";
            }

            if (pData.status === "done") {
                clearInterval(renderTimer);
                $("renderStatusText").textContent = "✅ Hoàn tất!";
                $("renderResultSection").classList.remove("hidden");
                $("finalVideoPlayer").src = `${API}${pData.result.video_url}`;
                $("downloadVideoBtn").href = `${API}${pData.result.video_url}`;
                btn.disabled = false; btn.textContent = "🚀 Bắt đầu tạo Video";
            } else if (pData.status === "error") {
                clearInterval(renderTimer);
                alert("Lỗi: " + pData.error); btn.disabled = false; btn.textContent = "🚀 Bắt đầu tạo Video";
            }
        }, 1000);
    } catch (e) {
        alert("Lỗi kết nối API"); btn.disabled = false; btn.textContent = "🚀 Bắt đầu tạo Video";
    }
});


// ==========================================
// LOGIC TAB 2: WHISPER
// ==========================================

$("startBtn").addEventListener("click", startTranscribe);
$("openFolderBtn").addEventListener("click", async () => {
    try { await fetch(`${API}/api/open-output`); } catch (e) { alert("Lỗi mở thư mục"); }
});
$("spellCheckBtn").addEventListener("click", spellCheck);

$("url").addEventListener("keydown", (e) => { if (e.key === "Enter") startTranscribe(); });

async function startTranscribe() {
    const url = $("url").value.trim();
    if (!url) { alert("Bạn chưa nhập URL."); return; }

    const model = $("model").value;
    const language = $("language").value || null;

    $("startBtn").disabled = true; $("startBtn").textContent = "⏳ Đang xử lý...";
    $("progressSection").classList.remove("hidden");
    $("logSection").classList.remove("hidden");
    $("resultSection").classList.add("hidden");
    $("logBox").textContent = ""; $("progressBar").style.width = "0%"; lastTranscribeLog = 0;

    try {
        const res = await fetch(`${API}/api/process`, {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, model, language }),
        });
        const data = await res.json();
        transcribeJobId = data.job_id;
        
        transcribeTimer = setInterval(async () => {
            const pRes = await fetch(`${API}/api/progress/${transcribeJobId}?since=${lastTranscribeLog}`);
            const pData = await pRes.json();

            if (pData.logs && pData.logs.length) {
                const box = $("logBox");
                pData.logs.forEach(l => box.textContent += `[${fmtTime(l.t)}] ${l.msg}\n`);
                box.scrollTop = box.scrollHeight;
                lastTranscribeLog = pData.log_count;
            }

            if (typeof pData.progress === "number") {
                $("progressBar").style.width = pData.progress + "%";
                $("progressPct").textContent = pData.progress.toFixed(1) + "%";
            }

            if (pData.status === "done") {
                clearInterval(transcribeTimer);
                $("resultSection").classList.remove("hidden");
                $("downloadTxt").href = `${API}/api/download/${transcribeJobId}/txt`;
                $("downloadSrt").href = `${API}/api/download/${transcribeJobId}/srt`;
                $("resultText").value = pData.result.text || "";
                $("startBtn").disabled = false; $("startBtn").textContent = "🚀 Bắt đầu";
            } else if (pData.status === "error") {
                clearInterval(transcribeTimer);
                alert("Lỗi: " + pData.error);
                $("startBtn").disabled = false; $("startBtn").textContent = "🚀 Bắt đầu";
            }
        }, 800);
    } catch (e) {
        alert("Lỗi: " + e.message); $("startBtn").disabled = false; $("startBtn").textContent = "🚀 Bắt đầu";
    }
}

async function spellCheck() {
    if (!transcribeJobId) return;
    const btn = $("spellCheckBtn");
    btn.disabled = true; btn.textContent = "⏳ Đang sửa...";

    try {
        const res = await fetch(`${API}/api/correct/${transcribeJobId}`, { method: "POST" });
        const data = await res.json();
        $("resultText").value = data.text || "";
        btn.textContent = "✅ Đã sửa";
        setTimeout(() => { btn.textContent = "✏️ Kiểm tra chính tả"; btn.disabled = false; }, 2000);
    } catch (e) {
        alert("Lỗi sửa chính tả"); btn.textContent = "✏️ Kiểm tra chính tả"; btn.disabled = false;
    }
}

function fmtTime(sec) {
    return new Date(sec * 1000).toLocaleTimeString("vi-VN");
}