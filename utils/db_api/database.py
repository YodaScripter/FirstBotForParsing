import mysql.connector
from mysql.connector import Error
from utils.misc.logging import logger


async def create_connection_mysql_db(db_host, user_name, user_password, db_name=None):
    connection_db = None
    try:

        connection_db = mysql.connector.connect(
            host=db_host,
            user=user_name,
            passwd=user_password,
            database=db_name
        )
        logger.info("Присоеднинение к БД")
    except Error as db_connection_error:
        logger.error("Возникла ошибка присоеднинения к БД: ", db_connection_error)
    return connection_db
