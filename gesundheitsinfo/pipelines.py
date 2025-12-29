# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from .models import Base, Topic, Section, ContentBlock, TopicLink

class SQLAlchemyPipeline:
    def open_spider(self, spider):
        DATABASE_URL = "postgresql://postgres:2240@localhost:5433/gesundheitsinformation"

        self.engine = create_engine(DATABASE_URL)

        #creating tables
        Base.metadata.create_all(self.engine)

        # create session
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def close_spider(self, spider):
        self.session.close()

    def process_item(self, item, spider):

        # Create Topic
        topic = self.session.query(Topic).filter_by(url=item.get("url")).first()
        if topic:
            # if theam exists, update fields (title, themengebiet) if needed
            topic.title = item.get("title") or topic.title
            topic.themengebiet = item.get("themengebiet") or topic.themengebiet
            topic.last_updated_at = item.get("last_updated_at")
        else:
            # insert new Topic
            topic = Topic(
                title=item.get("title"),
                themengebiet=item.get("themengebiet"),
                url=item.get("url"),
                last_updated_at=item.get("last_updated_at")
            )
        
            self.session.add(topic)
            self.session.flush()

        # Create Sections (per theme)
        for s in item.get("sections", []):
            section_title = s.get("title")
            if not section_title:
                continue
            
            section = Section(
                title=section_title,
                theme=topic
            )
            self.session.add(section)
            self.session.flush()

            for b in s.get("content_blocks", []):
                block = ContentBlock(
                    section=section,
                    block_type=b.get("block_type"),
                    content=b.get("content"),
                    image_url=b.get("image_url"),
                    alt=b.get("alt"),
                    caption=b.get("caption"),
                    href=b.get("href"),
                    order_index=b.get("order_index"),
                )
                self.session.add(block)
        
        # Topic links
        for link in item.get("links_from_here", []):
            href = link["href"]

            to_topic = self.session.query(Topic).filter_by(url=href).first()

            if not to_topic:
                to_topic = Topic(url=href) # placeholder
                self.session.add(to_topic)
                self.session.flush()

            existing_link = self.session.query(TopicLink).filter_by(
                from_topic_id=topic.id,
                to_topic_id=to_topic.id
            ).first()

            if not existing_link:
                topic_link = TopicLink(
                    from_topic=topic,
                    to_topic=to_topic, 
                    href=href
                )
                self.session.add(topic_link)

        #adding to session
        self.session.add(topic)

        try:
            self.session.commit()
        except:
            self.session.rollback()
            raise
        return item