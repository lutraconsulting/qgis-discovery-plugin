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
        self.key = ""

        # signals
        self.buttonBox.button(QDialogButtonBox.Help).clicked.connect(self.show_help)
        self.addButton.clicked.connect(self.add_config)
        self.deleteButton.clicked.connect(self.delete_config)
        self.configListW.itemClicked.connect(self.on_item_clicked)

        settings = QSettings()
        settings.beginGroup("/Discovery")

        # init config list
        if not settings.value("config_list"):
            settings.setValue("config_list", [])
        config_list = settings.value("config_list")

        for key in config_list:
            item = QListWidgetItem(key)
            self.configListW.addItem(item)

        if self.configListW.count():
            self.configListW.setCurrentRow(0)

        key = self.configListW.currentItem().text() if self.configListW.currentItem() else ""


        # TODO !!! disable when empty
        if (not self.configListW.currentItem()):
            self.enable_form(False)
        self.enable_form(False)
        self.set_form_fields(key)

    def set_form_fields(self, key = ""):

        QApplication.setOverrideCursor(Qt.WaitCursor)
        settings = QSettings()
        settings.beginGroup("/Discovery")
        #key = "osdata"

        # connections
        self.cboConnection.addItem('')
        for conn in dbutils.get_postgres_connections():
            self.cboConnection.addItem(conn)
        self.init_combo_from_settings(self.cboConnection, key + "connection")
        self.cboConnection.currentIndexChanged.connect(self.connect_db)
        self.connect_db()
        # schemas
        self.init_combo_from_settings(self.cboSchema, key + "schema")
        self.cboSchema.currentIndexChanged.connect(self.populate_tables)
        self.populate_tables()
        # tables
        self.init_combo_from_settings(self.cboTable, key + "table")
        self.cboTable.currentIndexChanged.connect(self.populate_columns)
        self.populate_columns()
        # columns
        self.init_combo_from_settings(self.cboSearchColumn, key + "search_column")
        self.init_combo_from_settings(self.cboGeomColumn, key + "geom_column")
        echo_search_col = settings.value(key + "echo_search_column", True, type=bool)
        if echo_search_col:
            self.cbEchoSearchColumn.setCheckState(Qt.Checked)
        else:
            self.cbEchoSearchColumn.setCheckState(Qt.Unchecked)
        columns = settings.value(key + "display_columns", "", type=str)
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
        self.editScaleExpr.setText(settings.value(key + "scale_expr", "", type=str))
        self.editBboxExpr.setText(settings.value(key + "bbox_expr", "", type=str))
        self.chkMarkerTime.setChecked(settings.value(key + "marker_time_enabled", True, type=bool))
        self.spinMarkerTime.setValue(settings.value(key + "marker_time", 5000, type=int) / 1000)

        # TODO only on init
        self.chkMarkerTime.stateChanged.connect(self.time_checkbox_changed)
        self.time_checkbox_changed()

        QApplication.restoreOverrideCursor()


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

    def write_config_to_list(self, key, settings):
        #settings = QSettings()
        #settings.beginGroup("/Discovery")

        #configs_list = settings.value("config_list")
        configs_list = {}

        config = {"connection": self.cboConnection.currentText,
                  "schema": self.cboSchema.currentText,
                  "table": self.cboTable.currentText,
                  "search_column": self.cboSearchColumn.currentText,
                  "echo_search_column": self.cbEchoSearchColumn.isChecked,
                  "display_columns": self.display_columns(),
                  "geom_column": self.cboGeomColumn.currentText,
                  "scale_expr": self.editScaleExpr.text,
                  "bbox_expr": self.editBboxExpr.text,
                  "marker_time_enabled": self.chkMarkerTime.isChecked,
                  "marker_time": self.spinMarkerTime.value
                  }

        # if not (configs_list):
        #     configs_list = {}
        # configs_list[key] = config
        # print("DEBUG!! saving config")
        #
        # dict = {}
        # for k, v in configs_list.items():
        #     dict[str(k)] = v
        # settings.setValue("config_list", dict)
        dict2 = {}
        dict2["fdsfs"] = 3
        dict3 = {"sdasd": 3}
        print(dict2)
        print(dict3)
        data = {'one': 1, 'two': dict3}
        settings.setValue('data', data)
        print("DEBUG!! data saved")

        data = settings.value('data')
        d = {}
        for k, v in data.items():
            d[str(k)] = v
        print("DEBUG!! data converted")
        print(d)

        print(configs_list)

    def write_config(self):

        settings = QSettings()
        settings.beginGroup("/Discovery")

        key = self.cboConnection.currentText()
        print("KEY write: " + key)

        config_list = settings.value("config_list")
        if not config_list:
            config_list = []

        if key not in config_list:
            config_list.append(key)
            settings.setValue("config_list", config_list)
        self.key = key
        settings.setValue(key + "connection", self.cboConnection.currentText())
        settings.setValue(key + "schema", self.cboSchema.currentText())
        settings.setValue(key + "table", self.cboTable.currentText())
        settings.setValue(key + "search_column", self.cboSearchColumn.currentText())
        settings.setValue(key + "echo_search_column", self.cbEchoSearchColumn.isChecked())
        settings.setValue(key + "display_columns", self.display_columns())
        settings.setValue(key + "geom_column", self.cboGeomColumn.currentText())
        settings.setValue(key + "scale_expr", self.editScaleExpr.text())
        settings.setValue(key + "bbox_expr", self.editBboxExpr.text())
        settings.setValue(key + "marker_time_enabled", self.chkMarkerTime.isChecked())
        settings.setValue(key + "marker_time", self.spinMarkerTime.value()*1000)

        #self.write_config_to_list(self.cboConnection.currentText(), settings)

    def reload_data(self, key):
        settings = QSettings()
        settings.beginGroup("/Discovery")

        self.cboConnection.setEditText(settings.value(key + "connection"))
        self.cboSchema.setEditText(settings.value(key + "schema"))
        self.cboTable.setEditText(settings.value(key + "table"))
        self.cboSearchColumn.setEditText(settings.value(key + "search_column"))

        self.cbEchoSearchColumn.setChecked(settings.value(key + "echo_search_column") == "true")
        self.display_columns.setEditText(settings.value(key + "display_columns"))

        print("DEBUG!!!")
        print(settings.value(key + "display_columns"))
        self.cboGeomColumn.setEditText(settings.value(key + "geom_column"))
        self.editScaleExpr.setText(settings.value(key + "scale_expr", self.editScaleExpr.text()))
        self.editBboxExpr.setText(settings.value(key + "bbox_expr", self.editBboxExpr.text()))
        #self.chkMarkerTime
        #self.spinMarkerTime

    def time_checkbox_changed(self):
        self.spinMarkerTime.setEnabled(self.chkMarkerTime.isChecked())

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

    # TODO name
    def add_config(self):
        txt = "New config"
        item = QListWidgetItem(txt)
        self.configListW.addItem(item)
        self.configListW.setCurrentItem(item)

        settings = QSettings()
        settings.beginGroup("/Discovery")
        config_list = settings.value("config_list")
        config_list.append(txt)
        settings.setValue("config_list", config_list)

        # reset fields
        self.set_form_fields()
        print("!!!add config")


    def enable_form(self, enable = True):
        self.formLayout.setEnabled(enable)

    # ask if really wanted to delete
    # delete selected config
    def delete_config(self):
        if self.configListW.currentItem():
            print("!!!delete config")
            item_text = self.configListW.currentItem().text()
            item = self.configListW.takeItem(self.configListW.currentRow())
            del item

            settings = QSettings()
            settings.beginGroup("/Discovery")
            config_list = settings.value("config_list")
            config_list.remove(item_text)
            settings.setValue("config_list", config_list)

            if (self.configListW.count()):
                self.configListW.setCurrentRow(0)
                self.on_item_clicked()
            else:
                self.enable_form(False)

    #TODO render form
    # TODO read correct config from settings
    # TODO onnect it to changeSelectedItem instead of click
    def on_item_clicked(self):
        print("ITEM clicked")
        #self.render_config_form()
        self.key = self.configListW.currentItem().text()
        self.set_form_fields(self.key)

    def show_help(self):
        QDesktopServices.openUrl(QUrl("http://www.lutraconsulting.co.uk/products/discovery/"))
