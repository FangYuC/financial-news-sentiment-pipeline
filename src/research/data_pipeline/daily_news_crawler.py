import logging
import os
import argparse
import sys
import random
import json
import certifi
import traceback
import requests
import time
import re
import urllib
import urllib.request
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# from seleniumwire import webdriver

from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from tqdm import tqdm

from src.research.utils.logging import setup_logging
from src.research.services.db_service import save_data_tosql

logger = setup_logging()


def simplify_change(text):
    """Fix like 3.06%increase; green up pointing triangle -> (3.06%increase) in WSJ.

    Args:
        text (str): article content

    Returns:
        str: (xx.xx%increase) or (xx.xx%decrease)
    """
    pattern = r"(-?\d+\.?\d*%\s*(increase|decrease))(;?\s*(red|green)?\s*(up|down)?\s*pointing\s*triangle)?"

    if text is None:  # 檢查是否為 None
        return ""

    return re.sub(pattern, r"(\1)", text)


class NYT:
    def __init__(self) -> None:
        self.base_url = "https://www.nytimes.com/sitemap"

    def get_nytimes_data(self, start_date, end_date):
        current_date = start_date

        data = pd.DataFrame(columns=["Date", "Headline", "Provider", "URL"])
        process_bar = tqdm(total=(end_date - start_date).days + 1)

        while current_date <= end_date:
            year, month, day = current_date.year, current_date.month, current_date.day
            url = f"{self.base_url}/{year}/{month:0>2}/{day:0>2}"

            response = requests.get(url)
            html = BeautifulSoup(response.text, "html.parser")
            ul_elements = html.select_one("ul.css-d7lzgg")
            unique_ul_elements = set()

            for ul_element in ul_elements:
                if ul_element not in unique_ul_elements:
                    li_elements = ul_element.find_all("a")

                    for link_element in li_elements:
                        link = link_element["href"]
                        match = re.search(r"(\d{4}/\d{2}/\d{2})", link)
                        if match:
                            date_str = match.group(1)
                            date = datetime.strptime(
                                date_str, "%Y/%m/%d").date()
                            if date != current_date:
                                continue

                            headline = link_element.get_text()
                            not_eng = re.compile(r"[^\x00-\x7F]+")
                            if not_eng.search(headline) is None:
                                # print(f"date: {date}, headline: {headline}")
                                data.loc[len(data)] = [
                                    date,
                                    headline,
                                    "NYT",
                                    link,
                                ]

            process_bar.update(1)
            delay_choices = [7, 5, 10, 6, 20, 14]
            delay = random.choice(delay_choices)
            time.sleep(delay)
            current_date += timedelta(days=1)

        process_bar.close()
        logging.info(f"Successfully saved NYTimes data at {end_date}")

        return data


class WSJ:
    def __init__(self) -> None:
        self.base_url = "https://www.wsj.com/news/archive"
        self.chromedriver_path = r"D:\chromedriver-win64\chromedriver.exe"

    def get_wsj_data(self, start_date, end_date):
        try:
            service = Service(executable_path=self.chromedriver_path)
            options = Options()
            # options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
            driver = webdriver.Chrome(service=service, options=options)
            driver.implicitly_wait(7)

            current_date = start_date

            data = []

            process_bar = tqdm(total=(end_date - start_date).days + 1)

            while current_date <= end_date:
                year, month, day = (
                    current_date.year,
                    current_date.month,
                    current_date.day,
                )
                url = f"{self.base_url}/{year}/{month:0>2}/{day:0>2}"

                driver.get(url)
                # time.sleep(45)
                # print("Times up.")

                headlines = driver.find_elements(
                    By.CLASS_NAME, "WSJTheme--headline--7VCzo7Ay"
                )
                sections = driver.find_elements(
                    By.CLASS_NAME, "WSJTheme--articleType--34Gt-vdG"
                )
                times = driver.find_elements(
                    By.CLASS_NAME, "WSJTheme--timestamp--22sfkNDv"
                )

                urls = []

                for headline in headlines:
                    urls_link = headline.find_element(By.TAG_NAME, "a")
                    # print(urls_link)
                    urls.append(urls_link.get_attribute("href"))

                for headline, section, url_link, time_ in zip(
                    headlines, sections, urls, times
                ):
                    time_ = time_.text
                    time_ = time_.replace("ET", "").strip()
                    time_ = datetime.strptime(time_, "%I:%M %p").time()
                    date = datetime.combine(current_date, time_)

                    data.append(
                        {
                            "Date": date,
                            "Section": section.text,
                            "Headline": headline.text,
                            "Provider": "WSJ",
                            "URL": url_link,
                        }
                    )

                try:
                    while True:
                        next_page_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable(
                                (By.XPATH, "//span[text()='Next Page']")
                            )
                        )

                        if next_page_button:
                            logging.info(f"{current_date} Next Page.")
                            driver.execute_script(
                                "arguments[0].click();", next_page_button
                            )

                            WebDriverWait(driver, 120).until(
                                EC.staleness_of(next_page_button)
                            )

                            headlines = driver.find_elements(
                                By.CLASS_NAME, "WSJTheme--headline--7VCzo7Ay"
                            )
                            sections = driver.find_elements(
                                By.CLASS_NAME, "WSJTheme--articleType--34Gt-vdG"
                            )
                            times = driver.find_elements(
                                By.CLASS_NAME, "WSJTheme--timestamp--22sfkNDv"
                            )

                            for headline in headlines:
                                urls_link = headline.find_element(
                                    By.TAG_NAME, "a")
                                # print(urls_link)
                                urls.append(urls_link.get_attribute("href"))

                            for headline, section, url_link, time_ in zip(
                                headlines, sections, urls, times
                            ):
                                time_ = time_.text
                                time_ = time_.replace("ET", "").strip()
                                time_ = datetime.strptime(
                                    time_, "%I:%M %p").time()
                                date = datetime.combine(current_date, time_)

                                data.append(
                                    {
                                        "Date": date,
                                        "Section": section.text,
                                        "Headline": headline.text,
                                        "Provider": "WSJ",
                                        "URL": url_link,
                                    }
                                )

                except (NoSuchElementException, TimeoutException):
                    logging.info(
                        f"Moving to the next day({current_date + timedelta(days=1)})."
                    )
                    pass

                process_bar.update(1)
                current_date += timedelta(days=1)

                delay_choices = [7, 5, 10, 6, 20, 14]
                delay = random.choice(delay_choices)
                time.sleep(delay)

            process_bar.close()

            df = pd.DataFrame(data)

            logging.info(f"Successfully saved WSJ data at {end_date}")

            # 關閉瀏覽器
            driver.quit()

            return df

        except Exception as e:
            logging.error(e)
            driver.quit()

    def get_wsj_article_content(self, df: pd.DataFrame) -> pd.DataFrame:
        data = []
        session = None

        try:
            session = requests.Session()
            # retry_strategy = Retry(
            #     total=3,  # 最多重試 3 次
            #     backoff_factor=1,  # 指數退避因子
            #     status_forcelist=[429, 500, 502, 503, 504],  # 哪些狀態碼需要重試
            # )
            # adapter = HTTPAdapter(max_retries=retry_strategy)
            # session.mount("https://", adapter)

            df = df.sort_values(by="Date")
            urls = df["URL"]

            logger.info("Parse the article.")
            process_bar = tqdm(total=len(urls))
            for url in urls:
                # google_cache_url = (
                #     "https://webcache.googleusercontent.com/search?q=cache:" + url[7:]
                # )
                # wayback_url = f"https://web.archive.org/web/20230000000000*/{url}"

                params = {
                    "id": json.dumps(
                        {"application": "WSJ", "marketsDiaryType": "overview"}
                    ),
                    "type": "mdc_marketsdiary",
                }

                user_agents = [
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                ]

                headers = {
                    "User-Agent": random.choice(user_agents),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                }

                # session.headers.update(headers)
                try:
                    response = session.get(
                        url,  # google_cache_url, wayback_url
                        headers=headers,
                        params=params,
                        verify=certifi.where(),
                    )  # , allow_redirects=False

                    time.sleep(random.uniform(5, 10))

                    if response.status_code == 200:
                        html = BeautifulSoup(response.text, "html.parser")

                        content_list = [
                            p.text
                            for p in html.find_all(
                                "p",
                                attrs={"data-type": "paragraph"},
                                class_=[
                                    "css-k3zb6l-Paragraph e1e4oisd0",
                                    "css-1akm6h5-Paragraph e1e4oisd0",
                                ],
                            )
                        ]
                        content = " ".join(
                            content_list) if content_list else ""
                        content = simplify_change(content)
                        content_1 = (
                            simplify_change(content_list[0])
                            if len(content_list) > 0
                            else ""
                        )
                        content_2 = (
                            simplify_change(content_list[1])
                            if len(content_list) > 1
                            else ""
                        )

                        subheadline = html.find(
                            "h2",
                            class_=[
                                "css-jiugt2-Dek-Dek e1jnru6p0",
                                "css-nqdt4q-Dek-Dek-SplitTopDek e1fgnxat5",
                                "etjy8xo0 css-1adf603-DekBlock",
                                "css-ikn547-Dek-Dek-BigTopDek e10dsoc81",
                                "css-1964saf-NormalDek-NormalDek-Styled-Styled-Styled emwm06f0",
                                "etjy8xo0 css-99tqod-DekBlock",
                                "css-d3ge02-NormalDek-NormalDek-Styled-Styled-Styled emwm06f0",
                            ],
                        )
                        subheadline = subheadline.text if subheadline else ""

                        data.append(
                            {
                                "URL": url,
                                "Content": content,
                                "Subheadline": subheadline,
                                "Content_1": content_1,
                                "Content_2": content_2,
                            }
                        )

                        process_bar.update(1)

                    elif response.status_code == 429:
                        retry_after = response.headers.get("Retry-After")
                        wait_time = (
                            int(retry_after)
                            if retry_after and retry_after.isdigit()
                            else random.uniform(60, 120)
                        )
                        logger.warning(
                            f"429 Too Many Requests for {url}, waiting {wait_time} seconds..."
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Failed to retrieve content from {url}, status code: {response.status_code}"
                        )

                except requests.exceptions.RequestException as e:
                    logger.error(f"Error fetching {url}: {e}")

                time.sleep(random.uniform(5, 15))

            data = pd.DataFrame(data)
            process_bar.close()

            return data

        except Exception as e:
            logging.error(e)
            return None, None

        finally:
            if session is not None:
                session.close()


class CNBC:
    def __init__(self) -> None:
        self.base_url = "https://www.cnbc.com/site-map/articles"
        self.chromedriver_path = r"D:\chromedriver-win64\chromedriver.exe"

    def get_cnbc_url(self, start_date, end_date):
        """動態爬蟲抓新聞網址"""
        try:
            service = Service(executable_path=self.chromedriver_path)
            options = Options()
            driver = webdriver.Chrome(service=service, options=options)

            driver.implicitly_wait(10)

            current_date = start_date

            url_data = []

            while current_date <= end_date:
                year, day = current_date.year, current_date.day
                month = current_date.strftime("%B")
                url = f"{self.base_url}/{year}/{month}/{day}/"

                driver.get(url)

                try:
                    WebDriverWait(driver, 45).until(
                        EC.visibility_of_element_located(
                            (By.CLASS_NAME, "SiteMapArticleList-emptyPage")
                        )
                    )
                    logging.info(f"No articles found {current_date}")
                    current_date += timedelta(days=1)
                    continue  # Move to the next iteration of the loop
                except TimeoutException:
                    pass

                WebDriverWait(driver, 200).until(
                    EC.visibility_of_element_located(
                        (By.XPATH,
                         "//a[contains(@class, 'SiteMapArticleList-link')]")
                    )
                )

                headline_links = driver.find_elements(
                    By.XPATH, "//a[contains(@class, 'SiteMapArticleList-link')]"
                )
                logging.info(
                    f"{current_date} has {len(headline_links)} articles.")

                for link in headline_links:
                    href = link.get_attribute("href")
                    url_data.append(
                        {"Date": current_date, "article_url": href})

                delay_choices = [7, 5, 10, 6, 20, 14]
                delay = random.choice(delay_choices)
                time.sleep(delay)
                current_date += timedelta(days=1)

            url_data = pd.DataFrame(url_data)

            try:
                file = "cnbc_news_url.csv"
                if not os.path.exists(file):
                    url_data.to_csv(file, index=False)

                else:
                    url_data.to_csv(file, mode="a", header=False, index=False)

            except Exception as e:
                logging.error(f"Failed to save urls to csv. {e}")

            driver.quit()
            logging.info("Successfully save urls.")

            return url_data

        except Exception as e:
            logging.error(
                "Error occurred while fetching data for %s: %s", current_date, str(
                    e)
            )

            url_data = pd.DataFrame()

    def get_cnbc_data_date(self, urls):
        """靜態爬蟲"""
        try:
            date = urls["Date"]
            article_urls = urls["article_url"]

            data = []

            for d, url in zip(date, tqdm(article_urls, desc="Processing")):
                match = re.search(r"(\d{4})[-/]?(\d{2})[-/]?(\d{2})", url)

                if match:
                    year, month, day = match.groups()
                    d = f"{year}-{month}-{day}"
                    d = datetime.strptime(d, "%Y-%m-%d").date()

                    session = requests.Session()

                    params = {
                        "id": '{"application":"CNBC","marketsDiaryType":"overview"}',
                        "type": "mdc_marketsdiary",
                    }

                    headers = {
                        # Mozilla/5.0 (Windows NT 10.0; Win64; x64)
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
                    }

                    response = session.get(url, headers=headers, params=params)

                    html = BeautifulSoup(response.text, "html.parser")
                    # print(html)
                    headlines = html.find_all(class_="ArticleHeader-headline")
                    # print(headlines)
                    key_points_list = html.find(
                        "div", class_="RenderKeyPoints-list")

                    key_points = ""
                    if key_points_list:
                        key_points_items = key_points_list.find_all("li")
                        for key_point in key_points_items:
                            key_points += key_point.text + " "

                        key_points = key_points.strip()
                        # print(key_points)
                    else:
                        key_points = ""

                    # print(key_points)

                    time_tag = html.find(
                        "time", {"data-testid": "published-timestamp"})
                    if time_tag:
                        time_part = time_tag.contents[-1]
                        time_clean = (
                            time_part.replace("EST", "").replace(
                                "EDT", "").strip()
                        )
                        time_24 = datetime.strptime(
                            time_clean, "%I:%M %p").time()
                        date = datetime.combine(d, time_24)

                    for headline in headlines:
                        headline = headline.text

                        section = ""
                        try:
                            section = html.find_all(
                                "a", class_="ArticleHeader-eyebrow")
                            section = ", ".join([c.text for c in section])

                        except NoSuchElementException:
                            logging.info(f"{headline}: No section.")

                        section = section if section else ""

                        data.append(
                            {
                                "Date": date,
                                "Section": section,
                                "Headline": headline,
                                "Provider": "CNBC",
                                "URL": url,
                                "Key_Point": key_points,
                            }
                        )

                        delay_choices = [7, 5, 10, 6, 20, 14]
                        delay = random.choice(delay_choices)
                        time.sleep(delay)

            df = pd.DataFrame(data)

            logging.info("Successfully saved CNBC data")

        except Exception as e:
            logging.error("Error occurred while fetching data: %s", str(e))
            df = pd.DataFrame()

        return df

    def get_cnbc_data(self, start_date, end_date):
        """動態爬蟲"""
        try:
            service = Service(executable_path=self.chromedriver_path)
            options = Options()
            driver = webdriver.Chrome(service=service, options=options)

            time.sleep(5)

            driver.implicitly_wait(10)

            current_date = start_date

            data = []

            while current_date <= end_date:
                year, day = current_date.year, current_date.day
                month = current_date.strftime("%B")
                url = f"{self.base_url}/{year}/{month}/{day}/"

                driver.get(url)

                article_links = driver.find_elements(
                    By.CLASS_NAME, "SiteMapArticleList-link"
                )

                logging.info(
                    f"{current_date} has {len(article_links)} articles.")

                if not article_links:
                    logging.info(f"No articles found for {current_date}")
                    current_date += timedelta(days=1)
                    continue

                for index in tqdm(
                    range(len(article_links)), desc=f"Processing {current_date}"
                ):
                    # for article in range(len(article_links)):
                    try:
                        article_links = driver.find_elements(
                            By.CLASS_NAME, "SiteMapArticleList-link"
                        )
                        link = article_links[index]
                        # print(f"Processing {current_date} article {index + 1} of {len(article_links)}")

                        ActionChains(driver).move_to_element(
                            link).click(link).perform()

                        WebDriverWait(driver, 180).until(
                            EC.visibility_of_element_located(
                                (By.CLASS_NAME, "ArticleHeader-headline")
                            )
                        )
                        # .until(EC.url_changes)
                        # #.until(EC.presence_of_all_elements_located((By.CLASS_NAME, "SiteMapArticleList-link")))

                        headline = driver.find_element(
                            By.CLASS_NAME, "ArticleHeader-headline"
                        )

                        key_points_list = driver.find_element(
                            By.CLASS_NAME, "RenderKeyPoints-list"
                        )
                        key_points = key_points_list.find_elements(
                            By.TAG_NAME, "li")

                        time_ = driver.find_element(
                            By.CLASS_NAME, "ArticleHeader-time")
                        time_ = time_.text[-11:].strip()
                        time_ = time_.replace("EST", "").strip()
                        time_ = datetime.strptime(time_, "%I:%M %p").time()
                        date = datetime.combine(current_date, time_)
                        print(date)

                        for key_point in key_points:
                            key_point = key_point.text + " "
                            print(key_point)

                        section = None
                        try:
                            section = driver.find_element(
                                By.CLASS_NAME, "ArticleHeader-eyebrow"
                            )
                        except NoSuchElementException:
                            logging.info("No section.")

                        section = section.text if section else ""

                        data.append(
                            {
                                "Date": current_date,
                                "Section": section,
                                "Headline": headline.text,
                                "URL": link,
                                "Key_Point": key_point,
                            }
                        )

                        print(
                            f"add {current_date} data--section {section}, headline {headline.text}"
                        )

                    except Exception as e:
                        logging.error(
                            "Error occurred while processing article: %s",
                            str(e),
                            exc_info=True,
                        )

                    driver.back()

                    WebDriverWait(driver, 15).until(EC.url_changes)

                delay_choices = [7, 5, 10, 6, 20, 14]
                delay = random.choice(delay_choices)
                time.sleep(delay)
                current_date += timedelta(days=1)

            df = pd.DataFrame(data)
            df["Provider"] = "CNBC"
            duplicates = df.duplicated()
            print(duplicates)
            logging.info(f"Successfully saved CNBC data at {end_date}")

            driver.quit()

        except Exception as e:
            logging.error(
                "Error occurred while fetching data for %s: %s", current_date, str(
                    e)
            )

            df = pd.DataFrame()

        return df


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
        help="Save to database",
    )
    parser.add_argument(
        "-p", "--provider", type=str, help="Data provider (e.g., NYT, WSJ or CNBC)"
    )
    parser.add_argument(
        "-a",
        "--article",
        action="store_false",
        required=False,
        help="Get contents of articles.",
    )

    args = parser.parse_args()

    logging.info(
        "--------------------------------------------------------------------------------------------"
    )
    logging.info("Start executing the program.")

    start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()

    nyt = NYT()
    wsj = WSJ()
    cnbc = CNBC()

    if args.provider.lower() == "nyt":
        data = nyt.get_nytimes_data(start_date, end_date)

    elif args.provider.lower() == "wsj":
        data = wsj.get_wsj_data(start_date, end_date)
        # data['Text'] = pd.concat([])

    elif args.provider.lower() == "cnbc":
        urls = cnbc.get_cnbc_url(start_date, end_date)
        data = cnbc.get_cnbc_data_date(urls)

        # news_url = pd.read_csv("cnbc_news_url.csv")
        # urls = news_url[news_url["Date"] == '2014-01-31']
        # urls = urls.drop_duplicates()
        # data = get_cnbc_data_(urls)
        # urls = news_url[news_url["Date"] == '2014-01-31']
        # urls = urls.drop_duplicates()
        # data = get_cnbc_data_(urls)
        # logging.info(f"Origin amounts of the data: {len(urls)}")

    else:
        print("Invalid provider. Please specify either 'NYT' or 'WSJ' or 'CNBC'.")
        sys.exit(1)

    print(f"origin data: {data}")
    print(f"repeat data: {data[data.duplicated()]}")
    data.drop_duplicates(keep="last", inplace=True)  #
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
    # data.drop(data[data["Headline"].str.contains('Recipe: ')].index, inplace=True)
    # data.drop(data[data["Headline"].str.contains('Correction: For The Record')].index, inplace=True)
    # data.drop(data[data["Headline"].str.contains("CORRECTIONS: FOR THE RECORD")].index, inplace=True)

    print(f"drop: {data}")

    if args.database:
        if args.provider.lower() == "wsj":
            save_data_tosql(data, table_name="wsj_url")
        else:
            save_data_tosql(data, table_name=args.provider.lower())

    else:
        data.to_csv(
            f"{args.start_date}_{args.end_date}_{args.provider.lower()}")

    logging.info("Program execution completed.")
