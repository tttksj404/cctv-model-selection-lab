INSERT INTO media_servers (
    id,
    server_code,
    name,
    device_key_id,
    device_key_hash,
    status
) VALUES (
    152001,
    'recording-fixture-server-1',
    'Recording Mapper Fixture Media Server 1',
    'recfixture000001',
    'fixture-device-key-hash-152001',
    'ACTIVE'
);

INSERT INTO media_servers (
    id,
    server_code,
    name,
    device_key_id,
    device_key_hash,
    status
) VALUES (
    152002,
    'recording-fixture-server-2',
    'Recording Mapper Fixture Media Server 2',
    'recfixture000002',
    'fixture-device-key-hash-152002',
    'ACTIVE'
);

INSERT INTO cameras (
    id,
    media_server_id,
    camera_name,
    camera_code,
    latitude,
    longitude,
    address,
    stream_url,
    status
) VALUES (
    153001,
    152001,
    'Recording Mapper Fixture Camera 1',
    'recording-fixture-camera-153001',
    37.5665000,
    126.9780000,
    'Recording Mapper Fixture Address 1',
    'rtsp://recording-fixture/153001/stream',
    'OFFLINE'
);

INSERT INTO cameras (
    id,
    media_server_id,
    camera_name,
    camera_code,
    latitude,
    longitude,
    address,
    stream_url,
    status
) VALUES (
    153002,
    152002,
    'Recording Mapper Fixture Camera 2',
    'recording-fixture-camera-153002',
    37.5666000,
    126.9781000,
    'Recording Mapper Fixture Address 2',
    'rtsp://recording-fixture/153002/stream',
    'OFFLINE'
);
