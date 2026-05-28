import os
import traceback
import logging
import pandas as pd

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def save_csv(df, filename="news_data.csv", subfolder="raw"):
    try:
        root = Path(__file__).resolve().parents[2]
        data_dir = root / "data" / subfolder
        data_dir.mkdir(parents=True, exist_ok=True)

        path = data_dir / filename
        df.to_csv(path, index=False)

        print(f"[SAVE] {path}")

    except Exception as e:
        traceback.print_exc()
        logging.error(f"CSV save failed: {e}")
        

def save_data_toxlsx(
    stock_data_dict,
    filename: str = "US_stock_price.xlsx",
    subfolder: str = "excel"
):

    try:

        data_dir = PROJECT_ROOT / "data" / subfolder

        data_dir.mkdir(parents=True, exist_ok=True)

        file_path = data_dir / filename

        if not file_path.exists():

            with pd.ExcelWriter(file_path, mode="w") as writer:

                for stock_name, df in stock_data_dict.items():

                    df.to_excel(writer, sheet_name=stock_name)

                    logging.info(f"Saved sheet: {stock_name}")

        else:

            with pd.ExcelWriter(
                file_path,
                engine="openpyxl",
                mode="a",
                if_sheet_exists="overlay"
            ) as writer:

                for stock_name, df in stock_data_dict.items():

                    if stock_name not in writer.sheets:

                        df.to_excel(writer, sheet_name=stock_name)

                    else:

                        df.to_excel(
                            writer,
                            sheet_name=stock_name,
                            startrow=writer.sheets[stock_name].max_row,
                            header=False
                        )

                    logging.info(f"Updated sheet: {stock_name}")

        print(f"[SAVE] Excel saved to: {file_path}")

    except Exception as e:

        traceback.print_exc()
        logging.error(f"Excel save failed: {e}")