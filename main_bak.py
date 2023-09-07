import re
import time
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, Timeout
from selenium.webdriver import Firefox, FirefoxOptions
from selenium.webdriver.common.by import By

# from selenium.webdriver.support import expected_conditions as EC
# from selenium.webdriver.support.ui import WebDriverWait

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

    def accept_cookies_clicker(self):
        # wait until popup loads
        time.sleep(3)

        # try to click directly if button is available
        try:
            self.driver.find_element(
                By.XPATH, "//*[contains(text(), 'Accept')]"
            ).click()
        except Exception:
            ...

        time.sleep(1)
        soup_obj = self.selenium_driver_obj_to_soup_obj()
        # print(soup_obj)

        def tag_name_to_text_getter(tag_names):
            """
            Helper function to get the texts
            of the based on the given tags list
            """
            for tag_name in tag_names:
                tags_list = soup_obj.find_all(tag_name)
                buttons_text = [
                    tag.text for tag in tags_list if "Accept" in tag.text
                ]  # noqa
                if buttons_text:
                    button_text = buttons_text[0].replace("\n", "").strip()
                    print("--" + button_text + "--")
                    return button_text

        button_tag_names = ["a", "button"]

        button_text = tag_name_to_text_getter(button_tag_names)
        if button_text:
            self.driver.find_element(
                By.XPATH, f"//*[contains(text(), '{button_text}')]"
            ).click()

            time.sleep(3)

    def selenium_driver_obj_to_soup_obj(self, do_clean=False):
        page_source = self.driver.page_source
        soup_object = BeautifulSoup(page_source, "html.parser")
        if do_clean:
            soup_object = self.clean_html(soup_object)
        return soup_object

    def build_complete_link(self, link, scheme="http", domain="example.com"):
        # Handle special cases like 'javascript:void(0)'
        if "javascript:" in link:
            return None

        # Check if the scheme is present in the link
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
            "--disable-blink-features=AutomationControlled"  # noqa
        )
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
                response = requests.get(
                    url,
                    headers=headers,
                    timeout=10,
                )
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
        df = pd.read_csv(input_csv_path)
        # Add a 'Career Link' column if it doesn't exist
        if "Career Link" not in df.columns:
            df["Career Link"] = None
        return df

    def write_csv(self, df, input_csv_path):
        df.to_csv(input_csv_path, index=False)

    def open_url_in_driver(self, url):
        try:
            self.driver.get(url)
        except Exception:
            self.driver.refresh()

    def main(self):
        df = self.read_csv(self.input_csv_path)

        for index, row in df.iterrows():
            website_url = row["Website"]
            career_link = row.get("Career Link", None)
            if not career_link:
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
                df.at[index, "Career Link"] = career_link
                self.write_csv(df, input_csv_path)

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
                    print("All Jobs Links", all_jobs_links)
                    for link in all_jobs_links:
                        link = self.build_complete_link(
                            link["href"], scheme="http", domain=jobs_link
                        )

                        self.open_url_in_driver(link)

                        soup_obj = self.selenium_driver_obj_to_soup_obj(
                            do_clean=True,
                        )

                        jd, title = self.get_jd_and_title(soup_obj)

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
