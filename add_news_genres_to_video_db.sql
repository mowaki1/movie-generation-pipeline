INSERT INTO m_genres (id, genre) VALUES
    (10001, 'AIニュース'),
    (10002, 'ITニュース'),
    (10003, 'GPUニュース'),
    (10004, '金融ニュース'),
    (10005, '地政学ニュース'),
    (10006, '科学ニュース'),
    (10007, '医療ニュース'),
    (10008, 'Linuxニュース'),
    (10009, 'セキュリティニュース'),
    (10010, 'Science and Technology News'),
    (10011, 'Geopolitical News')
ON CONFLICT (id) DO NOTHING;
