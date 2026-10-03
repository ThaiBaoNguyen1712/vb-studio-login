-- ==============================================================
-- VB-Login Database Schema (PostgreSQL on VPS)
-- Architecture: 10 Google Accounts -> 40 Social Channels
-- ==============================================================

-- 1. Bảng tài khoản Google gốc
CREATE TABLE IF NOT EXISTS accounts (
    id VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    recovery_email VARCHAR(255),
    notes TEXT,
    logo TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- Migration cho DB cũ: thêm cột logo nếu chưa có
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS logo TEXT;

-- 2. Bảng kênh mạng xã hội (40 kênh)
CREATE TABLE IF NOT EXISTS channels (
    id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL,
    channel_name VARCHAR(255) NOT NULL,
    studio_url TEXT NOT NULL,
    login_url TEXT NOT NULL,
    avatar_url TEXT,
    status VARCHAR(50) DEFAULT 'NOT_SETUP',
    pinned BOOLEAN DEFAULT FALSE,
    pinned_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- Migration cho DB cũ
ALTER TABLE channels ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE;
ALTER TABLE channels ADD COLUMN IF NOT EXISTS pinned_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE session_cookies ADD COLUMN IF NOT EXISTS health JSONB;
ALTER TABLE session_cookies ADD COLUMN IF NOT EXISTS last_heartbeat TIMESTAMPTZ;

-- Đợt 1: hàng đợi xin mở kênh (Presence + Request Access)
CREATE TABLE IF NOT EXISTS channel_access_requests (
    id VARCHAR(50) PRIMARY KEY,
    channel_id VARCHAR(50) NOT NULL,
    requester VARCHAR(100) NOT NULL,
    message TEXT DEFAULT '',
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    resolved_by VARCHAR(100),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_access_channel ON channel_access_requests(channel_id);
CREATE INDEX IF NOT EXISTS idx_access_status ON channel_access_requests(status);

-- Đợt kiểm tra phiên: lịch sử runs + kết quả từng kênh (report)
CREATE TABLE IF NOT EXISTS health_runs (
    id VARCHAR(50) PRIMARY KEY,
    triggered_by VARCHAR(100) DEFAULT '',
    scope VARCHAR(50) DEFAULT 'ALL',
    total INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,
    alive INT DEFAULT 0,
    dead INT DEFAULT 0,
    error INT DEFAULT 0,
    skipped INT DEFAULT 0,
    empty INT DEFAULT 0
);
CREATE TABLE IF NOT EXISTS health_results (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(50) REFERENCES health_runs(id) ON DELETE CASCADE,
    channel_id VARCHAR(50),
    status VARCHAR(20),
    detail TEXT DEFAULT '',
    checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_health_results_run ON health_results(run_id);

-- 3. Bảng lưu trữ Cookies & Khóa phiên (in_use_by)
CREATE TABLE IF NOT EXISTS session_cookies (
    channel_id VARCHAR(50) PRIMARY KEY REFERENCES channels(id) ON DELETE CASCADE,
    cookies_data JSONB,
    in_use_by VARCHAR(100) DEFAULT NULL,
    in_use_since TIMESTAMP WITH TIME ZONE,
    last_synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    updated_by VARCHAR(100)
);

-- 4. Bảng Audit Logs
CREATE TABLE IF NOT EXISTS session_logs (
    id SERIAL PRIMARY KEY,
    channel_id VARCHAR(50) NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,
    ip_address VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tạo Index
CREATE INDEX IF NOT EXISTS idx_channels_account_id ON channels(account_id);
CREATE INDEX IF NOT EXISTS idx_channels_platform ON channels(platform);
CREATE INDEX IF NOT EXISTS idx_session_in_use ON session_cookies(in_use_by);

-- ==============================================================
-- DỮ LIỆU KHỞI TẠO MẪU (10 TÀI KHOẢN GOOGLE & 40 KÊNH)
-- ==============================================================

-- 10 Tài khoản Google
INSERT INTO accounts (id, display_name, email, notes) VALUES
('acc_01', 'Google Acc #01', 'team.vb.account01@gmail.com', 'Kênh chủ đề Tech & AI'),
('acc_02', 'Google Acc #02', 'team.vb.account02@gmail.com', 'Kênh chủ đề Đời sống & Du lịch'),
('acc_03', 'Google Acc #03', 'team.vb.account03@gmail.com', 'Kênh chủ đề Ẩm thực & Mukbang'),
('acc_04', 'Google Acc #04', 'team.vb.account04@gmail.com', 'Kênh chủ đề Thể thao & Fitness'),
('acc_05', 'Google Acc #05', 'team.vb.account05@gmail.com', 'Kênh chủ đề Review Phim & Giải trí'),
('acc_06', 'Google Acc #06', 'team.vb.account06@gmail.com', 'Kênh chủ đề Gaming & Esports'),
('acc_07', 'Google Acc #07', 'team.vb.account07@gmail.com', 'Kênh chủ đề Tài chính & Đầu tư'),
('acc_08', 'Google Acc #08', 'team.vb.account08@gmail.com', 'Kênh chủ đề Tin tức & Sự kiện'),
('acc_09', 'Google Acc #09', 'team.vb.account09@gmail.com', 'Kênh chủ đề Giáo dục & Ngoại ngữ'),
('acc_10', 'Google Acc #10', 'team.vb.account10@gmail.com', 'Kênh chủ đề Âm nhạc & Podcast')
ON CONFLICT (id) DO NOTHING;

-- Tự động sinh 40 kênh tương ứng (mỗi Acc có YouTube, TikTok, Facebook, Instagram)
-- Channel IDs quy ước: ch_acc01_yt, ch_acc01_tt, ch_acc01_fb, ch_acc01_ig ...
DO $$
DECLARE
    i INT;
    acc_id VARCHAR(50);
    acc_num VARCHAR(10);
BEGIN
    FOR i IN 1..10 LOOP
        acc_num := LPAD(i::text, 2, '0');
        acc_id := 'acc_' || acc_num;

        -- YouTube Shorts
        INSERT INTO channels (id, account_id, platform, channel_name, studio_url, login_url, status)
        VALUES (
            'ch_' || acc_num || '_yt',
            acc_id,
            'YOUTUBE_SHORTS',
            'YT Shorts #' || acc_num,
            'https://studio.youtube.com',
            'https://accounts.google.com/ServiceLogin?service=youtube',
            'NOT_SETUP'
        ) ON CONFLICT (id) DO NOTHING;

        -- TikTok
        INSERT INTO channels (id, account_id, platform, channel_name, studio_url, login_url, status)
        VALUES (
            'ch_' || acc_num || '_tt',
            acc_id,
            'TIKTOK',
            'TikTok #' || acc_num,
            'https://www.tiktok.com/creator-center/upload',
            'https://www.tiktok.com/login',
            'NOT_SETUP'
        ) ON CONFLICT (id) DO NOTHING;

        -- Facebook Reels
        INSERT INTO channels (id, account_id, platform, channel_name, studio_url, login_url, status)
        VALUES (
            'ch_' || acc_num || '_fb',
            acc_id,
            'FACEBOOK_REELS',
            'FB Reels #' || acc_num,
            'https://business.facebook.com/latest/reels_composer',
            'https://www.facebook.com/login',
            'NOT_SETUP'
        ) ON CONFLICT (id) DO NOTHING;

        -- Instagram Reels
        INSERT INTO channels (id, account_id, platform, channel_name, studio_url, login_url, status)
        VALUES (
            'ch_' || acc_num || '_ig',
            acc_id,
            'INSTAGRAM_REELS',
            'Insta Reels #' || acc_num,
            'https://www.instagram.com',
            'https://www.instagram.com/accounts/login',
            'NOT_SETUP'
        ) ON CONFLICT (id) DO NOTHING;
    END LOOP;
END $$;
