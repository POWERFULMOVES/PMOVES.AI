-- Seed data for local testing
insert into studio_board(title, namespace, content_url, status, meta)
values ('Hello World', 'pmoves', 's3://outputs/demo.png', 'submitted', '{"seed": true}'::jsonb);
