from logger import log_video_selection, log_eye_data_stub
import streamlit as st
import os
from logger import log_video_selection

VIDEO_FOLDER = "videos"

st.title("Skill Lens Video Player")

videos = [f for f in os.listdir(VIDEO_FOLDER) if f.endswith((".mp4", ".mov"))]

selected_video = st.selectbox("Select a video", videos)

if selected_video:
    video_path = os.path.join(VIDEO_FOLDER, selected_video)

    log_video_selection(selected_video)
    log_eye_data_stub(selected_video)

    st.video(video_path)
    st.write(f"Now playing: {selected_video}")