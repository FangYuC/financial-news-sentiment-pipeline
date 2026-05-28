from datetime import datetime

def generate_url(start_date, end_date, keyword, section=None):

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    keyword = keyword.replace(" ", "%20")

    base = "https://www.wsj.com/search"

    url = (
        f"{base}?query={keyword}"
        f"&isToggleOn=true&operator=OR"
        f"&sort=relevance&duration=1y"
        f"&startDate={start.year}%2F{start.month}%2F{start.day}"
        f"&endDate={end.year}%2F{end.month}%2F{end.day}"
    )

    if section:
        url += f"&meta={section}&source=wsjie%2Cblog"
    else:
        url += "&source=wsjie%2Cblog"

    return url
