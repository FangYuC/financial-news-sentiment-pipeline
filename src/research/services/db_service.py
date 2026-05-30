import json
import logging
import traceback
import pandas as pd

from pathlib import Path
from sqlalchemy import create_engine


PROJECT_ROOT = Path(__file__).resolve().parents[3]
logger = logging.getLogger(__name__)


def load_setting(setting_file: str = "setting.json"):

    config_path = PROJECT_ROOT / "config" / setting_file

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        setting = json.load(f)

    return setting


def db_connect(setting: dict):
    try:
        engine = create_engine(
            f"mysql+pymysql://{setting['username']}:{setting['password']}@"
            f"{setting['host']}/{setting['database']}",
            echo=False
        )
        return engine, "success"

    except Exception as e:
        logger.error(f"db_connect error: {e}")
        return None, "fail"
    

def load_data_from_sql(
    setting_file: str = "setting.json",
    table_name: str = "news"
):

    try:

        setting = load_setting(setting_file)

        engine, status = db_connect(setting)
        
        if status == "success":
            with engine.connect() as connection:
                data = pd.read_sql(table_name, con=connection)

        logger.info(f"Loaded table: {table_name}")

        return data

    except Exception as e:

        traceback.print_exc()
        logger.error(f"Failed loading SQL data: {e}")

        raise
    
    
def save_data_tosql(
    df,
    setting_file: str = "setting.json",
    table_name: str = "stock_price",
    index: bool = False
):

    try:

        setting = load_setting(setting_file)

        engine, status = db_connect(setting)

        if status == "success":
            with engine.connect() as connection:
                df.to_sql(
                    name=table_name,
                    con=connection,
                    index=index,
                    if_exists="append"
                )

        logger.info(f"Saved data to MySQL table: {table_name}")

    except Exception as e:

        traceback.print_exc()
        logger.error(f"Failed saving data to MySQL: {e}")

        raise
    