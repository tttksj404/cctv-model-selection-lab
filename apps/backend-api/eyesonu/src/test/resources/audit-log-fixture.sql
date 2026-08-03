INSERT INTO admins (id, login_id, password_hash, name, role, enabled, created_at)
VALUES
    (255001, 'audit-admin-1', 'fixture-hash-1', 'Audit Admin One', 'ADMIN', TRUE, '2026-08-01 00:00:00.000000'),
    (255002, 'audit-admin-2', 'fixture-hash-2', 'Audit Admin Two', 'ADMIN', TRUE, '2026-08-01 00:00:00.000000');

INSERT INTO reporters (id, name, phone, email, relation)
VALUES (255001, 'Audit Reporter', '01012345678', NULL, NULL);

INSERT INTO cases (
    id,
    reporter_id,
    case_number,
    status,
    report_content,
    missing_name,
    gender,
    birth_year,
    upper_clothing,
    distinctive_features,
    last_seen_time,
    last_seen_address,
    reported_at,
    created_at,
    updated_at
) VALUES (
    255001,
    255001,
    'EFU-AUDIT255001ABCDEFGHJKM',
    'RECEIVED',
    'Audit fixture case',
    'Audit Missing Person',
    'UNKNOWN',
    2000,
    'Blue coat',
    'Audit fixture appearance',
    '2026-08-01 00:00:00.000000',
    'Audit fixture address',
    '2026-08-01 00:00:00.000000',
    '2026-08-01 00:00:00.000000',
    '2026-08-01 00:00:00.000000'
);

INSERT INTO audit_logs (
    id, admin_id, case_id, action_type, target_type, target_id,
    before_value, after_value, detail, created_at
) VALUES
    (255001, 255001, 255001, 'CASE_STATUS_CHANGED', 'CASE', 255001,
     '{"status":"RECEIVED"}', '{"status":"SEARCHING"}', '{"reason":"begin"}',
     '2026-08-02 01:00:00.000000'),
    (255002, 255002, NULL, 'ADMIN_LOGIN_SUCCESS', 'ADMIN', 255002,
     NULL, NULL, '{"ipFingerprint":"fingerprint"}',
     '2026-08-02 02:00:00.000000'),
    (255003, 255001, 255001, 'CASE_UPDATED', 'CASE', 255001,
     '{"status":"SEARCHING"}', '{"status":"CLOSED"}', '{}',
     '2026-08-02 03:00:00.000000');
