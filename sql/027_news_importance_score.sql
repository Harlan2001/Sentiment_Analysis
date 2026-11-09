-- 新闻重要性打分（S3-2 推荐排序）
--
-- 背景：全平台新闻列表此前只有 pub_time DESC 一种排序，缺少面向固收
-- 交易员的重要性视角。打分拆成两层：
--   1. 静态重要性分 importance_score（0-100）：由 9 个可解释信号加权合成，
--      新闻分析完成后预计算写入本表（信号子分同时落 signals_json，供后续
--      「为什么推荐」与 learning-to-rank 特征台账使用）；
--   2. 时间衰减：唯一随时间持续变化的项，不入库，查询时在 SQL 内
--      EXP(-RECOMMEND_DECAY_LAMBDA * age_days) 实时施加。
-- score_version 支持未来新公式并行灰度（v2 行为信号 / LLM 复核分）。

CREATE TABLE IF NOT EXISTS `news_importance_score` (
  `news_id` bigint(20) unsigned NOT NULL COMMENT '新闻 ID（FK news.id）',
  `score_version` varchar(20) NOT NULL DEFAULT 'v1' COMMENT '打分公式版本',
  `importance_score` decimal(8,4) NOT NULL DEFAULT 0.0000 COMMENT '静态重要性分 I_news，0-100',
  `s_direction` decimal(6,4) DEFAULT NULL COMMENT '信号：最佳模型方向强度',
  `s_agreement` decimal(6,4) DEFAULT NULL COMMENT '信号：多模型方向一致性',
  `s_horizon` decimal(6,4) DEFAULT NULL COMMENT '信号：期限',
  `s_category` decimal(6,4) DEFAULT NULL COMMENT '信号：因子最高类别权重',
  `s_hit` decimal(6,4) DEFAULT NULL COMMENT '信号：因子命中率先验均值',
  `s_nfactor` decimal(6,4) DEFAULT NULL COMMENT '信号：关联因子数量（饱和归一）',
  `s_rich` decimal(6,4) DEFAULT NULL COMMENT '信号：内容丰富度（图/表/标题块）',
  `s_policy` tinyint(1) NOT NULL DEFAULT 0 COMMENT '信号：政策标记 0/1',
  `s_source` decimal(6,4) DEFAULT NULL COMMENT '信号：来源权重',
  `factor_count` int(11) NOT NULL DEFAULT 0 COMMENT 'DISTINCT 关联因子数',
  `top_category` varchar(20) DEFAULT NULL COMMENT '权重最高的因子类别',
  `signals_json` json DEFAULT NULL COMMENT '全部信号子分与原始取值（解释/台账）',
  `computed_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '本次计算时间',
  PRIMARY KEY (`news_id`, `score_version`),
  KEY `idx_nis_version_score` (`score_version`, `importance_score`),
  KEY `idx_nis_computed` (`computed_at`),
  CONSTRAINT `fk_nis_news` FOREIGN KEY (`news_id`) REFERENCES `news` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='新闻重要性打分（静态分量预计算，时间衰减读时施加）';
