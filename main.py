import os
import re
import time
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.exceptions import ConnectionError, Timeout
from selenium.webdriver import Firefox, FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from get_links import keywords_list  # External file for keywords
from job_description_n_job_title import heuristic_scrape
from utils import (
    extract_content_from_tag,
    find_all_pattern_matches,
    find_div_structure,
)

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
            try:
                self.driver.find_element(
                    By.XPATH, f"//*[contains(text(), '{button_text}')]"
                ).click()
                time.sleep(3)
            except Exception:
                pass

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
            url = self.build_complete_link(domain, path)
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
            sitemap_url = self.build_complete_link(domain, sitemap_path)
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

    def build_complete_link(self, link, domain="example.com"):
        # Handle javascript:void(0)
        if link.lower() == "javascript:void(0)":
            return None

        # Parse the base URL
        base_parsed = urlparse(domain)
        base_domain = f"{base_parsed.scheme}://{base_parsed.netloc}"

        # Parse the provided href
        href_parsed = urlparse(link)

        # Case 1: href is an absolute URL
        if href_parsed.scheme and href_parsed.netloc:
            return link

        # Case 2: href starts with a slash, meaning it's an absolute path
        if link.startswith("/"):
            return urlunparse(
                (
                    base_parsed.scheme,
                    base_parsed.netloc,
                    href_parsed.path,
                    "",
                    href_parsed.query,
                    "",
                )
            )

        # Case 3: href is just a fragment (e.g., #latest-vacancies)
        if link.startswith("#"):
            return f"{domain}{link}"

        # Case 4: href is a relative path (e.g., vacancies)
        return f"{domain}/{link}"

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
            print("Most Repeated <div> Structure:")
            print(" -> ".join(most_repeated_structure))
            tag_list = list(most_repeated_structure)
            # Find all elements that match the target pattern
            matching_elements = find_all_pattern_matches(soup, tag_list)
            if matching_elements:
                # Extract and print the content from the
                # 'a' tag within the matching elements
                return extract_content_from_tag(matching_elements, "a")

    def write_jobs_in_csv(self, new_row, output_csv_path):
        """Write DataFrame to output CSV."""

        # Columns for the DataFrame
        columns = ["Website", "Job URL", "Job Title", "Job Description"]

        # Check if the output CSV already exists
        if os.path.exists(output_csv_path):
            # If it does, read it into a DataFrame
            df = pd.read_csv(output_csv_path)
        else:
            # If it doesn't, create an empty
            # DataFrame with the specified columns
            df = pd.DataFrame(columns=columns)

        # Create a DataFrame from the new row
        new_df = pd.DataFrame([new_row], columns=columns)

        # Check if a similar row already exists in the DataFrame
        if not df[df["Job Title"] == new_row["Job Title"]].empty:
            print("Row already exists. Skipping.")
            return

        # Concatenate the existing and new DataFrames
        df = pd.concat([df, new_df], ignore_index=True)

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
                        jobs_link, domain=self.driver.current_url
                    )

                    self.open_url_in_driver(jobs_link)

                    soup_obj = self.selenium_driver_obj_to_soup_obj(
                        do_clean=True,
                    )

                    all_jobs_links = (
                        self.get_job_links_from_indexing_page(
                            soup_obj,
                        )
                        or []
                    )

                    for link in all_jobs_links:
                        link = self.build_complete_link(
                            link, domain=self.driver.current_url
                        )
                        print("Job link are", link)
                        self.open_url_in_driver(link)

                        soup_obj = self.selenium_driver_obj_to_soup_obj(
                            do_clean=True,
                        )

                        jobs_data = heuristic_scrape(soup_obj)
                        if jobs_data:
                            print("Job Personal Link is", link)
                            jobs_data["Website"] = website_url
                            jobs_data["Job URL"] = link
                            self.write_jobs_in_csv(
                                jobs_data,
                                self.output_csv_path,
                            )


if __name__ == "__main__":
    scrapper = JobsScrapperCrunchbase(INPUT_CSV_PATH, keywords_list)
    scrapper.main()
