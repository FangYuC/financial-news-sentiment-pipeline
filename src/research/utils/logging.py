import os
import logging
from datetime import datetime
import sys


logger = logging.getLogger(__name__)


def setup_logging(log_folder="logs", level=logging.INFO):

    os.makedirs(log_folder, exist_ok=True)

    file_name = f"{datetime.today().strftime('%Y_%m_%d')}.log"

    # 直接抓 root logger
    logger = logging.getLogger()

    # 防止重複初始化（關鍵）
    if logger.handlers:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s"
    )

    file_handler = logging.FileHandler(
        os.path.join(log_folder, file_name)
    )
    file_handler.setFormatter(formatter)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console)

    return logger