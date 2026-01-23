from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from .models import (
    Topic, Section, ContentBlock, TopicLink, GlossaryTerm,TopicGlossaryLink
)

def get_session(database_url: str):
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()

def get_full_topic(session, topic_url: str):
    topic = (
        session.query(Topic)
        .filter(Topic.url == topic_url)
        .first()
    )

    if not topic:
        return None

    return {
        "title": topic.title,
        "themengebiet": topic.themengebiet,
        "last_updated_at": topic.last_updated_at,
        "sections": [
            {
                "title": section.title,
                "content_blocks": (
                    session.query(ContentBlock)
                    .filter(ContentBlock.section_id == section.id)
                    .order_by(ContentBlock.order_index)
                    .all()
                )
            }
            for section in (
                session.query(Section)
                .filter(Section.topic_id == topic.id)
                .order_by(Section.id)
                .all()
            )
        ]
    }

def get_most_used_glossary_terms(session, limit: int = 10):
    return (
        session.query(
            GlossaryTerm.term,
            func.count(TopicGlossaryLink.topic_id.distinct()).label("topic_count"),
            func.sum(TopicGlossaryLink.count).label("total_mentions"),
        )
        .join(
            TopicGlossaryLink,
            TopicGlossaryLink.glossary_term_id == GlossaryTerm.id,
        )
        .group_by(GlossaryTerm.term)
        .order_by(func.sum(TopicGlossaryLink.count).desc())
        .limit(limit)
        .all()
    )
