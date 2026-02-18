"""
Database models for gesundheitsinformation.de crawler.

Defines relational structure for:
- Topic pages
- Sections
- Content blocks
- Glossary references
- Internal page links
"""

from sqlalchemy import Column, Integer, Text, TIMESTAMP, func, Date, ForeignKey, String, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Page(Base):
    """
    Represents a crawled topic page.
    """

    __tablename__ = "pages"

    id = Column(Integer, primary_key=True)
    title = Column(Text)
    themengebiet = Column(Text)
    url = Column(Text, unique=True, nullable=False)
    last_updated_at = Column(Date, nullable=True)
    crawled_at = Column(TIMESTAMP(timezone=True), nullable=True)

    is_placeholder = Column(Boolean, default=True)

    # Relationships
    sections = relationship(
        "Section", 
        back_populates="page", 
        cascade="all, delete-orphan"
        )
    

class Section(Base):
    """
    Represents a logical section within a topic page.
    """
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    title = Column(Text)
    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    page = relationship("Page", back_populates="sections")

    # Relationships
    content_blocks = relationship(
        "ContentBlock", 
        back_populates="section", 
        cascade="all, delete-orphan",
        order_by="ContentBlock.order_index"
        )



class ContentBlock(Base):
    """
    Represents structured content inside a section.

    block_type can be:
    - text
    - heading
    - list
    - table
    - image
    - link
    """
    __tablename__ = "content_blocks"

    id = Column(Integer, primary_key=True)
    section_id = Column(Integer, ForeignKey("sections.id"))

    block_type = Column(Text)

    # Generic content
    content = Column(Text, nullable=True)

    # Image-specific
    image_url = Column(Text, nullable=True) 
    alt = Column(Text, nullable=True)
    caption = Column(Text, nullable=True)

    # Link-specific
    href = Column(Text, nullable=True)

    order_index = Column(Integer)

    # Relationships
    section = relationship("Section", back_populates="content_blocks")


class PageLink(Base):
    """
    Represents an internal link between topic pages.

    Used to build page graph and analyze link structure.
    """

    __tablename__ = "page_links"

    id = Column(Integer, primary_key=True)

    from_page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    to_page_id = Column(Integer, ForeignKey("pages.id"), nullable=True)

    # Number of occurrences of this link in the page
    count = Column(Integer, default=1)

    from_page = relationship(
        "Page",
        foreign_keys=[from_page_id],
        backref="links_from_here"
    )
    to_page = relationship(
        "Page",
        foreign_keys=[to_page_id],
        backref="links_to_here"
    )

class GlossaryTerm(Base):
    """
    Represents glossary terms that were found.
    """
    __tablename__ = "glossary_terms"

    id = Column(Integer, primary_key=True)
    term = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    url = Column(Text, nullable=True)

class PageGlossaryLink(Base):
    """
    Represents glossary terms referenced in a topic page.
    """
     
    __tablename__ = "page_glossary_links"

    id = Column(Integer, primary_key=True)

    page_id = Column(Integer, ForeignKey("pages.id"), nullable=False)
    glossary_term_id = Column(Integer, ForeignKey("glossary_terms.id"), nullable=False)

    count = Column(Integer, default=1) # number of times referenced on this page

    # Relationships
    page = relationship("Page", backref="glossary_links")
    glossary_term = relationship("GlossaryTerm", backref="references")