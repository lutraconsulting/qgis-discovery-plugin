import pyodbc
from . import dbutils

def get_mssql_conn():

    # server = 'myserver,port' # to specify an alternate port
    server = 'localhost,1433'
    database = 'dis1'
    username = 'SA'
    password = 'post123GRES'
    conn = pyodbc.connect(
        'DRIVER={ODBC Driver 17 for SQL Server};SERVER=' + server + ';DATABASE=' + database + ';UID=' + username + ';PWD=' + password)
    return conn


def list_schemas(conn):
    """ Get list of schema names
       """
    query = """SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_owner = 'dbo';"""
    cursor = conn.cursor()
    cursor.execute(query)
    names = map(lambda row: row[0], cursor.fetchall())
    return sorted(names)


def list_tables(conn):
    query = "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"
    cursor = conn.cursor()
    cursor.execute(query)

    names = map(lambda row: row[0], cursor.fetchall())
    return sorted(names)


def list_columns(cursor, schema, table):
    query = """SELECT COLUMN_NAME
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_NAME = '%s' AND TABLE_SCHEMA ='%s';""" % (dbutils._quote_str(table), dbutils._quote_str(schema))
    cursor.execute(query)

    names = map(lambda row: row[0], cursor.fetchall())
    return sorted(names)

def get_search_sql(search_text, geom_column, search_column, echo_search_column, display_columns, extra_expr_columns, schema, table):
    wildcarded_search_string = ''
    for part in search_text.split():
        wildcarded_search_string += '%' + part
    wildcarded_search_string += '%'
    query_dict = wildcarded_search_string

    query_text = """ SELECT
                            "%s" AS geom,
                            '%s' AS epsg,
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
                         WHERE
                            "%s" LIKE
                      """ % (schema, table, search_column)
    query_text += """   ?
                      """
    query_text += """ORDER BY
                            "%s"
                      """ % search_column

    return query_text, query_dict

