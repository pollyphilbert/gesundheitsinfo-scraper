""" 
Spider for crawling health information from gesundheitsinformation.de 
This spider extracts structured health information including: 
- Topic pages with sections and content blocks 
- Internal page links and their relationships 
- Glossary term references 
- Images, tables, lists, and other structured content 
"""

import scrapy
import json
from collections import Counter
from gesundheitsinfo.utils.date_parsers import parse_german_date


class GesuninfoSpider(scrapy.Spider):
    """ 
    Spider for crawling German health information website. 
    Supports two modes: 
    1. Normal mode: Crawls all topics from A-Z 
    2. Test mode: Crawls a single URL for testing purposes 
    """

    name = "gesundheitsinfo"

    allowed_domains = ["gesundheitsinformation.de"]
    start_urls = ["https://www.gesundheitsinformation.de/themengebiete/"]

    def __init__(self, test_mode=None, url=None, *args, **kwargs):
        """ 
        Initialize the spider with optional test mode. 
        
        Args: 
            test_mode: If "true", spider will only crawl the specified URL 
            url: URL to crawl in test mode 
        """

        super().__init__(*args, **kwargs)
        self.test_mode = (str(test_mode).lower() == "true")
        self.test_url = url

        self.visited = set() # Track visited URLs to avoid duplicates

        if self.test_mode and self.test_url:
            self.start_urls = [self.test_url]
    

    def start_requests(self):
         """Generate initial requests for crawling."""
         for url in self.start_urls:
            self.visited.add(url)
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        """
        Parse the main topics page. 
        In test mode: directly parse as a topic page 
        In normal mode: find and follow alphabet letter pages
        """
        if self.test_mode:
            yield from self.parse_topic(response)
            return
        
        # Normal mode: Find all A-Z topic links
        for href in response.css("a::attr(href)").getall():
            if href and "/themen-von-a-bis-z" in href:
                yield response.follow(href, callback=self.parse_letter_page)

    def parse_letter_page(self, response):
        """ 
        Parse an alphabet letter page.
        Extracts all topic links and follows them. 
        Also follows pagination/other letter pages.
        """
        if self.test_mode:
            return
        
        # Extract individual topic links from the letter page
        links = response.css("ul.topicLinks li a::attr(href)").getall()

        for link in links:
            full_url = response.urljoin(link)
            yield response.follow(full_url, callback=self.parse_topic)

        # Follow links to other pages
        for href in response.css("a::attr(href)").getall():
            if "/themen-von-a-bis-z/" in href:
                yield response.follow(href, callback=self.parse_letter_page)

    def parse_topic(self, response):
        """ 
        Parse a health topic page and extract all structured content. 
        Extracts: 
        - Page metadata (title, category, update date) 
        - Content sections with various block types 
        - Glossary term references 
        - Internal page links 
        """

        # Extract basic page metadata
        title = response.css("h1::text").get()

        crumbs = response.css(".breadcrumb-gi__item a span::text").getall()
        themengebiet = crumbs[-2].strip() if crumbs else None

        update_date = response.xpath(
            "//p[contains(text(),'Aktualisiert am')]/text()"
        ).get()

        last_updated_at = parse_german_date(update_date)

        # Initialize tracking structures
        link_counter = Counter()
        seen_links_in_section = set() #Avoid duplicate links in sections

        

        for a in response.css("a[href]"):
            href = a.attrib.get("href")
            abs_url = response.urljoin(href)

            # Only crawl internal topic pages
            if not abs_url.startswith("https://www.gesundheitsinformation.de/"):
                continue
            
            # Skip glossary pages
            if "/glossar/" in abs_url:
                continue
            
            # Skip topic overview pages
            if "/themengebiete/" in abs_url:
                continue

            # Only follow .html topic pages
            if (abs_url.endswith(".html") and abs_url != response.url):
                

                if abs_url not in self.visited:
                    self.visited.add(abs_url)
                    yield response.follow(abs_url, callback=self.parse_topic)

        # Glossary references storage
        glossary_refs = [] 

        # All main section headers (h2)
        section_nodes = response.css("main article h2")
        sections = []

        # iterate through h2 headers and capture everything untill next h2
        for h2 in section_nodes:
            section_title = h2.xpath("text()").get()
            section_title = section_title.strip() if section_title else None

            # Get full article node for this section
            article_node = h2.xpath("./ancestor::article")[0]
            content_blocks = []
            order = 0

             # Extract all relevant content types inside article
            for node in article_node.xpath(
                ".//p | .//h3 | .//ul | .//figure | "
                " .//div[contains(@class,'table__wrapper')] | "
                ".//div[contains(@class,'mediaItem__inner')]"
                ):
                tag = node.root.tag.lower()
                classes = node.attrib.get("class", "")

                # Text paragraphs
                if tag == "p":

                    # Extract glossary terms
                    for span in node.xpath(".//span[contains(@class,'glossaryLink')]"):
                            term = span.attrib.get("data-title")
                            desc = span.attrib.get("data-desc")

                            href = (
                                span.attrib.get("data-link")
                                or span.xpath(".//a/@href").get()
                            )

                            if href:
                                href = response.urljoin(href)

                            if term:
                                glossary_refs.append({
                                    "term": term,
                                    "description": desc,
                                    "href": href
                                })

                    # Extract visible paragraph text
                    text = " ".join(
                        node.xpath(
                            ".//text()[normalize-space() and not(ancestor::span[contains(@class,'glossaryLink')])]"
                            ).getall()).strip()
                    if text:
                        content_blocks.append({
                            "block_type": "text",
                            "content": text,
                            "order_index": order
                        })
                        order += 1

                    # Extract internal  links inside paragraph
                    for a in node.xpath(".//a[@href]"):
                        href = a.attrib.get("href")
                        abs_url = response.urljoin(href)

                        if not abs_url.startswith("https://www.gesundheitsinformation.de/"):
                            continue

                        link_counter[abs_url] += 1

                        if abs_url in seen_links_in_section:
                            continue

                        seen_links_in_section.add(abs_url)

                        link_text = " ".join(
                            a.xpath(".//text()[normalize-space()]").getall()
                        ).strip()
                        
                        content_blocks.append({
                            "block_type": "link",
                            "href": abs_url,
                            "content": link_text,
                            "order_index": order,
                        })
                        order += 1

                # Sub-headings (h3)
                elif tag == "h3":
                    text = " ".join(node.xpath(".//text()[normalize-space()]").getall()).strip()
                    if text:
                        content_blocks.append({
                            "block_type": "heading",
                            "content": text,
                            "order_index": order
                        })
                        order += 1

                # Lists
                elif tag == "ul":
                    items = [" ".join(li.xpath(".//text()[normalize-space()]").getall()).strip()
                            for li in node.css("li")]
                    if items:
                        content_blocks.append({
                            "block_type": "list",
                            "content": json.dumps(items, ensure_ascii=False),
                            "order_index": order
                        })
                        order += 1

                # Tables
                elif tag == "div" and "table__wrapper" in classes:
                    table_data = []
                    for tr in node.css("table tr"):
                        row = [" ".join(cell.xpath(".//text()[normalize-space()]").getall()).strip()
                            for cell in tr.css("th, td")]
                        if row:
                            table_data.append(row)
                    if table_data:
                        content_blocks.append({
                            "block_type": "table",
                            "content": json.dumps(table_data, ensure_ascii=False),
                            "order_index": order
                        })
                        order += 1

                # Images
                elif tag == "div" and "mediaItem__inner" in classes:
                    img = node.css("img")
                    if img:
                        src = img.attrib.get("src")
                        alt = img.attrib.get("alt")
                        caption = node.css("div.mediaItem__subTitleWrapper p::text").get()
                        if caption:
                            caption = caption.strip()
                        content_blocks.append({
                            "block_type": "image",
                            "image_url": src,
                            "alt": alt,
                            "caption": caption,
                            "order_index": order
                        })
                        order += 1

                # Images inside Einleitung
                elif tag == "figure" and "topicIntro__image" in classes:
                    img = node.css("img")
                    if img:
                        src = response.urljoin(img.attrib.get("src"))
                        alt = img.attrib.get("alt")
                        caption = node.css("div.mediaItem_subTitleWrapper p.mediaItem_subTitle::text").get()
                        if caption:
                            caption = caption.strip()
                        content_blocks.append({
                            "block_type": "image",
                            "image_url": src,
                            "alt": alt,
                            "caption": caption,
                            "order_index": order
                        })
                        order += 1

            sections.append({
                "title": section_title,
                "content_blocks": content_blocks
            })

        # Debug logging
        self.logger.warning(
            "RAW UPDATE TEXT: %r",
            response.css("div.topicFooter__text p::text").getall()
        )

        self.logger.warning(
            "PARSED DATE: %r (%s)",
            last_updated_at,
            type(last_updated_at),
        )

        # Final structured output
        yield{
            "title": title.strip() if title else None,
            "themengebiet": themengebiet,
            "url": response.url,
            "last_updated_at": last_updated_at,
            "sections": sections,
            "glossary_refs": glossary_refs,
            "raw_link_counts": dict(link_counter),
        }


