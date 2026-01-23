import scrapy
import json
from gesundheitsinfo.utils.date_parsers import parse_german_date


class GesuninfoSpider(scrapy.Spider):
    name = "gesundheitsinfo"

    allowed_domains = ["gesundheitsinformation.de"]
    start_urls = ["https://www.gesundheitsinformation.de/themengebiete/"]

    def __init__(self, test_mode=None, url=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_mode = (str(test_mode).lower() == "true")
        self.test_url = url

        self.visited = set()

        if self.test_mode and self.test_url:
            self.start_urls = [self.test_url]
    

    def start_requests(self):
         for url in self.start_urls:
            self.visited.add(url)
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        # test mode
        if self.test_mode:
            #return self.parse_topic(response)
            yield from self.parse_topic(response)
            return
        
        # normal crewler
        for href in response.css("a::attr(href)").getall():
            if href and "/themen-von-a-bis-z" in href:
                yield response.follow(href, callback=self.parse_letter_page)

    def parse_letter_page(self, response):
        if self.test_mode:
            return
        
        links = response.css("ul.topicLinks li a::attr(href)").getall()

        for link in links:
            full_url = response.urljoin(link)
            yield response.follow(full_url, callback=self.parse_topic)
            # if full_url not in self.visited:
            #     self.visited.add(full_url)
            #     yield response.follow(full_url, callback=self.parse_topic)

        for href in response.css("a::attr(href)").getall():
            if "/themen-von-a-bis-z/" in href:
                yield response.follow(href, callback=self.parse_letter_page)

    def parse_topic(self, response):
        title = response.css("h1::text").get()

        crumbs = response.css(".breadcrumb-gi__item a span::text").getall()
        themengebiet = crumbs[-2].strip() if crumbs else None

        update_date = response.xpath(
            "//p[contains(text(),'Aktualisiert am')]/text()"
        ).get()

        last_updated_at = parse_german_date(update_date)


        # Extract topic -> topic links
        links_from_here = []

        for a in response.css("a[href]"):
            href = a.attrib.get("href")
            abs_url = response.urljoin(href)

            if not abs_url.startswith("https://www.gesundheitsinformation.de/"):
                continue

            if "/glossar/" in abs_url:
                continue

            if "/themengebiete/" in abs_url:
                continue

            if (abs_url.endswith(".html") and abs_url != response.url):
                links_from_here.append(abs_url)

                if abs_url not in self.visited:
                    self.visited.add(abs_url)
                    yield response.follow(abs_url, callback=self.parse_topic)

        glossary_refs = [] 

        # getting sections
        #section_nodes = response.css("h2.topicHeader")
        section_nodes = response.css("main article h2")
        sections = []

        # iterate through h2 headers and capture everything untill next h2
        for h2 in section_nodes:
            section_title = h2.xpath("text()").get()
            section_title = section_title.strip() if section_title else None


            article_node = h2.xpath("./ancestor::article")[0]
            content_blocks = []
            order = 0

            for node in article_node.xpath(".//p | .//h3 | .//ul | .//figure | .//div[contains(@class,'table__wrapper')] | .//div[contains(@class,'mediaItem__inner')]"):  # all descendents
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

                    # Extract normal text
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

                # h3 headings
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


        self.logger.warning(
            "RAW UPDATE TEXT: %r",
            response.css("div.topicFooter__text p::text").getall()
        )

        self.logger.warning(
            "PARSED DATE: %r (%s)",
            last_updated_at,
            type(last_updated_at),
        )
        yield{
            "title": title.strip() if title else None,
            "themengebiet": themengebiet,
            "url": response.url,
            "last_updated_at": last_updated_at,
            "sections": sections,
            "links_from_here": links_from_here,
            "glossary_refs": glossary_refs
        }




        #     # Text blocks
        #     for p in content_div.css("p"):
        #         text_nodes = p.xpath(".//text()[normalize-space()]").getall()
        #         full_text = " ".join(t.strip() for t in text_nodes)
        #         if full_text:
        #             content_blocks.append({
        #                 "block_type": "text",
        #                 "content": full_text,
        #                 "order_index": order
        #             })
        #             order += 1
            
        #     # Headers like h3
        #     for h in content_div.css("h3"):
        #         text = " ".join(h.xpath(".//text()[normalize-space()]").getall()).strip()

        #         if text:
        #             content_blocks.append({
        #                 "block_type": "heading h3",
        #                 "content": text,
        #                 "order_index": order
        #             })
        #             order += 1

        #     # List blocks
        #     for ul in content_div.css("ul"):
        #         items = []
        #         for li in ul.css("li"):
        #             li_text_parts = li.xpath(".//text()[normalize-space()]").getall()
        #             li_text = " ".join(t.strip() for t in li_text_parts if t.strip())
        #             if li_text:
        #                 items.append(li_text)
                
        #         if items:
        #             content_blocks.append({
        #                 "block_type": "list",
        #                 "content": json.dumps(items, ensure_ascii=False),
        #                 "order_index": order
        #             })
        #             order += 1
            
        #     # Table blocks
        #     for table_wrapper in content_div.css("div.table__wrapper"):
        #         table_data = []
        #         for tr in table_wrapper.css("table tr"):
        #             row = []
        #             for cell in tr.css("th, td"):
        #                 cell_text = " ".join(cell.xpath(".//text()[normalize-space()]").getall()).strip()
        #                 row.append(cell_text)
        #             if row:
        #                 table_data.append(row)
                
        #         if table_data:
        #             content_blocks.append({
        #                 "block_type": "table",
        #                 "content": json.dumps(table_data, ensure_ascii=False),
        #                 "order_index": order
        #             })
        #             order += 1
            
        #     # Image blocks
        #     for media in content_div.css("div.mediaItem__inner"):
        #         img = media.css("img")
        #         if img:
        #             src = img.attrib.get("src")
        #             alt = img.attrib.get("alt")

        #             #caption
        #             caption = media.css("div.mediaItem__subTitleWrapper p::text").get()
        #             if caption:
        #                 caption = caption.strip()

        #             content_blocks.append({
        #                 "block_type": "image",
        #                 "image_url": src,
        #                 "alt": alt,
        #                 "caption": caption,
        #                 "order_index": order
        #             })
        #             order += 1
        #     sections.append({
        #         "title": section_title,
        #         "content_blocks": content_blocks
        #     })



        # yield{
        #     "title": title.strip() if title else None,
        #     "themengebiet": themengebiet,
        #     "url": response.url,
        #     "sections": sections
        # }



    # def parse_topic(self, response):
    #     title = response.css("h1::text").get()

    #     crumbs = response.css(".breadcrumb-gi__item a span::text").getall()
    #     themengebiet = crumbs[-2].strip() if crumbs else None

    #     # getting sections
    #     #section_nodes = response.css("h2.topicHeader")
    #     section_nodes = response.css("main article h2")
    #     sections = []

    #     # iterate through h2 headers and capture everything untill next h2
    #     for h2 in section_nodes:
    #         section_title = h2.xpath("text()").get()
    #         section_title = section_title.strip()

    #         #find article after h2
    #         content_div = h2.xpath("following-sibling::div[contains(@class,'topicContent')][1]")
    #         if not content_div:
    #             content_div = h2.xpath("./ancestor::article[contains(@class,'topicIntro')]//div[contains(@class,'wysiwyg')]")
    
    #         content_blocks = []
    #         order = 0

    #         for node in content_div.xpath("./*"):
    #             classes = node.attrib.get("class", "")
    #             tag = node.root.tag.lower()

    #             if "wysiwyg" in classes:
    #                 for child in node.xpath("./*"):
    #                     ctag = child.root.tag.lower()


    #                     # Text blocks
    #                     if ctag == "p":
    #                         text = " ".join(child.xpath(".//text()[normalize-space()]").getall()).strip()
                            
    #                         if text:
    #                             content_blocks.append({
    #                                 "block_type": "text",
    #                                 "content": text,
    #                                 "order_index": order
    #                             })
    #                             order += 1
                        
    #                     # Heading bloks
    #                     elif ctag == "h3":
    #                         text = " ".join(child.xpath(".//text()[normalize-space()]").getall()).strip()

    #                         if text:
    #                             content_blocks.append({
    #                                 "block_type": "heading",
    #                                 "content": text,
    #                                 "order_index": order
    #                             })
    #                             order += 1

    #                     # List blocks
    #                     elif ctag == "ul":
    #                         items = []
    #                         for li in child.css("li"):
    #                             li_text_parts = li.xpath(".//text()[normalize-space()]").getall()
    #                             li_text = " ".join(t.strip() for t in li_text_parts if t.strip())
    #                             if li_text:
    #                                 items.append(li_text)
                            
    #                         if items:
    #                             content_blocks.append({
    #                                 "block_type": "list",
    #                                 "content": json.dumps(items, ensure_ascii=False),
    #                                 "order_index": order
    #                             })
    #                             order += 1

    #                     # Table blocks
    #                     elif ctag == "div" and "table__wrapper" in child.attrib.get("class", ""):
    #                         table_data = []
    #                         for tr in child.css("table tr"):
    #                             row = []
    #                             for cell in tr.css("th, td"):
    #                                 cell_text = " ".join(cell.xpath(".//text()[normalize-space()]").getall()).strip()
    #                                 row.append(cell_text)
    #                             if row:
    #                                 table_data.append(row)
                            
    #                         if table_data:
    #                             content_blocks.append({
    #                                 "block_type": "table",
    #                                 "content": json.dumps(table_data, ensure_ascii=False),
    #                                 "order_index": order
    #                             })
    #                             order += 1


    #             # Image blocks
    #             elif "mediaItem__inner" in classes:
    #                 img = node.css("img")
    #                 if img:
    #                     src = img.attrib.get("src")
    #                     alt = img.attrib.get("alt")

    #                     #caption
    #                     caption = node.css("div.mediaItem__subTitleWrapper p::text").get()
    #                     if caption:
    #                         caption = caption.strip()

    #                     content_blocks.append({
    #                         "block_type": "image",
    #                         "image_url": src,
    #                         "alt": alt,
    #                         "caption": caption,
    #                         "order_index": order
    #                     })
    #                     order += 1
            
    #         sections.append({
    #             "title": section_title,
    #             "content_blocks": content_blocks
    #         })



    #     yield{
    #         "title": title.strip() if title else None,
    #         "themengebiet": themengebiet,
    #         "url": response.url,
    #         "sections": sections
    #     }
