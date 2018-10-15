from PyQt5.QtCore import QSettings
from PyQt5.QtSql import QSqlDatabase, QSqlQuery
from . import dbutils


def get_mssql_connections():
    """ Read PostgreSQL connection names from QSettings stored by QGIS
    """
    settings = QSettings()
    settings.beginGroup(u"/mssql/connections/")
    return settings.childGroups()


def get_mssql_conn_info(connection):
    settings = QSettings()
    settings.beginGroup(u"/mssql/connections/" + connection)
    return settings.value('/service', "")


def get_mssql_conn(conn_service):
    db = QSqlDatabase.addDatabase("QODBC3")
    db.setDatabaseName(conn_service)
    db.open()
    return db


def list_schemas():
    """ Get list of schema names
       """
    query = QSqlQuery()
    query_text = """SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_owner = 'dbo';"""
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return sorted(names)


def list_tables():
    query_text = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"
    query = QSqlQuery()
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return names


def list_columns(schema, table):
    query_text = """SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '%s' AND TABLE_SCHEMA ='%s';""" % (dbutils._quote_str(table), dbutils._quote_str(schema))
    query = QSqlQuery()
    query.exec(query_text)
    names = []
    while query.next():
        names.append(query.value(0))
    return names


def get_search_sql(search_text, geom_column, search_column, echo_search_column, display_columns, extra_expr_columns, schema, table):
    wildcarded_search_string = ''
    for part in search_text.split():
        wildcarded_search_string += '%' + part
    wildcarded_search_string += '%'
    query_dict = {":search_string": wildcarded_search_string}
    query_text = """ SELECT
                            "%s".STAsText() AS geom,
                            "%s" AS epsg,
                     """ % (geom_column, "EPSG:27700")

    info_columns = []
    if echo_search_column:
        info_columns.append(dbutils._quote(search_column))
    if len(display_columns) > 0:
        for display_column in display_columns.split(','):
            info_columns.append(dbutils._quote(display_column))
    suggestion_string_seperator = ', '
    query_column_selection_text = """CONCAT_WS('%s', %s ) AS suggestion_string """ % (suggestion_string_seperator, ','.join(info_columns))

    query_text += query_column_selection_text
    for extra_column in extra_expr_columns:
        query_text += ', "%s"' % extra_column
    query_text += """
                      FROM
                            "%s"."%s"
                      WHERE "%s" LIKE
                      """ % (schema, table, search_column)
    query_text += """   :search_string
                      """
    query_text += """ORDER BY
                            "%s"
                      """ % search_column

    return query_text, query_dict


def execute(query_text, query_dict):
    query = QSqlQuery()
    query.prepare(query_text)
    for key in query_dict.keys():
       query.bindValue(key, query_dict[key])
    query.exec_()
    record = query.record()
    result_set = []
    while query.next():
        row = []
        for i in range(record.count()):
            row.append(query.value(i))
        result_set.append(row)
    print(result_set)
    return result_set

