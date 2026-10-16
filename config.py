import os

DATABASE_URL = "sqlite:///./english_train.db"
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
MEDIA_DIR = os.path.join(os.path.dirname(__file__), "static", "media")
