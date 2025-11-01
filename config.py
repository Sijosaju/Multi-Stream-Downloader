
# """
# config.py - Configuration for RL-based Multi-Stream Downloader
# Aligned with the paper's approach for optimal network bandwidth utilization
# """
# import os

# # ======================== Download Settings ========================
# DEFAULT_NUM_STREAMS = 8
# MIN_STREAMS = 1
# MAX_STREAMS = 16

# # Chunk settings
# DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024   # 4 MB default chunk size
# MIN_CHUNK_SIZE = 1024 * 1024           # 1 MB minimum
# BUFFER_SIZE = 8192

# # Network settings
# CONNECTION_TIMEOUT = 10
# READ_TIMEOUT = 30
# MAX_RETRIES = 3
# RETRY_DELAY = 2

# # ======================== RL Settings (Paper-aligned) ========================
# # Monitoring Interval (MI) - Section 3 of paper
# RL_MONITORING_INTERVAL = 5.0  # seconds between RL decisions (conservative)

# # Q-Learning parameters (FIXED)
# RL_LEARNING_RATE = 0.2        # α in Q-learning update (higher for faster learning)
# RL_DISCOUNT_FACTOR = 0.85     # γ - future reward discount
# RL_EXPLORATION_RATE = 0.4     # ε - initial exploration rate (higher initial exploration)
# RL_MIN_EXPLORATION = 0.1      # minimum exploration to maintain
# RL_EXPLORATION_DECAY = 0.998  # slower decay for more exploration

# # Utility function parameters (Equation 3 from paper) - FIXED
# UTILITY_K = 1.1  # Cost-benefit parameter for additional streams
# UTILITY_B = 100  # Punishment severity for packet loss (scaled up since loss is now decimal)
# UTILITY_EPSILON = 0.15  # Threshold for significant utility change (adjusted for scale)

# # Reward values (Section 3.1.3 from paper)
# REWARD_POSITIVE = 1.0   # x - positive improvement
# REWARD_NEGATIVE = -1.0  # y - negative impact
# REWARD_NEUTRAL = 0.0    # no significant change

# # State discretization levels (reduced for faster convergence)
# THROUGHPUT_LEVELS = 3   # Low, Medium, High
# RTT_LEVELS = 3          # Good, Fair, Poor
# LOSS_LEVELS = 2         # Low, High

# # ======================== Application Settings ========================
# DOWNLOAD_FOLDER = os.path.join(
#     os.path.expanduser("~"), 
#     "Downloads", 
#     "MultiStreamDownloader"
# )

# # Flask web interface
# FLASK_HOST = '0.0.0.0'
# FLASK_PORT = 5000
# FLASK_DEBUG = False

# # Q-table persistence
# Q_TABLE_FILE = 'q_table.json'
# Q_TABLE_BACKUP = 'q_table_backup.json'
# Q_TABLE_SAVE_INTERVAL = 50  # Save every N decisions

# # Performance monitoring
# HEALTH_CHECK_INTERVAL = 10  # seconds
# PROGRESS_CHECK_INTERVAL = 10  # seconds
# NO_PROGRESS_TIMEOUT = 30  # seconds without progress = potential issue

# # Create download folder
# os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# # ======================== Logging ========================
# ENABLE_VERBOSE_LOGGING = True
# LOG_RL_DECISIONS = True
# LOG_NETWORK_METRICS = True
# LOG_Q_TABLE_UPDATES = True
"""
config.py - Configuration for RL-based Multi-Stream Downloader
Fixed parameters to prevent over-optimization
"""
import os

# ======================== Download Settings ========================
DEFAULT_NUM_STREAMS = 8
MIN_STREAMS = 1
MAX_STREAMS = 16

# Chunk settings
DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024   # 4 MB default chunk size
MIN_CHUNK_SIZE = 1024 * 1024           # 1 MB minimum
BUFFER_SIZE = 8192

# Network settings
CONNECTION_TIMEOUT = 10
READ_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_DELAY = 2

# ======================== RL Settings (Fixed) ========================
# Monitoring Interval (MI) - Section 3 of paper
RL_MONITORING_INTERVAL = 5.0  # seconds between RL decisions

# Q-Learning parameters (BALANCED)
RL_LEARNING_RATE = 0.1        # α - lower for stability
RL_DISCOUNT_FACTOR = 0.8      # γ - lower discount for immediate rewards
RL_EXPLORATION_RATE = 0.3     # ε - balanced exploration
RL_MIN_EXPLORATION = 0.05     # minimum exploration
RL_EXPLORATION_DECAY = 0.995  # slower decay

# Utility function parameters (BALANCED)
UTILITY_K = 1.02              # Much smaller cost per stream
UTILITY_B = 5.0               # Moderate punishment for loss
UTILITY_EPSILON = 0.08         # 10% relative threshold

# Reward values
REWARD_POSITIVE = 1.0
REWARD_NEGATIVE = -1.0
REWARD_NEUTRAL = 0.0

# State discretization levels
THROUGHPUT_LEVELS = 4   # Very Low, Low, Medium, High
RTT_LEVELS = 3          # Excellent, Good, Poor
LOSS_LEVELS = 3         # Excellent, Good, Poor

# ======================== Application Settings ========================
DOWNLOAD_FOLDER = os.path.join(
    os.path.expanduser("~"), 
    "Downloads", 
    "MultiStreamDownloader"
)

# Flask web interface
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 5000
FLASK_DEBUG = False

# Q-table persistence
Q_TABLE_FILE = 'q_table.json'
Q_TABLE_BACKUP = 'q_table_backup.json'
Q_TABLE_SAVE_INTERVAL = 50  # Save every N decisions

# Performance monitoring
HEALTH_CHECK_INTERVAL = 10
PROGRESS_CHECK_INTERVAL = 10
NO_PROGRESS_TIMEOUT = 30

# Create download folder
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# ======================== Logging ========================
ENABLE_VERBOSE_LOGGING = True
LOG_RL_DECISIONS = True
LOG_NETWORK_METRICS = True
LOG_Q_TABLE_UPDATES = False  # Less verbose