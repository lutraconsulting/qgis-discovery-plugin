import sys
from PyQt5.QtCore import QSettings
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from qgis.core import QgsMessageLog, QgsSettings
from . import dbutils


def get_mssql_connections():
    """ Read PostgreSQL connection names from QgsSettings stored by QGIS
    """
    settings = QgsSettings()
    settings.beginGroup(u"/MSSQL/connections/")
    return settings.childGroups()


def get_mssql_conn_info(connection):
    return connection


def get_connection(conn_name, service, host, database, username, password):
    # inspired by creation of connection string from QGIS MS SQL provider
    db = QSqlDatabase.addDatabase("QODBC", "discovery_" + conn_name)
    db.setHostName(host)
    if service:
        connection_string = service
    else:
        if sys.platform.startswith("win"):
            connection_string = "driver={SQL Server}"
        else:
            connection_string = "driver={FreeTDS};port=1433"
        if host:
            connection_string += ";server=" + host

        if database:
            connection_string += ";database=" + database
        if not password:
            connection_string += ";trusted_connection=yes"
        else:
            connection_string += ";uid=" + username + ";pwd=" + password
        connection_string += ";TDS_Version=8.0;ClientCharset=UTF-8"

        if username:
            db.setUserName(username)

        if password:
            db.setPassword(password)
    db.setDatabaseName(connection_string)

    if not db.open():
        raise Exception(db.lastError().text())
    return db


def get_mssql_conn(connection):
    settings = QgsSettings()
    settings.beginGroup(u"/MSSQL/connections/" + connection)
    service = settings.value('/service', "")
    host = settings.value('/host', "")
    database = settings.value('/database', "")
    username = settings.value('/username', "")
    password = settings.value('/password', "")
    return get_connection(connection, service, host, database, username, password)


def list_schemas(db):
    """ Get list of schema names
       """
    query = QSqlQuery(db)
    query_text = """SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_owner = 'dbo';"""  # TODO: better way to filter out system schemas
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return sorted(names)


def list_tables(db):
    query_text = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"
    query = QSqlQuery(db)
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return names


def list_columns(db, schema, table):
    query_text = """SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '%s' AND TABLE_SCHEMA ='%s';""" % (dbutils._quote_str(table), dbutils._quote_str(schema))
    query = QSqlQuery(db)
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return names

def _quote_brackets(identifier):
    """ quote identifier as [<identifier>]"""
    return u'[%s]' % identifier.replace('"', '""')

def get_search_sql(search_text, geom_column, search_column, echo_search_column, display_columns, extra_expr_columns, schema, table):
    wildcarded_search_string = ''
    for part in search_text.split():
        wildcarded_search_string += '%' + part
    wildcarded_search_string += '%'
    query_text = """ SELECT
                            [%s].STAsText() AS geom,
                            [%s].STSrid AS epsg,
                     """ % (geom_column, geom_column)

    info_columns = []
    if echo_search_column:
        info_columns.append(_quote_brackets(search_column))
    if len(display_columns) > 0:
        for display_column in display_columns.split(','):
            info_columns.append(_quote_brackets(display_column))

    if len(info_columns) == 0:
        query_text += "'' AS suggestion_string"
    elif len(info_columns) == 1:
        query_text += "CAST (%s AS nvarchar) AS suggestion_string" % info_columns[0]
    else:
        joined_info_columns = ", ', ' COLLATE Latin1_General_CI_AS, ".join(info_columns)
        query_text += "CONCAT( %s ) AS suggestion_string" % joined_info_columns

    for extra_column in extra_expr_columns:
        query_text += ', [%s]' % extra_column
    query_text += """
                      FROM
                            [%s].[%s]
                      WHERE [%s] LIKE
                      """ % (schema, table, search_column)
    query_text += """   '%s'
                      """ % wildcarded_search_string
    query_text += """ORDER BY
                            [%s]
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
