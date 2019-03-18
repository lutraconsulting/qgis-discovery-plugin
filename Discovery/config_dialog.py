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

from PyQt5.QtCore import QSettings, Qt, QUrl
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QApplication, QDialogButtonBox, QMessageBox, QFileDialog, QDialog
from PyQt5 import uic
from . import dbutils
from . import discoveryplugin
from . import gpkg_utils
from . import mssql_utils

plugin_dir = os.path.dirname(__file__)

uiConfigDialog, qtBaseClass = uic.loadUiType(os.path.join(plugin_dir, 'config_dialog.ui'))


class ConfigDialog(qtBaseClass, uiConfigDialog):

    def __init__(self, parent=None):
        qtBaseClass.__init__(self, parent)
        self.setupUi(self)

        self.conn = None
        self.key = ""  # currently selected config key

        # signals
        self.buttonBox.button(QDialogButtonBox.Help).clicked.connect(self.show_help)
        self.addButton.clicked.connect(self.add_config)
        self.deleteButton.clicked.connect(self.delete_config)
        self.configOptions.currentIndexChanged.connect(self.config_selection_changed)
        self.cboName.textChanged.connect(self.validate_nameField)
        self.cboDataSource.currentIndexChanged.connect(self.data_type_changed)
        self.fileButton.clicked.connect(self.browse_file_db)
        self.cboFile.currentIndexChanged.connect(self.populate_tables)
        self.cboSchema.currentIndexChanged.connect(self.populate_tables)
        self.cboTable.currentIndexChanged.connect(self.populate_columns)

        settings = QSettings()
        settings.beginGroup("/Discovery")

        # init config list
        if not settings.value("config_list"):
            settings.setValue("config_list", [])
        config_list = settings.value("config_list")

        # prev version compatibility settings
        if self.prev_version_config_available():
            config_list.append("")
            settings.setValue("config_list", config_list)

        # if empty, add config
        if not config_list:
            config_list.append("New config")
            settings.setValue("config_list", config_list)

        self.init_cbo_data_source()
        self.cboConnection.currentIndexChanged.connect(self.connect_db)
        self.cboConnection.addItem("")

        for key in config_list:
            self.configOptions.addItem(key)

        if self.configOptions.count():
            self.configOptions.setCurrentIndex(0)

        self.key = self.configOptions.currentText() if self.configOptions.currentIndex() >= 0 else ""

        if not self.configOptions.count():
            self.enable_form(False)

        self.chkMarkerTime.stateChanged.connect(self.time_checkbox_changed)

    def init_cbo_data_source(self):
        self.cboDataSource.addItem("PostgreSQL", "postgres")
        self.cboDataSource.addItem("MS SQL Server", "mssql")
        self.cboDataSource.addItem("GeoPackage", "gpkg")
        self.cboDataSource.setCurrentIndex(0)

    def prev_version_config_available(self):
        settings = QSettings()
        settings.beginGroup("/Discovery")

        conn = settings.value("connection")
        if conn:
            return True
        return False


    def validate_nameField(self):
        settings = QSettings()
        settings.beginGroup("/Discovery")
        config_list = settings.value("config_list")
        key = self.cboName.text()

        if self.validate_key(key, config_list):
            self.cboName.setStyleSheet("")
            self.lblMessage.setText("")
        else:
            self.lblMessage.setText("<font color=red>Connection name is too short or already exists!</font>")
            self.cboName.setStyleSheet("QLineEdit {background-color: pink;}")

    # connected to buttonBox.accepted()
    def validate_and_accept(self):
        settings = QSettings()
        settings.beginGroup("/Discovery")
        config_list = settings.value("config_list")
        key = self.cboName.text()

        if self.validate_key(key, config_list):
            self.accept()
        else:
            self.cboName.setStyleSheet("QLineEdit {background-color: pink;}")

    def reset_form_fields(self):
        self.cboName.setText("")
        self.cboDataSource.setCurrentIndex(0)
        self.enable_fields_for_data_type()
        self.init_conn_schema_cbos([], "")
        self.cboTable.setCurrentIndex(0)
        self.populate_columns()

        for cbo in [self.cboSearchColumn, self.cboGeomColumn, self.cboDisplayColumn1, self.cboDisplayColumn2, self.cboDisplayColumn3, self.cboDisplayColumn4, self.cboDisplayColumn5]:
            cbo.setCurrentIndex(0)

    def set_form_fields(self, key):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        settings = QSettings()
        settings.beginGroup("/Discovery")

        if key:
            self.cboName.setText(key)
        else:
            self.cboName.setText("")

        data_type = settings.value(key + "data_type", "postgres")
        data_type_idx = self.cboDataSource.findData(data_type)
        self.cboDataSource.blockSignals(True)
        self.cboDataSource.setCurrentIndex(data_type_idx)
        self.cboDataSource.blockSignals(False)

        self.populate_connections()

        # tables
        self.init_combo_from_settings(self.cboTable, key + "table")
        self.populate_columns()

        # columns
        self.init_combo_from_settings(self.cboSearchColumn, key + "search_column")
        if data_type == "postgres" or data_type == "mssql":
            self.label_3.setText("Table")
            self.cboGeomColumn.setEnabled(True)
            self.init_combo_from_settings(self.cboGeomColumn, key + "geom_column")
        elif data_type == "gpkg":
            self.label_3.setText("Layer")
            self.cboGeomColumn.clear()
            self.cboGeomColumn.addItem("")
            self.cboGeomColumn.setEnabled(False)

        self.enable_fields_for_data_type()

        echo_search_col = settings.value(key + "echo_search_column", True, type=bool)
        self.cbEchoSearchColumn.setCheckState(Qt.Checked if echo_search_col else Qt.Unchecked)

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
        self.chkMarkerTime.setChecked(settings.value("marker_time_enabled", True, type=bool))
        self.spinMarkerTime.setValue(settings.value("marker_time", 5000, type=int) / 1000)
        self.time_checkbox_changed()

        QApplication.restoreOverrideCursor()

    def init_conn_schema_cbos(self, current_connections, key):
        all_cons = [self.cboConnection.itemText(i) for i in range(self.cboConnection.count())]
        self.cboConnection.clear()
        for conn in current_connections:
            if conn not in all_cons:
                self.cboConnection.addItem(conn)
        self.init_combo_from_settings(self.cboConnection, key + "connection")
        self.connect_db()
        # schemas
        self.init_combo_from_settings(self.cboSchema, key + "schema")
        self.populate_tables()

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
            data_type = self.cboDataSource.itemData(self.cboDataSource.currentIndex())
            if data_type == "postgres":
                self.conn = dbutils.get_connection(dbutils.get_postgres_conn_info(name))
            elif data_type == "mssql":
                self.conn = mssql_utils.get_mssql_conn(mssql_utils.get_mssql_conn_info(name))
            self.lblMessage.setText("")
        except Exception as e:
            self.conn = None
            self.lblMessage.setText("<font color=red>"+ str(e) +"</font>")
        self.populate_schemas()

    def populate_connections(self):
        key = self.cboName.text()
        data_type = self.cboDataSource.itemData(self.cboDataSource.currentIndex())
        if data_type == "postgres":
            current_connections = dbutils.get_postgres_connections()
            self.init_conn_schema_cbos(current_connections, key)
        elif data_type == "mssql":
            current_connections = mssql_utils.get_mssql_connections()
            self.init_conn_schema_cbos(current_connections, key)
        elif data_type == "gpkg":
            self.init_combo_from_settings(self.cboFile, key + "file")
            self.populate_tables()

    def populate_schemas(self):
        self.cboSchema.clear()
        self.cboSchema.addItem('')
        if self.conn is None: return

        data_type = self.cboDataSource.itemData(self.cboDataSource.currentIndex())
        if data_type == "postgres":
            schemas = dbutils.list_schemas(self.conn.cursor())
        elif data_type == "mssql":
            schemas = mssql_utils.list_schemas(self.conn)
        else:
            schemas = []
        for schema in schemas:
            self.cboSchema.addItem(schema)

    def populate_tables(self):
        self.cboTable.clear()
        self.cboTable.addItem('')
        data_type = self.cboDataSource.itemData(self.cboDataSource.currentIndex())
        if data_type == "postgres":
            if self.conn is None: return
            tables = dbutils.list_tables(self.conn.cursor(), self.cboSchema.currentText())
        elif data_type == "mssql":
            if self.conn is None: return
            tables = mssql_utils.list_tables(self.conn)  # TODO: filter by schema
        elif data_type == "gpkg":
            tables = gpkg_utils.list_gpkg_layers(self.cboFile.currentText())
        else:
            return   # current index == -1

        for table in tables:
            self.cboTable.addItem(table)

    def populate_columns(self):
        cbos = [self.cboSearchColumn, self.cboGeomColumn, self.cboDisplayColumn1, self.cboDisplayColumn2,
                self.cboDisplayColumn3, self.cboDisplayColumn4, self.cboDisplayColumn5]
        for cbo in cbos:
            cbo.clear()
            cbo.addItem("")

        data_type = self.cboDataSource.itemData(self.cboDataSource.currentIndex())
        if data_type == "postgres":
            if self.conn is None: return
            columns = dbutils.list_columns(self.conn.cursor(), self.cboSchema.currentText(), self.cboTable.currentText())
        elif data_type == "mssql":
            if self.conn is None: return
            columns = mssql_utils.list_columns(self.conn, self.cboSchema.currentText(), self.cboTable.currentText())
        elif data_type == "gpkg":
            columns = gpkg_utils.list_gpkg_fields(self.cboFile.currentText(), self.cboTable.currentText())
        else:
            return   # current index == -1

        for cbo in cbos:
            for column in columns:
                cbo.addItem(column)

    def enable_fields_for_data_type(self):
        data_type = self.cboDataSource.itemData(self.cboDataSource.currentIndex())
        is_db = data_type == "mssql" or data_type == "postgres"

        for w in [self.cboConnection, self.cboSchema, self.label, self.label_2]:
            w.setEnabled(is_db)
            w.setVisible(is_db)
        for w in [self.file_grid_layout, self.cboFile, self.label_10, self.fileButton]:
            w.setEnabled(not is_db)
            w.setVisible(not is_db)

    def validate_key(self, key, config_list):
        if not key: return False
        if self.key != key and key in config_list: return False

        return True

    def write_config(self):

        settings = QSettings()
        settings.beginGroup("/Discovery")

        config_list = settings.value("config_list")
        if not config_list:
            config_list = []

        key = self.cboName.text()
        if self.key != key:

            if not self.validate_key(key, config_list):
                return

            if self.key in config_list:
                config_list.remove(self.key)
            discoveryplugin.delete_config_from_settings(self.key, settings)
            self.key = key

        if key not in config_list:
            config_list.append(key)
            settings.setValue("config_list", config_list)

        settings.setValue(key + "data_type", self.cboDataSource.itemData(self.cboDataSource.currentIndex()))
        settings.setValue(key + "file", self.cboFile.currentText())
        settings.setValue(key + "connection", self.cboConnection.currentText())
        settings.setValue(key + "schema", self.cboSchema.currentText())
        settings.setValue(key + "table", self.cboTable.currentText())
        settings.setValue(key + "search_column", self.cboSearchColumn.currentText())
        settings.setValue(key + "echo_search_column", self.cbEchoSearchColumn.isChecked())
        settings.setValue(key + "display_columns", self.display_columns())
        settings.setValue(key + "geom_column", self.cboGeomColumn.currentText())
        settings.setValue(key + "scale_expr", self.editScaleExpr.text())
        settings.setValue(key + "bbox_expr", self.editBboxExpr.text())

        settings.setValue("marker_time_enabled", self.chkMarkerTime.isChecked())
        settings.setValue("marker_time", self.spinMarkerTime.value()*1000)

        self.configOptions.clear()
        for k in config_list:
            self.configOptions.addItem(k)

        index = self.configOptions.findText(key)
        if (index != -1):
            self.configOptions.setCurrentIndex(index)


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

    def enable_form(self, enable = True):
        # TODO put all to one widget and enable/disable only it
        self.cboName.setEnabled(enable)
        self.cboConnection.setEnabled(enable)
        self.cboSchema.setEnabled(enable)
        self.cboTable.setEnabled(enable)
        self.cboSearchColumn.setEnabled(enable)
        self.cbEchoSearchColumn.setEnabled(enable)
        self.cboDisplayColumn1.setEnabled(enable)
        self.cboDisplayColumn2.setEnabled(enable)
        self.cboDisplayColumn3.setEnabled(enable)
        self.cboDisplayColumn4.setEnabled(enable)
        self.cboDisplayColumn5.setEnabled(enable)
        self.cboGeomColumn.setEnabled(enable)
        self.editScaleExpr.setEnabled(enable)
        self.editBboxExpr.setEnabled(enable)
        self.chkMarkerTime.setEnabled(enable)
        self.spinMarkerTime.setEnabled(enable)

    def add_config(self):
        txt = ""
        self.configOptions.addItem(txt)
        self.configOptions.setCurrentIndex(self.configOptions.count() - 1)

        settings = QSettings()
        settings.beginGroup("/Discovery")
        config_list = settings.value("config_list")
        if not (config_list):
            config_list = []
            self.enable_form()
        config_list.append(txt)
        settings.setValue("config_list", config_list)

        # reset fields
        self.reset_form_fields()
        self.cboName.setText(txt)
        self.cboDataSource.setCurrentIndex(0)
        self.key = txt


    def delete_config(self):
        if self.configOptions.currentIndex() < 0: return

        msgBox = QMessageBox()
        msgBox.setWindowTitle("Delete configuration")
        msgBox.setText("Do you want to delete selected configuration?")
        msgBox.setStandardButtons(QMessageBox.Yes)
        msgBox.addButton(QMessageBox.No)
        msgBox.setDefaultButton(QMessageBox.No)
        if msgBox.exec_() == QMessageBox.No:
            return

        self.delete_config_without_confirm()

    def delete_config_without_confirm(self):
        item_text = self.configOptions.currentText()
        self.configOptions.removeItem(self.configOptions.currentIndex())
        settings = QSettings()
        settings.beginGroup("/Discovery")
        config_list = settings.value("config_list")
        config_list.remove(item_text)
        settings.setValue("config_list", config_list)
        if (self.configOptions.count()):
            self.configOptions.setCurrentIndex(0)
        else:
            self.reset_form_fields()
            self.enable_form(False)
            self.key = ""

    def config_selection_changed(self):
        if not self.configOptions.count(): return
        if self.configOptions.currentIndex() < 0: return

        self.key = self.configOptions.currentText()
        self.set_form_fields(self.key)

    def data_type_changed(self):
        self.populate_connections()
        self.enable_fields_for_data_type()

    def browse_file_db(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Open GeoPackage database')
        dialog.setNameFilters(['*.gpkg'])
        dialog.setFileMode(QFileDialog.ExistingFile)
        if dialog.exec_() == QDialog.Accepted:
            filename = dialog.selectedFiles()[0]
            if self.cboFile.findText(filename) < 0:
                self.cboFile.addItem(filename)
            self.cboFile.setCurrentIndex(self.cboFile.findText(filename))

    def show_help(self):
        QDesktopServices.openUrl(QUrl("http://www.lutraconsulting.co.uk/products/discovery/"))
