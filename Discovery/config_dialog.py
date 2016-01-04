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

import os

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import uic

import dbutils

plugin_dir = os.path.dirname(__file__)

uiConfigDialog, qtBaseClass = uic.loadUiType(os.path.join(plugin_dir, 'config_dialog.ui'))



class ConfigDialog(qtBaseClass, uiConfigDialog):

    def __init__(self, parent=None):
        qtBaseClass.__init__(self, parent)
        self.setupUi(self)

        self.conn = None

        self.buttonBox.button(QDialogButtonBox.Help).clicked.connect(self.show_help)

        settings = QSettings()
        settings.beginGroup("/Discovery")

        # connections

        self.cboConnection.addItem('')
        for conn in dbutils.get_postgres_connections():
            self.cboConnection.addItem(conn)

        self.init_combo_from_settings(self.cboConnection, "connection")
        self.cboConnection.currentIndexChanged.connect(self.connect_db)
        self.connect_db()

        # schemas
        self.init_combo_from_settings(self.cboSchema, "schema")
        self.cboSchema.currentIndexChanged.connect(self.populate_tables)
        self.populate_tables()

        # tables
        self.init_combo_from_settings(self.cboTable, "table")
        self.cboTable.currentIndexChanged.connect(self.populate_columns)
        self.populate_columns()

        # columns
        self.init_combo_from_settings(self.cboSearchColumn, "search_column")
        self.init_combo_from_settings(self.cboGeomColumn, "geom_column")

        echo_search_col = settings.value("echo_search_column", True, type=bool)
        if echo_search_col:
            self.cbEchoSearchColumn.setCheckState(Qt.Checked)
        else:
            self.cbEchoSearchColumn.setCheckState(Qt.Unchecked)

        columns = settings.value("display_columns", "", type=str)
        if len(columns) != 0:
            lst = columns.split(",")
            self.set_combo_current_text(self.cboDisplayColumn1, lst[0])
            if len(lst) > 1:
                self.set_combo_current_text(self.cboDisplayColumn2, lst[1])
            if len(lst) > 2:
                self.set_combo_current_text(self.cboDisplayColumn3, lst[2])
            if len(lst) > 3:
                self.set_combo_current_text(self.cboDisplayColumn4, lst[3])
            if len(lst) > 4:
                self.set_combo_current_text(self.cboDisplayColumn5, lst[4])

        self.editScaleExpr.setText(settings.value("scale_expr", "", type=str))
        self.editBboxExpr.setText(settings.value("bbox_expr", "", type=str))

    def init_combo_from_settings(self, cbo, settings_key):
        settings = QSettings()
        settings.beginGroup("/Discovery")
        name = settings.value(settings_key, "", type=str)
        self.set_combo_current_text(cbo, name)

    def set_combo_current_text(self, cbo, name):
        idx = cbo.findText(name)
        cbo.setCurrentIndex(idx) if idx != -1 else cbo.setEditText(name)

    def connect_db(self):
        name = self.cboConnection.currentText()
        try:
            self.conn = dbutils.get_connection(dbutils.get_postgres_conn_info(name))
            self.lblMessage.setText("")
        except StandardError, e:
            self.conn = None
            self.lblMessage.setText("<font color=red>"+ e.message +"</font>")
        self.populate_schemas()

    def populate_schemas(self):
        self.cboSchema.clear()
        self.cboSchema.addItem('')
        if self.conn is None: return
        for schema in dbutils.list_schemas(self.conn.cursor()):
            self.cboSchema.addItem(schema)

    def populate_tables(self):
        self.cboTable.clear()
        self.cboTable.addItem('')
        if self.conn is None: return
        for table in dbutils.list_tables(self.conn.cursor(), self.cboSchema.currentText()):
            self.cboTable.addItem(table)

    def populate_columns(self):
        cbos = [self.cboSearchColumn, self.cboGeomColumn, self.cboDisplayColumn1, self.cboDisplayColumn2,
                self.cboDisplayColumn3, self.cboDisplayColumn4, self.cboDisplayColumn5]
        for cbo in cbos:
            cbo.clear()
            cbo.addItem("")
        if self.conn is None: return
        columns = dbutils.list_columns(self.conn.cursor(), self.cboSchema.currentText(), self.cboTable.currentText())
        for cbo in cbos:
            for column in columns:
                cbo.addItem(column)

    def write_config(self):

        settings = QSettings()
        settings.beginGroup("/Discovery")

        settings.setValue("connection", self.cboConnection.currentText())
        settings.setValue("schema", self.cboSchema.currentText())
        settings.setValue("table", self.cboTable.currentText())
        settings.setValue("search_column", self.cboSearchColumn.currentText())
        settings.setValue("echo_search_column", self.cbEchoSearchColumn.isChecked())
        settings.setValue("display_columns", self.display_columns())
        settings.setValue("geom_column", self.cboGeomColumn.currentText())
        settings.setValue("scale_expr", self.editScaleExpr.text())
        settings.setValue("bbox_expr", self.editBboxExpr.text())

    def display_columns(self):
        """ Make a string out of display columns, e.g. "column1,column2" or just "column1"
        """
        lst = []
        for cbo in [self.cboDisplayColumn1, self.cboDisplayColumn2, self.cboDisplayColumn3, self.cboDisplayColumn4,
                    self.cboDisplayColumn5]:
            txt = cbo.currentText()
            if len(txt) > 0:
                lst.append(txt)
        return ",".join(lst)

    def show_help(self):
        QDesktopServices.openUrl(QUrl("http://www.lutraconsulting.co.uk/products/discovery/"))
