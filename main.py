import re
import time
from urllib.parse import urljoin, urlparse
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, Timeout
from selenium.webdriver import Firefox, FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from utils import (
    find_all_pattern_matches,
    extract_content_from_tag,
    find_div_structure,
)
from get_links import keywords_list  # External file for keywords

# Constants
INPUT_CSV_PATH = "apollo-accounts-export.csv"
CAREERS = "careers/"


class JobsScrapperCrunchbase:
    def __init__(self, input_csv_path, keywords_list):
        """Initialise the scrapper class."""
        self.driver = None
        self.input_csv_path = input_csv_path
        self.output_csv_path = "jobs.csv"
        self.keywords_list = keywords_list

    # Utility Methods
    def seconds_to_structured_format_time(self, secs):
        """Convert seconds to a structured time format."""
        gmt_format = time.gmtime(secs)
        return time.strftime("%H:%M:%S", gmt_format)

    # Browser Configuration
    def configure_browser(self):
        """Configure the browser settings."""
        firefox_options = FirefoxOptions()
        # firefox_options.add_argument("--headless")
        # firefox_options.add_argument("--no-sandbox")
        firefox_options.add_argument("--log-level=3")
        firefox_options.add_argument("--disable-dev-shm-usage")
        firefox_options.add_argument("--disable-extensions")
        firefox_options.add_argument("--disable-gpu")
        firefox_options.add_argument("start-maximized")
        firefox_options.add_argument(
            "--disable-blink-features=AutomationControlled"  # noqa
        )
        firefox_options.add_argument("--disable-infobars")
        self.driver = Firefox(options=firefox_options)

    # Page Interactions
    def open_url_in_driver(self, url):
        """Open URL in the selenium driver."""
        try:
            self.driver.get(url)
            time.sleep(3)
        except Exception:
            self.driver.refresh()

    def accept_cookies(self):
        # wait until popup loads
        time.sleep(3)

        # try to click directly if button is available
        try:
            self.driver.find_element(
                By.XPATH, "//*[contains(text(), 'Accept')]"
            ).click()
            return
        except Exception:
            ...

        time.sleep(1)
        soup_obj = self.selenium_driver_obj_to_soup_obj()

        def tag_name_to_text_getter(tag_names):
            """
            Helper function to get the texts of the based on the given tags list
            """
            for tag_name in tag_names:
                tags_list = soup_obj.find_all(tag_name)
                buttons_text = [tag.text for tag in tags_list if "Accept" in tag.text]
                if buttons_text:
                    button_text = buttons_text[0].replace("\n", "").strip()
                    return button_text

        button_tag_names = ["a", "button"]

        button_text = tag_name_to_text_getter(button_tag_names)
        if button_text:
            self.driver.find_element(
                By.XPATH, f"//*[contains(text(), '{button_text}')]"
            ).click()
            time.sleep(3)

    def selenium_driver_obj_to_soup_obj(self, do_clean=False):
        """Convert Selenium driver object to BeautifulSoup object."""
        page_source = self.driver.page_source
        soup_object = BeautifulSoup(page_source, "html.parser")
        if do_clean:
            soup_object = self.clean_html(soup_object)
        return soup_object

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

    def clean_html(self, soup_obj):
        """Clean the HTML content from unwanted tags."""
        # Parse the HTML content using BeautifulSoup
        # Extract only the body tag
        body_tag = soup_obj.find("body")

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

        # Remove extra spaces using regex
        cleaned_html = re.sub(r"\s+", " ", str(body_tag))

        return BeautifulSoup(cleaned_html, "html.parser")

    def build_complete_link(self, link, scheme="http", domain="example.com"):
        """Build a complete link from a partial link."""
        # Handle special cases like 'javascript:void(0)'
        if CAREERS in link and CAREERS in domain:
            link = link.replace(CAREERS, "")

        if "javascript:" in link:
            return None
        elif link[0] == "/":
            domain += link[1:]
            return domain

        # Check if the scheme is present in the link
        if scheme not in link:
            domain += link
            return domain

        return link

    # Data Handling
    def read_csv(self):
        """Read input CSV."""
        df = pd.read_csv(self.input_csv_path)

        if "Career Link" not in df.columns:
            df["Career Link"] = None

        # Keep only the columns 'Company', 'Website', and 'Career Link'
        columns_to_keep = ["Company", "Website", "Career Link"]
        df = df[columns_to_keep]

        return df

    def write_csv(self, df):
        """Write DataFrame to CSV."""
        df.to_csv(self.input_csv_path, index=False)

    def get_job_links_from_indexing_page(self, soup):
        most_repeated_structure = find_div_structure(soup)
        if most_repeated_structure:
            # Parse the most repeated div structure and extract the tags
            most_repeated_soup = BeautifulSoup(
                most_repeated_structure,
                "html.parser",
            )
            # Initialize an empty list to store the tags in the desired order
            tag_list = []

            # Function to traverse the tree and
            # extract tags in the desired order
            def extract_tags(node):
                if node.name:
                    tag_list.append(node.name)
                    for child in node.children:
                        extract_tags(child)

            # Start the traversal from the root of the parsed structure
            for child in most_repeated_soup.children:
                extract_tags(child)
            # # Remove duplicate entries while preserving the order
            # tag_list = list(dict.fromkeys(tag_list))​
            # Now, tag_list contains the desired list of tags
            target_pattern = tag_list
            # Find all elements that match the target pattern
            matching_elements = find_all_pattern_matches(soup, target_pattern)

            if matching_elements:
                # Extract and print the content from the
                # 'a' tag within the matching elements
                content_list = extract_content_from_tag(matching_elements, "a")
                return content_list

    def write_jobs_in_csv(self, new_row, output_csv_path):
        """Write DataFrame to output CSV."""

        # Columns for the DataFrame
        columns = [
            "Website",
            "Job URL",
            "Job Title",
            "Job Description",
        ]

        # Check if the output CSV already exists
        if os.path.exists(output_csv_path):
            # If it does, read it into a DataFrame
            df = pd.read_csv(output_csv_path)
        else:
            # If it doesn't, create an empty
            # DataFrame with the specified columns
            df = pd.DataFrame(columns=columns)

        # Check if the new_row already exists in the DataFrame
        if not df[
            (df["Career Link"] == new_row["Career Link"])
            & (df["Job Title"] == new_row["Job Title"])
        ].empty:
            print("Row already exists. Skipping.")
            return

        # Append the new_row to the DataFrame
        df = df.append(new_row, ignore_index=True)

        # Save the updated DataFrame to CSV
        df.to_csv(output_csv_path, index=False)

    # Core Functionality
    def main(self):
        """Main execution logic."""
        self.configure_browser()
        df = self.read_csv()

        for index, row in df.iterrows():
            if index == 0:
                continue
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
                self.write_csv(df)

                self.open_url_in_driver(career_link)
                self.accept_cookies()

                soup_obj = self.selenium_driver_obj_to_soup_obj(do_clean=True)

                jobs_link = self.get_job_link_from_button(soup_obj)

                if jobs_link:
                    jobs_link = self.build_complete_link(
                        jobs_link, scheme="http", domain=career_link
                    )

                    self.open_url_in_driver(jobs_link)

                    soup_obj = self.selenium_driver_obj_to_soup_obj(
                        do_clean=True,
                    )

                    all_jobs_links = self.get_job_links_from_indexing_page(
                        soup_obj,
                    ) or []

                    for link in all_jobs_links:
                        link = self.build_complete_link(
                            link["href"], scheme="http", domain=jobs_link
                        )
                        print(link)
                        self.open_url_in_driver(link)

                        soup_obj = self.selenium_driver_obj_to_soup_obj(
                            do_clean=True,
                        )

                        jd, title = self.get_jd_and_title(soup_obj)
                        print(jd, title)

                        self.write_jobs_in_csv(
                            {
                                "Website": website_url,
                                "Job URL": link,
                                "Job Title": title,
                                "Job Description": jd,
                            },
                            self.output_csv_path,
                        )


if __name__ == "__main__":
    scrapper = JobsScrapperCrunchbase(INPUT_CSV_PATH, keywords_list)
    scrapper.main()
