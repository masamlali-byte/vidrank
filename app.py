import streamlit as st
import yt_dlp
import subprocess
import tempfile
from pathlib import Path

st.set_page_config(page_title="Ranking Video Maker", page_icon="🎬", layout="wide")

st.title("🎬 Ranking Video Maker")
st.caption("Search YouTube → pick clips → cut & add ranking overlays → export final video")

# ── SESSION STATE ──────────────────────────────────────────────────────────────
if "clips" not in st.session_state:
    st.session_state.clips = []
if "search_results" not in st.session_state:
    st.session_state.search_results = []

WORK_DIR = Path(tempfile.gettempdir()) / "ranking_video"
WORK_DIR.mkdir(exist_ok=True)

# ── SIDEBAR — SETTINGS ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Video Settings")
    video_title = st.text_input("Video title", "Top 10 Soccer Goals of All Time")
    resolution  = st.selectbox("Resolution", ["1920x1080", "1280x720"], index=1)
    font_size   = st.slider("Rank text size", 40, 120, 80)
    bg_opacity  = st.slider("Text bg opacity", 0.0, 1.0, 0.5, 0.05)
    intro_dur   = st.slider("Intro duration (sec)", 1, 5, 3)
    output_fmt  = st.selectbox("Output format", ["mp4", "webm"])
    st.divider()
    st.markdown("**⚠️ Reminder**")
    st.caption("Content ID will flag copyrighted footage. Use at your own risk.")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — SEARCH YOUTUBE
# ══════════════════════════════════════════════════════════════════════════════
st.header("1. Search YouTube")

col_q, col_n, col_btn = st.columns([3, 1, 1])
with col_q:
    query = st.text_input("Search query", placeholder="Maradona goal of the century 1986", label_visibility="collapsed")
with col_n:
    n_results = st.selectbox("Results", [5, 10, 15, 20], label_visibility="collapsed")
with col_btn:
    do_search = st.button("🔍 Search", type="primary", use_container_width=True)

if do_search and query:
    with st.spinner(f"Searching YouTube for: {query}..."):
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "skip_download": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(f"ytsearch{n_results}:{query}", download=False)
                entries = info.get("entries", [])
                st.session_state.search_results = [
                    {
                        "title":     e.get("title", "Unknown"),
                        "url":       f"https://www.youtube.com/watch?v={e.get('id', '')}",
                        "id":        e.get("id", ""),
                        "duration":  e.get("duration") or 0,
                        "channel":   e.get("uploader") or e.get("channel") or "Unknown",
                        "views":     e.get("view_count") or 0,
                        "thumbnail": e.get("thumbnail") or "",
                    }
                    for e in entries if e.get("id")
                ]
        except Exception as ex:
            st.error(f"Search failed: {ex}")

# ── DISPLAY SEARCH RESULTS ─────────────────────────────────────────────────────
if st.session_state.search_results:
    st.subheader(f"{len(st.session_state.search_results)} results")

    for idx, r in enumerate(st.session_state.search_results):
        dur_str   = f"{int(r['duration']//60)}:{int(r['duration']%60):02d}" if r["duration"] else "?"
        views_str = f"{r['views']:,}" if r["views"] else "?"

        c1, c2, c3 = st.columns([1, 4, 2])
        with c1:
            if r["thumbnail"]:
                st.image(r["thumbnail"], use_container_width=True)
            else:
                st.markdown("🎬")
        with c2:
            st.markdown(f"**{r['title']}**")
            st.caption(f"📺 {r['channel']}  •  ⏱ {dur_str}  •  👁 {views_str} views")
            st.caption(r["url"])
        with c3:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("➕ Add to ranking", key=f"add_{idx}", use_container_width=True):
                st.session_state[f"adding_{idx}"] = True
                st.rerun()

        # Inline config form
        if st.session_state.get(f"adding_{idx}"):
            with st.form(key=f"form_{idx}"):
                st.markdown(f"**Configure:** {r['title'][:70]}")
                fa, fb, fc = st.columns(3)
                with fa:
                    rank_num  = st.number_input("Rank #", 1, 100, len(st.session_state.clips) + 1)
                with fb:
                    max_dur   = int(r["duration"]) if r["duration"] else 300
                    start_sec = st.number_input("Start (sec)", 0, max(0, max_dur - 1), 0)
                with fc:
                    end_sec   = st.number_input("End (sec)", 1, max_dur, min(15, max_dur))
                rank_label = st.text_input("Rank label", f"#{rank_num} — {r['title'][:40]}")
                rank_desc  = st.text_input("Description on screen", r["channel"])

                ok, cancel = st.columns(2)
                with ok:
                    submitted = st.form_submit_button("✅ Confirm & Add", type="primary", use_container_width=True)
                with cancel:
                    cancelled = st.form_submit_button("Cancel", use_container_width=True)

                if submitted:
                    st.session_state.clips.append({
                        "url":      r["url"],
                        "title":    r["title"],
                        "rank":     int(rank_num),
                        "label":    rank_label,
                        "desc":     rank_desc,
                        "start":    int(start_sec),
                        "end":      int(end_sec),
                        "duration": int(end_sec) - int(start_sec),
                    })
                    st.session_state.clips.sort(key=lambda x: x["rank"], reverse=True)
                    st.session_state[f"adding_{idx}"] = False
                    st.success(f"Added: {rank_label}")
                    st.rerun()
                if cancelled:
                    st.session_state[f"adding_{idx}"] = False
                    st.rerun()

        st.divider()

# ══════════════════════════════════════════════════════════════════════════════
# MANUAL URL FALLBACK
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("➕ Add a clip manually by URL"):
    with st.form("manual_form"):
        m1, m2 = st.columns([3, 1])
        with m1:
            man_url   = st.text_input("YouTube URL", placeholder="https://www.youtube.com/watch?v=...")
            man_label = st.text_input("Rank label", placeholder="e.g. #1 — Goal of the Century")
            man_desc  = st.text_input("Description", placeholder="Maradona vs England, 1986")
        with m2:
            man_rank  = st.number_input("Rank #", 1, 100, len(st.session_state.clips) + 1)
            man_start = st.number_input("Start (sec)", 0, 9999, 0)
            man_end   = st.number_input("End (sec)", 1, 9999, 15)
        if st.form_submit_button("Add Clip", type="primary"):
            if man_url and man_label:
                st.session_state.clips.append({
                    "url":      man_url,
                    "title":    man_label,
                    "rank":     int(man_rank),
                    "label":    man_label,
                    "desc":     man_desc,
                    "start":    int(man_start),
                    "end":      int(man_end),
                    "duration": int(man_end) - int(man_start),
                })
                st.session_state.clips.sort(key=lambda x: x["rank"], reverse=True)
                st.success(f"Added: {man_label}")
                st.rerun()
            else:
                st.error("URL and label are required.")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — CLIP LINEUP
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.clips:
    st.header("2. Your ranking lineup")
    st.caption(f"{len(st.session_state.clips)} clips • ordered highest rank → #1")

    for i, clip in enumerate(st.session_state.clips):
        ca, cb, cc = st.columns([3, 2, 1])
        with ca:
            st.markdown(f"**{clip['label']}**")
            st.caption(clip["url"])
        with cb:
            st.caption(f"⏱ {clip['start']}s → {clip['end']}s ({clip['duration']}s)")
            st.caption(f"📝 {clip['desc']}")
        with cc:
            if st.button("🗑", key=f"del_{i}"):
                st.session_state.clips.pop(i)
                st.rerun()

    if st.button("🗑 Clear all clips"):
        st.session_state.clips = []
        st.rerun()

    # ══════════════════════════════════════════════════════════════════════════
    # STEP 3 — GENERATE
    # ══════════════════════════════════════════════════════════════════════════
    st.header("3. Generate video")

    if st.button("🚀 Download & Build Video", type="primary"):
        progress   = st.progress(0)
        status     = st.empty()
        total      = len(st.session_state.clips)
        clip_paths = []
        w, h       = resolution.split("x")
        font_bold  = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        font_reg   = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

        for i, clip in enumerate(st.session_state.clips):
            out_base     = WORK_DIR / f"raw_{i}"
            cut_path     = WORK_DIR / f"cut_{i}.mp4"
            overlay_path = WORK_DIR / f"overlay_{i}.mp4"

            # 1. Download
            status.info(f"⬇️ [{i+1}/{total}] Downloading: {clip['label']}")
            ydl_opts = {
                "format": "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]",
                "outtmpl": str(out_base) + ".%(ext)s",
                "quiet": True,
                "no_warnings": True,
                "merge_output_format": "mp4",
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([clip["url"]])
            except Exception as e:
                st.error(f"Download failed for clip {i+1}: {e}")
                continue

            found = list(WORK_DIR.glob(f"raw_{i}.*"))
            if not found:
                st.error(f"File not found after download for clip {i+1}")
                continue
            raw_file = found[0]

            # 2. Cut
            status.info(f"✂️ [{i+1}/{total}] Cutting {clip['start']}s → {clip['end']}s")
            cut_cmd = [
                "ffmpeg", "-y",
                "-ss", str(clip["start"]),
                "-i", str(raw_file),
                "-t", str(clip["duration"]),
                "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                       f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-b:a", "128k", "-r", "30",
                str(cut_path)
            ]
            try:
                subprocess.run(cut_cmd, check=True, capture_output=True)
            except subprocess.CalledProcessError as e:
                st.error(f"Cut failed: {e.stderr.decode()[:300]}")
                continue

            # 3. Rank overlay
            status.info(f"🔤 [{i+1}/{total}] Adding rank overlay")
            rank_text  = f"#{clip['rank']}"
            label_safe = clip["label"].replace("'", "\\'").replace(":", "\\:")[:50]
            desc_safe  = clip["desc"].replace("'", "\\'").replace(":", "\\:")[:60]

            drawtext = (
                f"drawbox=x=0:y=0:w={w}:h=150:color=black@{bg_opacity}:t=fill,"
                f"drawtext=text='{rank_text}':fontsize={font_size}:fontcolor=gold:"
                f"x=28:y=18:fontfile={font_bold}:shadowcolor=black:shadowx=3:shadowy=3,"
                f"drawtext=text='{label_safe}':fontsize={font_size//3}:fontcolor=white:"
                f"x={28+font_size+10}:y=25:fontfile={font_bold}:shadowcolor=black:shadowx=2:shadowy=2,"
                f"drawtext=text='{desc_safe}':fontsize={font_size//4}:fontcolor=#bbbbbb:"
                f"x={28+font_size+10}:y={25+font_size//3+12}:fontfile={font_reg}:shadowcolor=black:shadowx=1:shadowy=1"
            )
            overlay_cmd = [
                "ffmpeg", "-y",
                "-i", str(cut_path),
                "-vf", drawtext,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "copy",
                str(overlay_path)
            ]
            try:
                subprocess.run(overlay_cmd, check=True, capture_output=True)
                clip_paths.append(str(overlay_path))
            except subprocess.CalledProcessError as e:
                st.warning(f"Overlay failed, using plain cut. ({e.stderr.decode()[:100]})")
                clip_paths.append(str(cut_path))

            progress.progress((i + 1) / total * 0.8)

        # Intro card
        status.info("🎬 Building intro card...")
        intro_path = WORK_DIR / "intro.mp4"
        title_safe = video_title.replace("'", "\\'").replace(":", "\\:")
        intro_cmd  = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:size={w}x{h}:duration={intro_dur}:rate=30",
            "-vf",
            f"drawtext=text='{title_safe}':fontsize={int(font_size*0.7)}:fontcolor=gold:"
            f"x=(w-text_w)/2:y=(h-text_h)/2-20:fontfile={font_bold}:shadowcolor=black:shadowx=3:shadowy=3,"
            f"drawtext=text='Ranking Video':fontsize={int(font_size*0.28)}:fontcolor=#888888:"
            f"x=(w-text_w)/2:y=(h+text_h)/2+10:fontfile={font_reg}",
            "-c:v", "libx264", "-preset", "fast", "-an",
            str(intro_path)
        ]
        try:
            subprocess.run(intro_cmd, check=True, capture_output=True)
            all_clips = [str(intro_path)] + clip_paths
        except Exception:
            all_clips = clip_paths

        # Concat
        status.info("🔗 Merging all clips into final video...")
        concat_list = WORK_DIR / "concat.txt"
        with open(concat_list, "w") as f:
            for cp in all_clips:
                f.write(f"file '{cp}'\n")

        final_path = WORK_DIR / f"final_ranking.{output_fmt}"
        concat_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(final_path)
        ]
        try:
            subprocess.run(concat_cmd, check=True, capture_output=True)
            progress.progress(1.0)
            status.success("✅ Video ready!")
            with open(final_path, "rb") as f:
                st.download_button(
                    label=f"⬇️ Download final video ({output_fmt.upper()})",
                    data=f,
                    file_name=f"ranking_video.{output_fmt}",
                    mime=f"video/{output_fmt}",
                    type="primary"
                )
            st.balloons()
        except subprocess.CalledProcessError as e:
            st.error(f"Merge failed: {e.stderr.decode()[:500]}")

# ── INSTALL INSTRUCTIONS ───────────────────────────────────────────────────────
with st.expander("📦 Installation & usage"):
    st.code("""# Install Python dependencies
pip install streamlit yt-dlp

# Install ffmpeg
sudo apt install ffmpeg        # Linux/Ubuntu
brew install ffmpeg            # Mac
# Windows: https://ffmpeg.org/download.html

# Run the app
streamlit run app.py
""", language="bash")
    st.markdown("""
**Workflow:**
1. Type a search query (e.g. "Ronaldo bicycle kick") → hit Search
2. Browse results with thumbnails, duration, view count
3. Click **Add to ranking** → set rank number, start/end time, label
4. Repeat for all your clips
5. Hit **Download & Build Video**
6. Add voiceover + music in CapCut before uploading to YouTube
""")
