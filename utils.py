from bs4 import Tag
from collections import Counter


def get_tag_pattern(element):
    if isinstance(element, Tag):
        return [element.name] + sum(
            [get_tag_pattern(child) for child in element.children], []
        )
    else:
        return []


def find_all_pattern_matches(soup, target_pattern):
    matching_elements = []
    for div in soup.find_all("div"):
        current_pattern = get_tag_pattern(div)
        if current_pattern == target_pattern:
            matching_elements.append(div)
    return matching_elements


def extract_content_from_tag(elements, tag_name):
    return [
        tag.get("href") for element in elements for tag in element.find_all(tag_name)
    ]


def find_div_structure(soup):
    div_structure_count = Counter()
    for div in soup.find_all("div"):
        if div.find("a"):
            div_structure = get_tag_pattern(div)
            div_structure_count[tuple(div_structure)] += 1

    if div_structure_count:
        most_repeated_div_structure = max(
            div_structure_count, key=div_structure_count.get
        )
        return most_repeated_div_structure
    else:
        return None
