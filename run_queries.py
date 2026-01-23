from gesundheitsinfo.queries import (
    get_session,
    get_full_topic,
    get_most_used_glossary_terms,
)

DATABASE_URL = "postgresql://postgres:2240@localhost:5433/gesundheitsinformation"

session = get_session(DATABASE_URL)

topic = get_full_topic(
    session,
    "https://www.gesundheitsinformation.de/mandelentzuendung.html"
)

print(topic["title"])
print("Sections:", len(topic["sections"]))

terms = get_most_used_glossary_terms(session, limit=5)
for term, topic_count, total in terms:
    print(term, topic_count, total)
