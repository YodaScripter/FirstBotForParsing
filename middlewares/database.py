# import mysql.connector
# from mysql.connector import Error
#
#
# async def create_connection_mysql_db(db_host, user_name, user_password, db_name=None):
#     connection_db = None
#     try:
#         connection_db = mysql.connector.connect(
#             host=db_host,
#             user=user_name,
#             passwd=user_password,
#             database=db_name
#         )
#     except Error as db_connection_error:
#         print("Возникла ошибка: ", db_connection_error)
#     return connection_db
