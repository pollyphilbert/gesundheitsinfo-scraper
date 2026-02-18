"""
SQLAlchemy pipeline for persisting scraped data into relational database.

Responsibilities:
- Create or update Page records
- Persist hierarchical structure (Sections → ContentBlocks)
- Build internal page link graph
- Create glossary terms and page-term relations
- Maintain placeholder pages for not-yet-crawled URLs
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from .models import Base, Page, Section, ContentBlock, PageLink, GlossaryTerm, PageGlossaryLink

class SQLAlchemyPipeline:
    """
    Scrapy pipeline that stores spider output in a SQL database.

    Implements:
    - Idempotent upsert logic
    - Graph construction between pages
    - Many-to-many glossary relationships
    """

    def open_spider(self, spider):
        """
        Initialize database connection and session when spider starts.
        """

        DATABASE_URL = spider.settings.get("DATABASE_URL")

        self.engine = create_engine(DATABASE_URL)

        # Create all tables if they don't exist
        Base.metadata.create_all(self.engine)

        # Create session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def close_spider(self, spider):
        """
        Close DB session when spider finishes.
        """
        self.session.close()

    def process_item(self, item, spider):
        """
        Process and persist a single scraped topic page.

        Performs:
        - Page upsert
        - Section & content block persistence
        - Internal link graph updates
        - Glossary term linking
        """

        url = item.get("url")

        
        page = self.session.query(Page).filter_by(url=url).first()
        if not page:
            # Page does not exist → create it
            page = Page(url=url)
            self.session.add(page)
            self.session.flush()

        # Mark as fully crawled (not placeholder anymore)
        page.is_placeholder = False

        # Update page metadata
        page.title = item.get("title") or page.title
        page.themengebiet = item.get("themengebiet") or page.themengebiet
        page.last_updated_at = item.get("last_updated_at")
        page.crawled_at = datetime.utcnow()

        # Create Sections (per page)
        for s in item.get("sections", []):
            section_title = s.get("title")
            if not section_title:
                continue
            
            section = self.session.query(Section).filter_by(
                page_id=page.id,
                title=section_title
            ).first()

            if not section:
                section = Section(title=section_title, page=page)
                self.session.add(section)
                self.session.flush()

            # Insert content blocks
            for b in s.get("content_blocks", []):
                block = self.session.query(ContentBlock).filter_by(
                    section_id=section.id,
                    order_index=b.get("order_index")
                ).first()

                if not block:
                    block = ContentBlock(
                        section=section,
                        block_type=b.get("block_type"),
                        content=b.get("content"),
                        image_url=b.get("image_url"),
                        alt=b.get("alt"),
                        caption=b.get("caption"),
                        href=b.get("href"),
                        order_index=b.get("order_index")
                    )
                    self.session.add(block)
        self.session.flush()


        # Build internal link graph
        raw_link_counts = item.get("raw_link_counts", {})
        
        for link_url, count in raw_link_counts.items():

            # Skip glossary links (handled separately)
            if "/glossar/" in link_url:
                continue
            
            # Ensure target page exists (create placeholder if needed)
            to_page = self.session.query(Page).filter_by(url=link_url).first()

            if not to_page:
                to_page = Page(
                    url=link_url,
                    is_placeholder=True # Will be completed when crawled
                )
                self.session.add(to_page)
                self.session.flush()

            link = self.session.query(PageLink).filter_by(
                from_page_id=page.id,
                to_page_id=to_page.id
            ).first()

            if link:
                link.count += count
            else:
                self.session.add(
                    PageLink(
                        from_page=page,
                        to_page=to_page,
                        count=count
                    )
                )
        

        # create glossary terms and links
        for g in item.get("glossary_refs", []):

            # Create glossary term if not exists
            term_obj = self.session.query(GlossaryTerm).filter_by(term=g["term"]).first()
            
            if not term_obj:
                term_obj = GlossaryTerm(
                    term=g["term"], 
                    description=g.get("description"), 
                    url=g.get("href")
                    )
                self.session.add(term_obj)
                self.session.flush()

            # Link glossary term to page (many-to-many)
            link_obj = self.session.query(PageGlossaryLink).filter_by(
                page_id=page.id,
                glossary_term_id=term_obj.id
            ).first()

            if link_obj:
                link_obj.count += 1
            else:
                self.session.add(
                    PageGlossaryLink(
                        page=page,
                        glossary_term=term_obj,
                        count=1
                    )
                )

        # Commit transaction
        try:
            self.session.commit()
        except:
            self.session.rollback()
            raise

        return item