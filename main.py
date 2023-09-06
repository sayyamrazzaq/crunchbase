import re
import time
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, Timeout
from selenium.webdriver import Firefox, FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from get_links import keywords_list

input_csv_path = "apollo-accounts-export.csv"


class Jobs_scrapper_crunshbase:
    def __init__(self, input_csv_path, keywords_list):
        self.driver = None
        self.input_csv_path = input_csv_path
        self.keywords_list = keywords_list

    def seconds_to_structured_format_time(self, secs):
        gmt_format = time.gmtime(secs)
        structured_time = time.strftime("%H:%M:%S", gmt_format)
        return structured_time

    def accept_cookies(self):
        try:
            # Wait for the cookie pop-up to appear,
            # then click the "Accept" button
            wait = WebDriverWait(self.driver, 10)
            accept_button = wait.until(
                EC.element_to_be_clickable(
                    (
                        By.XPATH,
                        "//button[text()='Accept']",
                    )
                )
            )
            accept_button.click()
        except Exception:
            pass

    def selenium_driver_obj_to_soup_obj(self, do_clean=False):
        page_source = self.driver.page_source
        soup_object = BeautifulSoup(page_source, "html.parser")
        if do_clean:
            soup_object = self.clean_html(soup_object)
        return soup_object

    def build_complete_link(self, link, scheme="http", domain="example.com"):
        if scheme not in link:
            domain += link
            return domain
        return link

    def configure_browser(self):
        firefox_options = FirefoxOptions()
        firefox_options.add_argument("--log-level=3")
        # firefox_options.add_argument("--headless")
        firefox_options.add_argument("--disable-dev-shm-usage")
        firefox_options.add_argument("--disable-extensions")
        firefox_options.add_argument("--disable-gpu")
        # firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("start-maximized")
        firefox_options.add_argument(
            "--disable-blink-features=AutomationControlled"
        )  # noqa
        firefox_options.add_argument("--disable-infobars")

        # Initialize Firefox driver
        self.driver = Firefox(
            # executable_path="./geckodriver",
            options=firefox_options,
        )

    def clean_html(self, soup_obj):
        # Parse the HTML content using BeautifulSoup
        tags_list = [
            "script",
            "img",
            "video",
            "audio",
            "noscript",
            "iframe",
            "svg",
            "footer",
            "nav",
            "header",
        ]

        for tag in tags_list:
            # Remove script tags
            for script in soup_obj.find_all(tag):
                script.decompose()

        # Keep only the button and text tags, but don't decompose <body>
        for tag in soup_obj.find_all(True):
            allowed_attrs = ["id", "class", "href"]
            tag.attrs = {
                key: value
                for key, value in tag.attrs.items()
                if key in allowed_attrs  # noqa
            }

        # Extract only the body tag
        body_tag = soup_obj.find("body")

        # Remove extra spaces using regex
        cleaned_html = re.sub(r"\s+", " ", str(body_tag))

        return BeautifulSoup(cleaned_html, "html.parser")

    def find_career_page(self, domain, soup):
        keywords = [
            "career",
            "careers",
            "employment",
            "opportunities",
            "vacancies",
            "recruitment",
            "hiring",
            "work",
            "join-us",
            "job-listings",
            "jobs",
        ]

        for link in soup.find_all("a"):
            for keyword in keywords:
                if keyword in link["href"]:
                    return link["href"]

        headers = {
            "User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)",
        }

        # Check if 'careers' is a subdomain
        parsed_url = urlparse(domain)
        for subdomain in [
            "careers",
            "recruitment",
            "jobs",
            "employment",
            "opportunities",
            "vacancies",
            "hiring",
            "join",
            "work",
            "jobboard",
        ]:
            career_subdomain = f"https://{subdomain}.{parsed_url.netloc}"

            try:
                response = requests.get(
                    career_subdomain,
                    headers=headers,
                    timeout=10,
                )
                if response.status_code == 200:
                    return career_subdomain
            except (ConnectionError, Timeout):
                ...
                # print(f"Failed to connect to {career_subdomain}")

        # Check common career paths
        career_paths = [
            "/careers",
            "/jobs",
            "/career",
            "/employment",
            "/opportunities",
            "/join-us",
            "/work-with-us",
            "/vacancies",
            "/job-openings",
            "/recruitment",
            "/hiring",
            "/work-for-us",
            "/job-listings",
            "/career-opportunities",
            "/job-search",
        ]
        for path in career_paths:
            url = urljoin(domain, path)
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return url
            except Exception as e:
                print(e)
                return None

        # Check sitemap
        sitemap_paths = [
            "/sitemap.xml",
            "/sitemap_index.xml",
        ]
        for sitemap_path in sitemap_paths:
            sitemap_url = urljoin(domain, sitemap_path)
            response = requests.get(sitemap_url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "xml")
                urls = soup.find_all("loc")
                for url in urls:
                    if any(
                        keyword in url.text
                        for keyword in [
                            "career",
                            "job",
                            "employment",
                            "opportunity",
                        ]
                    ):
                        return url.text

        return None

    def read_csv(self, input_csv_path):
        return pd.read_csv(input_csv_path)

    def open_url_in_driver(self, url):
        try:
            self.driver.get(url)
        except:
            self.driver.refresh()

    def main(self):
        df = self.read_csv(self.input_csv_path)

        for _, row in df.iterrows():
            website_url = row["Website"]

            print(website_url)

            if "https" not in website_url:
                website_url = website_url.replace("http", "https")

            self.open_url_in_driver(website_url)
            self.accept_cookies()

            soup_obj = self.selenium_driver_obj_to_soup_obj()

            career_link = self.find_career_page(website_url, soup_obj)
            print("career_link", career_link)
            if not career_link:
                continue

            if career_link:
                self.open_url_in_driver(career_link)

                soup_obj = self.selenium_driver_obj_to_soup_obj(do_clean=True)

                jobs_link = self.get_job_link_from_button(soup_obj)
                print(jobs_link)
                if jobs_link:
                    jobs_link = self.build_complete_link(
                        jobs_link, scheme="http", domain=career_link
                    )
                    print("after build", jobs_link)
                    self.open_url_in_driver(jobs_link)

                    soup_obj = self.selenium_driver_obj_to_soup_obj(
                        do_clean=True,
                    )

                    all_jobs_links = self.get_all_job_links(soup_obj)
                    print('All Jobs Links', all_jobs_links)
                    for link in all_jobs_links:
                        print(link)
                        self.open_url_in_driver(link)

                        soup_obj = self.selenium_driver_obj_to_soup_obj(
                            do_clean=True,
                        )

    def get_job_link_from_button(self, soup):
        links = soup.find_all("a")
        keywords_list = [keyword.lower() for keyword in self.keywords_list]
        for link in links:
            text = link.text.lower()
            if text in keywords_list:
                return link.get("href")

    def get_all_job_links(self, div):
        list_of_jobs = []
        anchor_elements = div.find_all("a")
        for anchor in anchor_elements:
            list_of_jobs.append(
                {
                    "content": anchor.text,
                    "href": anchor.get("href"),
                },
            )
        return list_of_jobs

    def get_jd_and_title(self, soup):
        content = []
        for p in soup.find_all("p"):
            content.append(p.text)

        return "\n\n".join(content), self.driver.title


if __name__ == "__main__":
    class_obj = Jobs_scrapper_crunshbase(input_csv_path, keywords_list)
    class_obj.configure_browser()
    class_obj.main()
