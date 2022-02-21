from os import getenv

db_config = {
    "mysql": {
        "host": getenv("MYSQL_HOST"),
        "user": getenv("MYSQL_USER"),
        "pass": getenv("MYSQL_PASS"),
    }
}