import os
import logging
from datetime import datetime
import sys

def setup_logging(log_folder="logs", level=logging.INFO):

    os.makedirs(log_folder, exist_ok=True)

    file_name = f"{datetime.today().strftime('%Y_%m_%d')}.log"

    logging.basicConfig(
        filename=os.path.join(log_folder, file_name),
        level=level,
        format="%(asctime)s %(levelname)s %(message)s"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

    logging.getLogger().addHandler(console)
    