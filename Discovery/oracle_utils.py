import sys
from PyQt5.QtCore import QSettings
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from qgis.core import QgsMessageLog, QgsSettings
from . import dbutils
from .utils import is_number


def get_oracle_connections():
    """ Read Oracle connection names from QgsSettings stored by QGIS
    """
    settings = QgsSettings()
    settings.beginGroup(u"/Oracle/connections/")
    return settings.childGroups()


def get_oracle_conn_info(connection):
    return connection


def get_connection(conn_name, host, database, port, username, password):
    """ Connect to the database using conn_info dict:
     { 'host': ..., 'port': ..., 'database': ..., 'username': ..., 'password': ... }
    """
    db = QSqlDatabase.addDatabase("QOCISPATIAL", "discovery_" + conn_name)
    connection_string = ""

    if host:
        connection_string = host

    if port not in ("1521"):
        connection_string = connection_string + ":" + port

    if database:
        connection_string = connection_string + "/" + database

    db.setDatabaseName(connection_string)
    db.setUserName(username)
    db.setPassword(password)

    if not db.open():
        raise Exception(db.lastError().text())
    return db


def get_oracle_conn(connection):
    settings = QgsSettings()
    settings.beginGroup(u"/Oracle/connections/" + connection)
    host = settings.value('/host', "")
    database = settings.value('/database', "")
    port     = settings.value('/port', "")
    username = settings.value('/username', "")
    password = settings.value('/password', "")
    return get_connection(connection, host, database, port, username, password)


def list_schemas(db):
    """ Get list of schema names
       """
    query = QSqlQuery(db)
    query_text = """SELECT u.username
            FROM all_users u
            WHERE EXISTS (SELECT null FROM all_tables t WHERE t.owner = u.username)
            ORDER BY u.username"""  # TODO: better way to filter out system schemas
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return names


def list_tables(db, schema):
    query_text = """SELECT object_name
            FROM all_objects
            WHERE object_type IN ('TABLE', 'VIEW')
            AND NOT REGEXP_LIKE (object_name, '^DR\\$|^MDRT_|^MDXT_')
            AND owner = '%s'
            ORDER BY object_name""" % dbutils._quote_str(schema)
    query = QSqlQuery(db)
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return names


def list_columns(db, schema, table):
    query_text = """SELECT column_name
                FROM all_tab_columns
                WHERE table_name = '%s' AND owner ='%s'
                ORDER BY column_id""" % (dbutils._quote_str(table), dbutils._quote_str(schema))
    query = QSqlQuery(db)
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return names

def _quote(identifier):
    """ quote identifier """
    return u'"%s"' % identifier.replace('"', '""')

def get_search_sql(search_text, geom_column, search_column, echo_search_column, display_columns, extra_expr_columns, schema, table, limit):
    """ Returns a tuple: (SQL query text, dictionary with values to replace variables with).
    """

    """
    Spaces in queries
        A query with spaces is executed as follows:
            'my query'
            LIKE '%my%query%'

    A note on spaces in postcodes
        Postcodes must be stored in the DB without spaces:
            'DL10 4DQ' becomes 'DL104DQ'
        This allows users to query with or without spaces
        As wildcards are inserted at spaces, it doesn't matter whether the query is:
            'dl10 4dq'; or
            'dl104dq'
    """
    wildcarded_search_string = ''
    for part in search_text.split():
        wildcarded_search_string += '%' + part
    wildcarded_search_string += '%'
    query_dict = {'search_text': wildcarded_search_string}
    query_text = """ SELECT
                        SDO_UTIL.TO_WKTGEOMETRY("%s") AS geom,
                        S."%s"."SDO_SRID" AS epsg,
                 """ % (geom_column, geom_column)

    if echo_search_column:
        query_column_selection_text = """"%s"
                                      """ % search_column
        suggestion_string_seperator = ', '
    else:
        query_column_selection_text = """''"""
        suggestion_string_seperator = ''
    if len(display_columns) > 0:
        for display_column in display_columns.split(','):
            query_column_selection_text += """ || CASE WHEN "%s" IS NOT NULL THEN
                                                     '%s' || "%s"
                                                 ELSE
                                                     ''
                                                 END
                                           """ % (display_column, suggestion_string_seperator, display_column)
            suggestion_string_seperator = ', '
    query_column_selection_text += """ AS suggestion_string """
    if query_column_selection_text.startswith("'', "):
        query_column_selection_text = query_column_selection_text[4:]
    query_text += query_column_selection_text
    for extra_column in extra_expr_columns:
        query_text += ', "%s"' % extra_column
    query_text += """
                  FROM
                        "%s"."%s" S
                     WHERE
                        LOWER("%s") LIKE
                  """ % (schema, table, search_column)
    query_text += """   LOWER('%s')
	              """ % (wildcarded_search_string)

    limit = "{}".format(int(limit)) if is_number(limit) else "1000"
    query_text += """AND ROWNUM <= %s""" % (limit)
    query_text += """ORDER BY
                            "%s"
                      """ % search_column
    return query_text


def execute(db, query_text):
    query = QSqlQuery(db)
    if not query.exec(query_text):
        QgsMessageLog.logMessage( query.lastError().text() + "\n\nQuery:\n" + query_text, "Discovery")
        return []

    record = query.record()
    result_set = []
    while query.next():
        row = []
        for i in range(record.count()):
            row.append(query.value(i))
        result_set.append(row)
    return result_set
