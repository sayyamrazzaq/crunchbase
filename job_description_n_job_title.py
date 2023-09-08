def find_largest_text_block(soup, tags):
    largest_block = ""
    largest_block_text = ""

    for tag in tags:
        elements = soup.find_all(tag)
        for element in elements:
            text = element.text.strip()
            if len(text.split()) > len(largest_block_text.split()):
                largest_block = element
                largest_block_text = text

    return largest_block


def heuristic_scrape(soup):
    # Heuristic 1: The job title is likely to be in an <h1>, <h2>, or <h3> tag
    for tag in ["h1", "h2", "h3"]:
        job_title = soup.find(tag)
        if job_title:
            job_title = job_title.text.strip()
            break

    # Heuristic 2: The largest text block within <div>,
    # <p>, or <span> is likely to be the job description
    largest_text_block = find_largest_text_block(soup, ["div", "p", "span"])

    if largest_text_block:
        job_description = largest_text_block.text.strip()
        return {"Job Title": job_title, "Job Description": job_description}