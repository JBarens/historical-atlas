from ingest import embed
from models import Document
from sqlalchemy.orm import Session
from database import engine


def retrieve(question: str, k: int = 3) -> list[str]:
    vector = embed([question])[0]
    with Session(engine) as session:
        # Retrieve the top k documents based on vector similarity
        results = (
            session.query(Document)
            .order_by(Document.embedding.op("<->")(vector))
            .limit(k)
            .all()
        )
    return [result.text for result in results]

if __name__ == "__main__":
    print(retrieve("assissination of Franz Ferdinand"))
