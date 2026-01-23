from sqlalchemy import Column, Integer, Text, TIMESTAMP, func, Date, ForeignKey, String, Boolean
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True)
    title = Column(Text)
    themengebiet = Column(Text)
    url = Column(Text, unique=True, nullable=False)
    last_updated_at = Column(Date, nullable=True)
    #crawled_at = Column(TIMESTAMP(timezone=True), nullable=True)

    is_placeholder = Column(Boolean, default=True)

    sections = relationship(
        "Section", 
        back_populates="topic", 
        cascade="all, delete-orphan"
        )
    

class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True)
    title = Column(Text)
    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    topic = relationship("Topic", back_populates="sections")
    content_blocks = relationship(
        "ContentBlock", 
        back_populates="section", 
        cascade="all, delete-orphan",
        order_by="ContentBlock.order_index"
        )



class ContentBlock(Base):
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

    section = relationship("Section", back_populates="content_blocks")


class TopicLink(Base):

    __tablename__ = "topic_links"

    id = Column(Integer, primary_key=True)

    from_topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    to_topic_id = Column(Integer, ForeignKey("topics.id"), nullable=True)

    href = Column(Text, nullable=False)  # url of the page
    count = Column(Integer, default=1)

    from_topic = relationship(
        "Topic",
        foreign_keys=[from_topic_id],
        backref="links_from_here"
    )
    to_topic = relationship(
        "Topic",
        foreign_keys=[to_topic_id],
        backref="links_to_here"
    )

class GlossaryTerm(Base):
    __tablename__ = "glossary_terms"

    id = Column(Integer, primary_key=True)
    term = Column(Text, nullable=False, unique=True)
    description = Column(Text, nullable=True)
    url = Column(Text, nullable=True)

class TopicGlossaryLink(Base):
    __tablename__ = "topic_glossary_links"

    id = Column(Integer, primary_key=True)

    topic_id = Column(Integer, ForeignKey("topics.id"), nullable=False)
    glossary_term_id = Column(Integer, ForeignKey("glossary_terms.id"), nullable=False)

    count = Column(Integer, default=1) # number of times referenced on this topic

    topic = relationship("Topic", backref="glossary_links")
    glossary_term = relationship("GlossaryTerm", backref="references")