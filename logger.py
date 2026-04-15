from datetime import datetime
import os

LOG_FILE = "video_log.csv"

def log_video_selection(video_name):
    file_exists = os.path.isfile(LOG_FILE)

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        if not file_exists:
            f.write("timestamp,video_name,event\n")
        f.write(f"{datetime.now().isoformat()},{video_name},video_selected\n")


def log_eye_data_stub(video_name):
    with open("eye_tracking_stub.csv", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat()},{video_name},eye_tracking_started\n")