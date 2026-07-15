CREATE TABLE m_genres (
    id SMALLINT PRIMARY KEY,
    genre TEXT NOT NULL
);

INSERT INTO m_genres (id, genre) VALUES
    (1001, '老人ホーム専科'),
    (1002, '会社人生専科'),
    (1003, '町工場専科'),
    (1004, '病院・医療専科'),
    (1005, '法廷ドラマ'),
    (1006, '介護・在宅介護'),
    (1007, '相続・遺産ドラマ'),
    (1008, '昭和の商店街'),
    (1009, '刑事・警察'),
    (1010, '学校・教師'),
    (1011, 'AI企業ドラマ'),
    (1012, '昭和・平成回想録'),
    (1013, 'ミステリー小説'),
    (2001, '大人の学びなおしチャンネル 日本史編'),
    (2002, '大人の学びなおしチャンネル 世界史編'),
    (2003, '大人の学びなおしチャンネル 地理編'),
    (2004, '大人の学びなおしチャンネル 政治経済編'),
    (2005, '大人の学びなおしチャンネル 倫理社会編'),
    (2006, '大人の学びなおしチャンネル 生物編'),
    (2007, '大人の学びなおしチャンネル 化学編'),
    (2008, '大人の学びなおしチャンネル 物理編'),
    (2009, '大人の学びなおしチャンネル 地学編'),
    (2010, '大人の学びなおしチャンネル 保健体育編'),
    (2011, '大人の学びなおしチャンネル 美術史編'),
    (2012, '大人の学びなおしチャンネル 音楽史編'),
    (2013, '大人の学びなおしチャンネル 日本文学史編'),
    (2014, '大人の学びなおしチャンネル 東洋文学史編'),
    (2015, '大人の学びなおしチャンネル 西洋文学史編'),
    (3001, '大人の雑学チャンネル'),
    (3002, '未解決事件簿');

CREATE TABLE m_statuses (
    id SMALLINT PRIMARY KEY,
    status TEXT NOT NULL
);

INSERT INTO m_statuses (id, status) VALUES
    (0, '動画生成未着手'),
    (1, '動画生成着手済み'),
    (2, '動画生成失敗'),
    (3, '動画生成済み');

CREATE TABLE t_movie_titles (
    id BIGSERIAL PRIMARY KEY,
    genre_id SMALLINT,
    status_id SMALLINT DEFAULT 0,
    pipeline_no BIGINT DEFAULT 0,
    movie_title TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (genre_id) REFERENCES m_genres(id),
    FOREIGN KEY (status_id) REFERENCES m_statuses(id)
);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_t_movie_titles_updated_at
BEFORE UPDATE ON t_movie_titles
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();
