from django.db import migrations


def create_features(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('''
            CREATE VIEW repair_summary AS
            SELECT r.id, r.item_name, r.status, c.name AS category,
                   r.created_at, r.completed_at,
                   COALESCE(SUM(u.quantity), 0) AS parts_used
            FROM repairs_repairrequest r
            JOIN repairs_itemcategory c ON c.id = r.category_id
            LEFT JOIN repairs_partusage u ON u.request_id = r.id
            GROUP BY r.id, r.item_name, r.status, c.name, r.created_at, r.completed_at
        ''')
        if schema_editor.connection.vendor == 'postgresql':
            cursor.execute('''
                CREATE FUNCTION log_repair_status() RETURNS trigger AS $$
                DECLARE actor_text text;
                BEGIN
                    actor_text := current_setting('repaircafe.actor_id', true);
                    INSERT INTO repairs_repairstatushistory
                        (request_id, old_status, new_status, changed_by_id, changed_at, note)
                    VALUES (NEW.id, OLD.status, NEW.status,
                        NULLIF(actor_text, '')::bigint, NOW(), 'Database trigger');
                    RETURN NEW;
                END;
                $$ LANGUAGE plpgsql
            ''')
            cursor.execute('''
                CREATE TRIGGER repair_status_audit
                AFTER UPDATE OF status ON repairs_repairrequest
                FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status)
                EXECUTE FUNCTION log_repair_status()
            ''')
            cursor.execute('''
                CREATE PROCEDURE complete_repair(IN p_request_id bigint)
                LANGUAGE plpgsql AS $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM repairs_repairsession WHERE request_id = p_request_id) THEN
                        RAISE EXCEPTION 'A repair session is required';
                    END IF;
                    UPDATE repairs_repairrequest
                    SET status = 'completed', completed_at = NOW(), updated_at = NOW()
                    WHERE id = p_request_id AND status NOT IN ('completed', 'cancelled');
                    IF NOT FOUND THEN
                        RAISE EXCEPTION 'Repair is already closed or does not exist';
                    END IF;
                END;
                $$
            ''')


def drop_features(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        if schema_editor.connection.vendor == 'postgresql':
            cursor.execute('DROP PROCEDURE IF EXISTS complete_repair(bigint)')
            cursor.execute('DROP TRIGGER IF EXISTS repair_status_audit ON repairs_repairrequest')
            cursor.execute('DROP FUNCTION IF EXISTS log_repair_status()')
        cursor.execute('DROP VIEW IF EXISTS repair_summary')


class Migration(migrations.Migration):
    dependencies = [('repairs', '0001_initial')]
    operations = [migrations.RunPython(create_features, drop_features)]
