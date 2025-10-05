# config.py - Configuration settings

import os

# Download settings
DEFAULT_NUM_STREAMS = 8  # Number of parallel connections (from paper: optimal is 15-20, but 8 is safe start)
MIN_STREAMS = 1
MAX_STREAMS = 16  # Cap to avoid overwhelming the network

# Chunk size settings
MIN_CHUNK_SIZE = 1024 * 1024  # 1 MB minimum per chunk
BUFFER_SIZE = 8192  # 8 KB buffer for reading/writing

# Download folder
DOWNLOAD_FOLDER = os.path.join(os.path.expanduser("~"), "Downloads", "MultiStreamDownloader")

# Timeout settings
CONNECTION_TIMEOUT = 10  # seconds
READ_TIMEOUT = 30  # seconds

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Create download folder if it doesn't exist
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)