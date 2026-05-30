import argparse
import os
import sys

import pandas as pd

from datetime import datetime
from src.research.data_pipeline.sources.nyt import NYTCrawler
from src.research.data_pipeline.sources.wsj import WSJCrawler
from src.research.data_pipeline.sources.cnbc import CNBCCrawler
from src.research.services.db_service import save_data_tosql
from src.research.utils.io import save_csv
from src.research.utils.logging import setup_logging


logger = setup_logging()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--start_date",
        type=str,
        required=False,
        help="Start date in YYYY-MM-DD format",
        default="2008-01-01",
    )
    parser.add_argument(
        "-e",
        "--end_date",
        type=str,
        required=False,
        help="End date in YYYY-MM-DD format",
        default=f"{datetime.today().date()}",
    )
    parser.add_argument(
        "-d",
        "--database",
        action="store_false",
        required=False,
        help="Save to database or not",
    )
    parser.add_argument(
        "-p",
        "--provider",
        type=str,
        help="Data provider (e.g., NYT, WSJ or CNBC)",
        default="wsj",
    )

    args = parser.parse_args()

    file_name = os.path.basename(__file__)
    logger.info(
        "--------------------------------------------------------------------------------------------"
    )
    logger.info(f"Start executing the program: {file_name}.")

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    if args.provider.lower() == "nyt":
        nyt = NYTCrawler()
        data = nyt.get_nytimes_data(start_date, end_date)
        data.set_index("Date", inplace=True)

    elif args.provider.lower() == "wsj":
        wsj = WSJCrawler()
        data = wsj.get_wsj_data(start_date, end_date)
        # print(data)
        data.drop(
            data[data["Section"].str.contains(
                "PEPPER & SALT")].index, inplace=True
        )
        data.drop(data[data["Section"].str.contains(
            "LETTERS")].index, inplace=True)
        data.drop(data[data["Section"].str.contains(
            "BOOKSHELF")].index, inplace=True)
        data.drop(data[data["Section"].str.contains(
            "CROSSWORD")].index, inplace=True)
        data.drop(
            data[data["Section"].str.contains(
                "CROSSWORD CONTEST")].index, inplace=True
        )

        data.set_index("Date", inplace=True)
        data.sort_values(by=["URL", "Date"])

        data.drop_duplicates(subset="URL", keep="first", inplace=True)
        data.drop_duplicates(keep="first", inplace=True)
        data.sort_values(by="Date")

        # print(data)

        save_data_tosql(df=data, table_name="wsj_url")
        # data = load_data_from_sql(table_name="wsj_url")
        # data = data[(data["Date"] < "2014-05-24") & (data["Date"] > "2014-05-23")][5:6]
        print(f"wsj \n{data}")

        data.reset_index(inplace=True)
        article = wsj.get_wsj_article_content(data)
        data = pd.merge(data, article, on="URL", how="inner")
        data.set_index("Date", inplace=True)

        data["Sentence"] = data.apply(
            lambda row: (
                f"{row['Headline']}. {row['Subheadline']}"
                if row["Subheadline"].strip() != ""
                else row["Headline"]
            ),
            axis=1,
        )

        # print(data)

    elif args.provider.lower() == "cnbc":
        cnbc = CNBCCrawler()
        urls = cnbc.get_cnbc_url(start_date, end_date)
        save_data_tosql(df=urls, table_name="cnbc_url", index=False)
        # urls = pd.read_csv("D:/research/cnbc_news_url.csv")
        # urls = load_data_from_sql(table_name="cnbc_url")
        # urls = urls[urls["Date"] == "2025-09-30"]
        data = cnbc.get_cnbc_data_date(urls)
        data.set_index("Date", inplace=True)
        data = data.reset_index() 

        data["Sentence"] = data.apply(
            lambda row: (
                f"{row['Headline']}. {row['Key_Point']}"
                if row["Key_Point"].strip() != ""
                else row["Headline"]
            ),
            axis=1,
        )

    else:
        print("Invalid provider. Please specify either 'NYT' or 'WSJ' or 'CNBC'.")
        sys.exit(1)

    print(f"origin data: {data}")
    print(f"repeat data: {data[data.duplicated()]}")
    data.drop(
        data[
            (data["Headline"] == "Your Monday Briefing")
            | (data["Headline"] == "Your Tuesday Briefing")
            | (data["Headline"] == "Your Wednesday Briefing")
            | (data["Headline"] == "Your Thursday Briefing")
            | (data["Headline"] == "Your Friday Briefing")
        ].index,
        inplace=True,
    )
    data.drop_duplicates(inplace=True)

    print(f"clean data \n{data}")
    # print(data.columns)

    # print(f"drop: {data}")

    if args.database:
        save_data_tosql(df=data, table_name=f"{args.provider.lower()}")

    else:
        save_csv(data)

    logger.info("Program execution completed.")
