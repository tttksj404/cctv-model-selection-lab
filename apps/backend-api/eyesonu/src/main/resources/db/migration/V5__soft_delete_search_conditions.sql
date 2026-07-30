ALTER TABLE `search_conditions`
    ADD COLUMN `deleted_at` DATETIME(6) NULL AFTER `updated_at`;

CREATE INDEX `ix_search_conditions_case_deleted_created`
    ON `search_conditions` (`case_id`, `deleted_at`, `created_at` DESC);
