----------------------------------------
-- Table For Tracking Deleted Records
----------------------------------------
CREATE TABLE deleted_records (
    id serial,
    "table" varchar NOT NULL,
    record_id integer NOT NULL,
    deleted_at timestamp,
    primary key(id)
);

CREATE INDEX deleted_records_table_index
  ON deleted_records
  USING btree
  ("table");

CREATE INDEX deleted_records_record_id_index
  ON deleted_records
  USING btree
  (record_id);


---------------------------------
-- Trigger functions
---------------------------------
CREATE OR REPLACE FUNCTION trg_on_insert()
RETURNS TRIGGER AS $$
BEGIN
    NEW.write_date = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_on_update()
RETURNS TRIGGER AS $$
BEGIN
    NEW.write_date = NOW() AT TIME ZONE 'UTC';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_on_delete()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO deleted_records ("table", record_id, deleted_at)
        VALUES (TG_TABLE_NAME, OLD.ID, NOW() AT TIME ZONE 'UTC');
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;