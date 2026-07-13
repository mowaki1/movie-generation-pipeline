CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE m_embedding_models(
    id SMALLINT PRIMARY KEY,
    model TEXT NOT NULL,
    dimension SMALLINT NOT NULL
);
INSERT INTO m_embedding_models (id, model, dimension) VALUES 
	(1, 'BAAI/bge-m3', 1024);

CREATE TABLE m_sources (
    id SMALLINT PRIMARY KEY,
    source TEXT NOT NULL,
    rss_url TEXT NOT NULL
);
INSERT INTO m_sources (id, source, rss_url) VALUES 
	(0, 'ソースなし', ''),
	(1, 'OpenAI', 'https://openai.com/news/rss.xml'),
	(2, 'Google AI', 'https://blog.google/innovation-and-ai/technology/ai/rss/'),
	(3, 'Hugging Face', 'https://huggingface.co/blog/feed.xml'),
	(4, 'NVIDIA AI', 'https://news.google.com/rss/search?q=site:www.nvidia.com/en-us/solutions/ai/&hl=en-US&gl=US&ceid=US:en'),
	(5, 'ITmedia', 'https://rss.itmedia.co.jp/rss/2.0/topstory.xml'),
	(6, 'PC Watch', 'https://pc.watch.impress.co.jp/data/rss/1.0/pcw/feed.rdf'),
	(7, 'Impress Watch', 'https://www.watch.impress.co.jp/data/rss/1.0/ipw/feed.rdf'),
	(8, 'ZDNET', 'https://news.google.com/rss/search?q=site:www.zdnet.com&hl=en-US&gl=US&ceid=US:en'),
	(9, 'TechCrunch', 'https://techcrunch.com/feed/'),
	(10, 'NVIDIA', 'https://blogs.nvidia.com/feed/'),
	(11, 'Tom's Hardware', 'https://www.tomshardware.com/feeds.xml'),
	(12, 'VideoCardz', 'https://news.google.com/rss/search?q=site:videocardz.com&hl=en-US&gl=US&ceid=US:en'),
	(13, 'ServeTheHome', 'https://www.servethehome.com/feed/'),
	(14, 'Investing.com', 'https://news.google.com/rss/search?q=site:investing.com&hl=en-US&gl=US&ceid=US:en'),
	(15, 'Yahoo!ファイナンス', 'https://news.google.com/rss/search?q=site:finance.yahoo.com&hl=en-US&gl=US&ceid=US:en'),
	(16, 'BBC World', 'https://news.google.com/rss/search?q=site:www.bbc.com/news/world&hl=en-US&gl=US&ceid=US:en'),
	(17, 'AP', 'https://news.google.com/rss/search?q=site:apnews.com&hl=en-US&gl=US&ceid=US:en'),
	(18, 'Al Jazeera', 'https://www.aljazeera.com/xml/rss/all.xml'),
	(19, 'Nature', 'https://www.nature.com/nature.rss'),
	(20, 'ScienceDaily', 'https://www.sciencedaily.com/rss/all.xml'),
	(21, 'NASA', 'https://www.nasa.gov/feed/'),
	(22, 'ESA', 'https://news.google.com/rss/search?q=site:www.esa.int&hl=en-US&gl=US&ceid=US:en'),
	(23, 'WHO', 'https://news.google.com/rss/search?q=site:www.who.int&hl=en-US&gl=US&ceid=US:en'),
	(24, 'MedicalXpress1', 'https://medicalxpress.com/rss-feed/'),
	(25, 'MedicalXpress2', 'https://medicalxpress.com/rss-feed/breaking/'),
	(26, 'Ubuntu', 'https://news.google.com/rss/search?q=site:ubuntu.com&hl=en-US&gl=US&ceid=US:en'),
	(27, 'Red Hat', 'https://news.google.com/rss/search?q=site:www.redhat.com&hl=en-US&gl=US&ceid=US:en'),
	(28, 'Phoronix', 'https://news.google.com/rss/search?q=site:www.phoronix.com&hl=en-US&gl=US&ceid=US:en'),
	(29, 'The Hacker News', 'https://news.google.com/rss/search?q=site:thehackernews.com&hl=en-US&gl=US&ceid=US:en'),
	(30, 'BleepingComputer', 'https://news.google.com/rss/search?q=site:www.bleepingcomputer.com&hl=en-US&gl=US&ceid=US:en'),
	(31, 'CISA', 'https://news.google.com/rss/search?q=site:www.cisa.gov&hl=en-US&gl=US&ceid=US:en');


CREATE TABLE m_genres (
    id SMALLINT PRIMARY KEY,
    genre TEXT NOT NULL
);
INSERT INTO m_genres (id, genre) VALUES 
	(0, '未分類'),
	(1, 'AIニュース'),
	(2, 'ITニュース'),
	(3, 'GPUニュース'),
	(4, '金融ニュース'),
	(5, '地政学ニュース'),
	(6, '科学ニュース'),
	(7, '医療ニュース'),
	(8, 'Linuxニュース'),
	(9, 'セキュリティニュース'),
	(9999, 'その他のニュース');

CREATE TABLE m_statuses (
    id SMALLINT PRIMARY KEY,
    status TEXT NOT NULL
);

INSERT INTO m_statuses (id, status) VALUES 
	(1, 'RSS取得直後'),
	(2, '本文取得成功'),
	(3, '本文が取得できなかった'),
	(4, '401/403などアクセス拒否'),
	(5, '通信エラー・タイムアウト'),
	(6, 'ジャンル振り分け済み'),
	(7, 'Embedding生成済み'),
	(8, '要約生成済み'),
	(9, '動画生成まで完了');


CREATE TABLE t_articles (
    id BIGSERIAL PRIMARY KEY,
    language CHAR(2),
    source_id SMALLINT DEFAULT 0,
    rss_guid TEXT,
    category TEXT,
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    published_at TIMESTAMPTZ,
    rss_summary TEXT,
    body TEXT,
    summary TEXT,
    genre_id SMALLINT DEFAULT 0,
    status_id SMALLINT DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES m_sources(id),
    FOREIGN KEY (genre_id) REFERENCES m_genres(id),
    FOREIGN KEY (status_id) REFERENCES m_statuses(id),
    UNIQUE (source_id, rss_guid)
);

CREATE TABLE t_embeddings (
    id BIGSERIAL PRIMARY KEY,
    article_id BIGINT NOT NULL,
    embedding_model_id  SMALLINT NOT NULL,
    embedding vector(1024),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (article_id) REFERENCES t_articles(id) ON DELETE CASCADE,
    FOREIGN KEY (embedding_model_id) REFERENCES m_embedding_models(id),
    UNIQUE (article_id, embedding_model_id)
);

CREATE INDEX idx_embeddings_hnsw
ON t_embeddings
USING hnsw (embedding vector_cosine_ops);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_t_articles_updated_at
BEFORE UPDATE ON t_articles
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

