"""
Configuration file for DB and FILES
"""

from parsers import parse_follower, parse_following
from exporters import export_to_html, export_to_csv, export_to_json, export_to_txt

FILES_CONFIG = {
    "followers": {
        "file_name": "followers_1.json",
        "parser": parse_follower,
        "item_path": "item",
    },
    "following": {
        "file_name": "following.json",
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
        );""",
]

PROCESS_OPTIONS = {
    "1": {
        "title": "Who doesn't follow me back",
        "output_message": "There are {} people that don't follow me back",
        "query": "SELECT p.username FROM people p JOIN following f ON p.id = f.user_id LEFT JOIN followers fo ON p.id = fo.user_id WHERE fo.user_id IS NULL",
    },
    "2": {
        "title": "My followers",
        "output_message": "I have {} followers",
        "query": "SELECT p.username FROM people p JOIN followers f ON p.id = f.user_id",
    },
    "3": {
        "title": "My following",
        "output_message": "I follow {} people",
        "query": "SELECT p.username FROM people p JOIN following f ON p.id = f.user_id",
    },
    "4": {
        "title": "Who I don't follow back",
        "output_message": "There are {} people that I don't follow back",
        "query": "SELECT p.username FROM followers f JOIN people p ON f.user_id = p.id LEFT JOIN following fg ON f.user_id = fg.user_id WHERE fg.user_id IS NULL",
    },
}

EXPORT_OPTIONS = {
    "1": {
        "title": "Export as HTML",
        "extension": "{}.html",
        "exporter": export_to_html,
    },
    "2": {
        "title": "Export as JSON",
        "extension": "{}.json",
        "exporter": export_to_json,
        "indent": 4,
    },
    "3": {"title": "Export as CSV", "extension": "{}.csv", "exporter": export_to_csv},
    "4": {"title": "Export as TXT", "extension": "{}.txt", "exporter": export_to_txt},
    "5": {"title": "Don't export", "extension": False},
}
