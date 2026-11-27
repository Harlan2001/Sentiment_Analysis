-- 手工执行的结构迁移；本地启动不会自动运行本文件。
CREATE TABLE IF NOT EXISTS `workbench_chat_attachments` (
  `id` char(36) NOT NULL,
  `conversation_id` char(36) NOT NULL,
  `message_id` char(36) DEFAULT NULL,
  `owner_username` varchar(191) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `stored_filename` varchar(255) NOT NULL,
  `size_bytes` bigint unsigned NOT NULL,
  `page_count` int unsigned DEFAULT NULL,
  `created_at` datetime(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  PRIMARY KEY (`id`),
  KEY `idx_chat_attachments_conversation` (`conversation_id`, `created_at`),
  KEY `idx_chat_attachments_message` (`message_id`),
  CONSTRAINT `fk_chat_attachments_conversation` FOREIGN KEY (`conversation_id`) REFERENCES `workbench_conversations` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_chat_attachments_message` FOREIGN KEY (`message_id`) REFERENCES `workbench_messages` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `workbench_chat_attachment_chunks` (
  `id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `attachment_id` char(36) NOT NULL,
  `chunk_index` int unsigned NOT NULL,
  `source_location` varchar(255) NOT NULL,
  `content` mediumtext NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uq_chat_attachment_chunk` (`attachment_id`, `chunk_index`),
  CONSTRAINT `fk_chat_attachment_chunks_attachment` FOREIGN KEY (`attachment_id`) REFERENCES `workbench_chat_attachments` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
