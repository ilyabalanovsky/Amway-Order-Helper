from db.database import Database


def test_database_backup_preserves_existing_data(tmp_path) -> None:
    source_path = tmp_path / "source.sqlite3"
    destination_path = tmp_path / "nested" / "destination.sqlite3"
    database = Database(source_path)
    database.initialize()
    with database.connect() as connection:
        connection.execute("INSERT INTO partner_groups (name) VALUES (?)", ("Тестовая группа",))
        connection.commit()

    database.backup_to(destination_path)

    copied_database = Database(destination_path)
    with copied_database.connect() as connection:
        group = connection.execute("SELECT name FROM partner_groups").fetchone()
    assert group["name"] == "Тестовая группа"
