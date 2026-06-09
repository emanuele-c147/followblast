"""
Read Instagram followers/following JSON exports and migrate them to a SQLite database.
"""

import ijson
import sqlite3


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


def connect(db_name="ig_contacts.db"):
    """Establish a connection with the database"""

    conn = sqlite3.connect(db_name)
    return conn


def read_json(file, item_path):
    """Reads the json content item by item avoiding RAM saturation"""

    with open(file, 'rb') as f:
        for contact in ijson.items(f, item_path):
            yield contact


def main():
    """Load followers and following from Instagram JSON exports and save them to SQLite."""

    db_conn = connect()

    for contact_type, config in FILES_CONFIG.items():

        contacts = read_json(config["file"], config["item_path"])

        # TODO: insert contacts into SQLite


if __name__ == "__main__":
    main()
