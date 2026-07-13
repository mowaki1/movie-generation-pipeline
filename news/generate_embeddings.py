import psycopg2
from sentence_transformers import SentenceTransformer

DB_DSN = "dbname=news_pipeline"

EMBEDDING_MODEL_ID = 1  # m_embedding_models: BAAI/bge-m3, 1024次元

BODY_CHARS_LIMIT = 4000

model = SentenceTransformer("BAAI/bge-m3")


def get_pending_articles(conn, limit):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, body FROM t_articles WHERE status_id = 6 ORDER BY id LIMIT %s",
            (limit,),
        )
        return cur.fetchall()


def embed_text(text):
    # コサイン類似度検索(t_embeddingsのHNSW索引がvector_cosine_ops)を使うため正規化する
    return model.encode(text, normalize_embeddings=True).tolist()


def save_embedding(conn, article_id, embedding):
    # pgvectorの'[v1,v2,...]'形式のリテラルとして渡す(pgvector用アダプタは未導入)
    vector_literal = "[" + ",".join(str(x) for x in embedding) + "]"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO t_embeddings (article_id, embedding_model_id, embedding)
            VALUES (%s, %s, %s::vector)
            ON CONFLICT (article_id, embedding_model_id)
            DO UPDATE SET embedding = EXCLUDED.embedding
            """,
            (article_id, EMBEDDING_MODEL_ID, vector_literal),
        )
        cur.execute(
            "UPDATE t_articles SET status_id = 7 WHERE id = %s",
            (article_id,),
        )
    conn.commit()


def main(limit=200):
    conn = psycopg2.connect(DB_DSN)
    articles = get_pending_articles(conn, limit)

    embedded = 0
    for article_id, title, body in articles:
        print(f"embedding: id={article_id} {title[:60]}")
        text = f"{title}\n\n{(body or '')[:BODY_CHARS_LIMIT]}"
        try:
            embedding = embed_text(text)
            save_embedding(conn, article_id, embedding)
        except Exception as e:
            print(f"  ERROR: {e}")
            continue

        print(f"  ok: {len(embedding)} dims")
        embedded += 1

    print(f"done: {embedded} / {len(articles)} articles embedded")
    conn.close()


if __name__ == "__main__":
    main()
