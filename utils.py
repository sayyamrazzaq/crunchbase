from bs4 import Tag


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
    content_list = []
    for element in elements:
        content_list.extend([tag.get("href") for tag in element.find_all(tag_name)])
    return content_list


def find_div_structure(soup):
    def get_structure(element):
        # Recursively build the structure identifier for a div
        structure = f"<{element.name}>"
        for child in element.children:
            if child.name:
                structure += get_structure(child)
        return structure

    divs = soup.find_all("div")
    # Initialize a dictionary to count occurrences of each unique div structure
    div_structure_count = {}
    for div in divs:
        div_structure = get_structure(div)
        if div_structure in div_structure_count:
            div_structure_count[div_structure] += 1
        else:
            div_structure_count[div_structure] = 1
    print("div structure count", div_structure_count)
    # Find the most repeated div structure
    most_repeated_div_structure = max(
        div_structure_count,
        key=div_structure_count.get,
    )
    return most_repeated_div_structure
