# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from .models import Base, Topic, Section, ContentBlock, TopicLink, GlossaryTerm, TopicGlossaryLink

class SQLAlchemyPipeline:
    def open_spider(self, spider):
        DATABASE_URL = spider.settings.get("DATABASE_URL")

        self.engine = create_engine(DATABASE_URL)

        #creating tables
        Base.metadata.create_all(self.engine)

        # create session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def close_spider(self, spider):
        self.session.close()

    def process_item(self, item, spider):

        url = item.get("url")
        # Create Topic
        topic = self.session.query(Topic).filter_by(url=url).first()
        if not topic:
            topic = Topic(url=url)
            self.session.add(topic)
            self.session.flush()

        topic.is_placeholder = False

        topic.title = item.get("title") or topic.title
        topic.themengebiet = item.get("themengebiet") or topic.themengebiet
        topic.last_updated_at = item.get("last_updated_at")
        #topic.crawled_at = datetime.utcnow()

        # Create Sections (per theme)
        for s in item.get("sections", []):
            section_title = s.get("title")
            if not section_title:
                continue
            
            section = self.session.query(Section).filter_by(
                topic_id=topic.id,
                title=section_title
            ).first()

            if not section:
                section = Section(title=section_title, topic=topic)
                self.session.add(section)
                self.session.flush()

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
        
        # Topic links
        for link_url in item.get("links_from_here", []):
            to_topic = self.session.query(Topic).filter_by(url=link_url).first()

            if not to_topic:
                to_topic = Topic(
                    url=link_url,
                    is_placeholder=True
                )
                self.session.add(to_topic)
                self.session.flush()
            
            topic.is_placeholder = False

            existing_link = self.session.query(TopicLink).filter_by(
                from_topic_id=topic.id,
                to_topic_id=to_topic.id
            ).first()
            if existing_link:
                existing_link.count += 1
            else:
                self.session.add(
                    TopicLink(
                        from_topic=topic,
                        to_topic=to_topic,
                        href=link_url,
                        count = 1
                    )
                )
        
        # create glossary terms and links
        for g in item.get("glossary_refs", []):
            term_obj = self.session.query(GlossaryTerm).filter_by(term=g["term"]).first()
            if not term_obj:
                term_obj = GlossaryTerm(
                    term=g["term"], 
                    description=g.get("description"), 
                    url=g.get("href")
                    )
                self.session.add(term_obj)
                self.session.flush()

            # link to topic
            link_obj = self.session.query(TopicGlossaryLink).filter_by(
                topic_id=topic.id,
                glossary_term_id=term_obj.id
            ).first()

            if link_obj:
                link_obj.count += 1
            else:
                self.session.add(
                    TopicGlossaryLink(
                        topic=topic,
                        glossary_term=term_obj,
                        count=1
                    )
                )


        #adding to session
        #self.session.add(topic)

        try:
            self.session.commit()
        except:
            self.session.rollback()
            raise

        return item