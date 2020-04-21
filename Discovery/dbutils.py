# -*- coding: utf-8 -*-

# Discovery Plugin
#
# Copyright (C) 2015 Lutra Consulting
# info@lutraconsulting.co.uk
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from PyQt5.QtCore import QSettings

import psycopg2

from qgis.core import QgsApplication, QgsAuthMethodConfig


def get_connection(conn_info):
    """ Connect to the database using conn_info dict:
     { 'host': ..., 'port': ..., 'database': ..., 'username': ..., 'password': ... }
    """
    conn = psycopg2.connect(**conn_info)
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def get_postgres_connections():
    """ Read PostgreSQL connection names from QSettings stored by QGIS
    """
    settings = QSettings()
    settings.beginGroup(u"/PostgreSQL/connections/")
    return settings.childGroups()


"""
def current_postgres_connection():
    settings = QSettings()
    settings.beginGroup("/Discovery")
    return settings.value("connection", "", type=str)
"""

def get_postgres_conn_info(selected):
    """ Read PostgreSQL connection details from QSettings stored by QGIS
    """
    settings = QSettings()
    settings.beginGroup(u"/PostgreSQL/connections/" + selected)
    if not settings.contains("database"): # non-existent entry?
        return {}

    conn_info = dict()

    #Check if a service is provided
    service = settings.value("service", '', type=str)
    hasService = len(service) > 0
    if hasService:
        conn_info["service"] = service

    # password and username
    username = ''
    password = ''
    authconf = settings.value('authcfg', '')
    if authconf :
        # password encrypted in AuthManager
        auth_manager = QgsApplication.authManager()
        conf = QgsAuthMethodConfig()
        auth_manager.loadAuthenticationConfig(authconf, conf, True)
        if conf.id():
            username = conf.config('username', '')
            password = conf.config('password', '')
    else:
        # basic (plain-text) settings
        username = settings.value('username', '', type=str)
        password = settings.value('password', '', type=str)

    # password and username could be stored in environment variables
    # if not present in AuthManager or plain-text settings, do not
    # add it to conn_info at all
    if len(username) > 0:
        conn_info["user"] = username
    if len(password) > 0:
        conn_info["password"] = password

    host = settings.value("host", "", type=str)
    database = settings.value("database", "", type=str)
    port = settings.value("port", "", type=str)

    #Prevent setting host, port or database to empty string or default value
    #It may by set in a provided service and would overload it
    if len(host) > 0:
        conn_info["host"] = host
    if len(database) > 0:
        conn_info["database"] = database
    if len(port) > 0:
        conn_info["port"] = int(port)

    return conn_info


def _quote(identifier):
    """ quote identifier """
    return u'"%s"' % identifier.replace('"', '""')


def _quote_str(txt):
    """ make the string safe - replace ' with '' """
    return txt.replace("'", "''")


def list_schemas(cursor):
    """ Get list of schema names
    """
    sql = "SELECT nspname FROM pg_namespace WHERE nspname !~ '^pg_' AND nspname != 'information_schema'"
    cursor.execute(sql)

    names = map(lambda row: row[0], cursor.fetchall())
    return sorted(names)


def list_tables(cursor, schema):
    sql = """SELECT pg_class.relname
                FROM pg_class
                JOIN pg_namespace ON pg_namespace.oid = pg_class.relnamespace
                WHERE pg_class.relkind IN ('v', 'r', 'm') AND nspname = '%s'
                ORDER BY nspname, relname""" % _quote_str(schema)
    cursor.execute(sql)
    names = map(lambda row: row[0], cursor.fetchall())
    return sorted(names)


def list_columns(cursor, schema, table):
    sql = """SELECT a.attname AS column_name
        FROM pg_class c
        JOIN pg_attribute a ON a.attrelid = c.oid
        JOIN pg_namespace nsp ON c.relnamespace = nsp.oid
        WHERE c.relname = '%s' AND nspname='%s' AND a.attnum > 0
        ORDER BY a.attnum""" % (_quote_str(table), _quote_str(schema))
    cursor.execute(sql)
    names = map(lambda row: row[0], cursor.fetchall())
    return sorted(names)


def get_search_sql(search_text, geom_column, search_column, echo_search_column, display_columns, extra_expr_columns, schema, table):
    """ Returns a tuple: (SQL query text, dictionary with values to replace variables with).
    """

    """
    Spaces in queries
        A query with spaces is executed as follows:
            'my query'
            ILIKE '%my%query%'

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
                        ST_AsText("%s") AS geom,
                        ST_SRID("%s") AS epsg,
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
                        "%s"."%s"
                     WHERE
                        "%s" ILIKE
                  """ % (schema, table, search_column)
    query_text += """   %(search_text)s
                  """
    query_text += """ORDER BY
                        "%s"
                    LIMIT 1000
                  """ % search_column

    return query_text, query_dict
