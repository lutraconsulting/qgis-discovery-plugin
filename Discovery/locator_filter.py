# -*- coding: utf-8 -*-

# Discovery Plugin
#
# Copyright (C) 2017 Lutra Consulting
# info@lutraconsulting.co.uk
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.


from qgis.core import QgsLocatorFilter, QgsLocatorResult

from . import config_dialog
from . import dbutils


class DiscoveryLocatorFilter(QgsLocatorFilter):
    def __init__(self, plugin):
        QgsLocatorFilter.__init__(self, None)
        self.plugin = plugin

    def clone(self):
        return DiscoveryLocatorFilter(self.plugin)

    def name(self):
        return "discovery"

    def displayName(self):
        return "Discovery - search in PostGIS tables"

    def prefix(self):
        return "dis"

    def fetchResults(self, text, context, feedback):

        if len(text) < 3:
            return

        query_text, query_dict = dbutils.get_search_sql(
                                    text,
                                    self.plugin.postgisgeomcolumn,
                                    self.plugin.postgissearchcolumn,
                                    self.plugin.echosearchcolumn,
                                    self.plugin.postgisdisplaycolumn,
                                    self.plugin.extra_expr_columns,
                                    self.plugin.postgisschema,
                                    self.plugin.postgistable)

        cur = self.plugin.get_db_cur()
        cur.execute(query_text, query_dict)

        for row in cur.fetchall():

            if feedback.isCanceled():
                return

            geom, epsg, suggestion_text = row[0], row[1], row[2]
            extra_data = {}
            for idx, extra_col in enumerate(self.plugin.extra_expr_columns):
                extra_data[extra_col] = row[3+idx]

            res = QgsLocatorResult(self, suggestion_text, (geom, epsg, extra_data))
            self.resultFetched.emit(res)

    def triggerResult(self, result):
        self.plugin.select_result(result.userData)

    def hasConfigWidget(self):
        return True

    def openConfigWidget(self, parent):
        dlg = config_dialog.ConfigDialog(parent)
        if dlg.exec_():
            dlg.write_config()
            self.plugin.read_config()
