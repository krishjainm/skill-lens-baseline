import os
import uuid

import streamlit as st

from logger import PROJECT_ROOT, log_session_ui_events_for_video

VIDEO_FOLDER = str(PROJECT_ROOT / "videos")

st.title("Skill Lens Video Player")

if not os.path.isdir(VIDEO_FOLDER):
    st.error(f"Missing folder: `{VIDEO_FOLDER}/` (expected next to the app, regardless of CWD).")
    st.stop()

videos = sorted(
    f for f in os.listdir(VIDEO_FOLDER) if f.lower().endswith((".mp4", ".mov"))
)

if not videos:
    st.warning(f"No `.mp4` or `.mov` files found in `{VIDEO_FOLDER}/`.")
    st.stop()

session_id = st.session_state.setdefault("session_id", str(uuid.uuid4()))
st.sidebar.caption("Session (match Neon recording)")
st.sidebar.code(session_id, language=None)
st.sidebar.caption(
    "Match Neon: set env `NEON_SESSION_ID` to this value, or use "
    "`neon_gaze_recorder.py --session-id` (cmd: `set`, PowerShell: `$env:NEON_SESSION_ID=`)."
)
if st.sidebar.button("New session ID"):
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.last_logged_video = None
    st.rerun()

selected_video = st.selectbox("Select a video", videos)
video_path = os.path.join(VIDEO_FOLDER, selected_video)

# Log only when the user changes the dropdown — not on every Streamlit rerun.
if "last_logged_video" not in st.session_state:
    st.session_state.last_logged_video = None
if st.session_state.last_logged_video != selected_video:
    log_session_ui_events_for_video(selected_video, session_id)
    st.session_state.last_logged_video = selected_video

st.video(video_path)
st.write(f"Now playing: {selected_video}")
