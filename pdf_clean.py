from bs4 import BeautifulSoup

def strip_some_tag(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")

    for s_tag in soup.find_all("s"):
        s_tag.unwrap()

    return str(soup)
