"""
Read Instagram followers/following JSON exports and migrate them to a SQLite database.
"""

import ijson
import sqlite3
from contextlib import contextmanager


def parse_follower(contact):
    """Normalize a raw follower entry into a flat {column: value} dict."""

    data = contact["string_list_data"][0]

    parsed_dict = {
        "username": data["value"],
        "contact_reference": data["href"],
        "timestamp": data["timestamp"]
    }

    return parsed_dict


def parse_following(contact):
    """Normalize a raw following entry into a flat {column: value} dict."""

    data = contact["string_list_data"][0]

    parsed_dict = {
        "username": contact["title"],
        "contact_reference": data["href"],
        "timestamp": data["timestamp"]
    }

    return parsed_dict


FILES_CONFIG = {
    "followers": {
        "file": "followers_1.json",
        "parser": parse_follower,
        "item_path": "item",
    },
    "following": {
        "file": "following.json",
        "parser": parse_following,
        "item_path": "relationships_following.item",
    },
}

DB_CONFIG = [
    """CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            contact_reference TEXT
        );""",
    """CREATE TABLE IF NOT EXISTS followers (
            user_id INTEGER PRIMARY KEY,
            timestamp INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES people(id)
        );""",
    """CREATE TABLE IF NOT EXISTS following (
            user_id INTEGER PRIMARY KEY,
            timestamp INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES people(id)
        );"""
]


@contextmanager
def connect(db_name="ig_contacts.db"):
    """Establish, yield, and safely close a database connection."""

    conn = sqlite3.connect(db_name)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.cursor()
        for create_table_query in DB_CONFIG:
            cur.execute(create_table_query)
        conn.commit()

        yield conn
    finally:
        conn.close()


def read_json(file, item_path):
    """Reads the json content item by item avoiding RAM saturation"""

    with open(file, 'rb') as f:
        for contact in ijson.items(f, item_path):
            yield contact


def contacts_to_database(db_conn, contact_type, contacts, parser):
    """Parse and insert contacts into the appropriate SQLite table.

    Args:
        db_conn: Active SQLite connection.
        contact_type: Table name / label ('followers' or 'following').
        contacts: Iterable of raw contact dicts from the JSON.
        parser: Function that normalizes a raw contact into a flat dict.
    """
    cur = db_conn.cursor()

    for contact in contacts:

        # Remap raw keys to a consistent schema
        contact_data = parser(contact)

        cur.execute(
            "INSERT OR IGNORE INTO people (username, contact_reference) VALUES (:username, :contact_reference)",
            contact_data
        )

        user_id = cur.execute(
            "SELECT id FROM people WHERE username = :username",
            contact_data
        ).fetchone()[0]

        cur.execute(
            f"INSERT OR IGNORE INTO {contact_type} (user_id, timestamp) VALUES (?, ?)",
            (user_id, contact_data["timestamp"])
        )

    db_conn.commit()


def extract_contact(db_conn):
    """Query the DB on what the user wants to see."""

    cur = db_conn.cursor()

    options = {
        "1": {
            "text1": "Who doesn't follow me back",
            "text2": "There are {} people that don't follow me back",
            "query": "SELECT p.username FROM people p JOIN following f ON p.id = f.user_id LEFT JOIN followers fo ON p.id = fo.user_id WHERE fo.user_id IS NULL"
        },
        "2": {
            "text1": "My followers",
            "text2": "I have {} followers",
            "query": "SELECT p.username, f.timestamp FROM people p JOIN followers f ON p.id = f.user_id"
        },
        "3": {
            "text1": "My following",
            "text2": "I follow {} people",
            "query": "SELECT p.username, f.timestamp FROM people p JOIN following f ON p.id = f.user_id"
        }
    }

    print("What do you want to know?")
    for option in options:
        print(f"{option}- {options[option]['text1']}")

    user_option = input("1, 2, 3: ")

    while user_option not in options:
        print("Invalid input, must be: 1, 2 or 3")
        user_option = input("1, 2, 3: ")

    query = options[user_option]["query"]

    count_rows_query = f"SELECT COUNT(*) FROM ({query})"

    cur.execute(count_rows_query)
    total_rows = cur.fetchone()[0]

    print(options[user_option]["text2"].format(total_rows))

    cur.execute(query)
    for row in cur:
        print(f"- {row[0]}")


def main():
    """Load followers and following from Instagram JSON exports and save them to SQLite.
    Extract data from the DB to see various information.
    """

    print("Instagram Contacts Manager")
    print("By Emanuele Canazza - https://github.com/emanuele-c147")
    print()

    with connect() as db_conn:

        for contact_type, config in FILES_CONFIG.items():

            contacts = read_json(config["file"], config["item_path"])

            contacts_to_database(db_conn, contact_type, contacts, config["parser"])

        extract_contact(db_conn)


if __name__ == "__main__":
    main()
