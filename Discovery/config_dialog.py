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
from enum import Enum
from Discovery import gpkg_utils
from . import dbutils
from . import discoveryplugin

plugin_dir = os.path.dirname(__file__)

uiConfigDialog, qtBaseClass = uic.loadUiType(os.path.join(plugin_dir, 'config_dialog.ui'))

class DataType(Enum):
    POSTGRES = 0
    GPKG = 1

class ConfigDialog(qtBaseClass, uiConfigDialog):

    def __init__(self, parent=None):
        qtBaseClass.__init__(self, parent)
        self.setupUi(self)

        self.conn = None
        self.key = ""  # currently selected config key
        self.data_type=DataType.POSTGRES.value # TODO/ change default

        # signals
        self.buttonBox.button(QDialogButtonBox.Help).clicked.connect(self.show_help)
        self.addButton.clicked.connect(self.add_config)
        self.deleteButton.clicked.connect(self.delete_config)
        self.configOptions.currentIndexChanged.connect(self.config_selection_changed)
        self.cboName.textChanged.connect(self.validate_nameField)
        self.fileButton.clicked.connect(self.browse_file_db)
        self.cboFile.currentIndexChanged.connect(self.populate_gpkg_tables)

        self.postgresButton.toggled.connect(self.data_type_changed)

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

        self.cboConnection.addItem("")

        for key in config_list:
            self.configOptions.addItem(key)

        if self.configOptions.count():
            self.configOptions.setCurrentIndex(0)

        self.key = self.configOptions.currentText() if self.configOptions.currentIndex() >= 0 else ""

        if not self.configOptions.count():
            self.enable_form(False)

        self.set_form_fields(self.key)
        self.chkMarkerTime.stateChanged.connect(self.time_checkbox_changed)

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

    def set_form_fields(self, key = ""):

        QApplication.setOverrideCursor(Qt.WaitCursor)
        settings = QSettings()
        settings.beginGroup("/Discovery")

        if key:
            self.cboName.setText(key)
        else:
            self.cboName.setText("")

        #self.data_type = settings.value(key + "data_type", DataType.POSTGRES.value)
        if str(self.data_type) == str(DataType.POSTGRES.value):
            # data type button
            self.postgresButton.setChecked(True)

            # connections
            all_cons = [self.cboConnection.itemText(i) for i in range(self.cboConnection.count())]
            for conn in dbutils.get_postgres_connections():
                if conn not in all_cons:
                    self.cboConnection.addItem(conn)
            self.init_combo_from_settings(self.cboConnection, key + "connection")
            self.cboConnection.currentIndexChanged.connect(self.connect_db)
            self.connect_db()
            # schemas
            self.init_combo_from_settings(self.cboSchema, key + "schema")
            self.cboSchema.currentIndexChanged.connect(self.populate_tables)
            self.populate_tables()
        elif str(self.data_type) == str(DataType.GPKG.value):
            # data type button
            self.geopackageButton.setChecked(True)

            # db file
            self.init_combo_from_settings(self.cboFile, key + "file")
            self.cboFile.currentIndexChanged.connect(self.populate_tables)
            self.populate_tables()
        # tables
        self.init_combo_from_settings(self.cboTable, key + "table")
        self.cboTable.currentIndexChanged.connect(self.populate_columns)
        self.populate_columns()
        # columns
        self.init_combo_from_settings(self.cboSearchColumn, key + "search_column")
        if str(self.data_type) == DataType.POSTGRES.value:
            self.cboGeomColumn.setEnabled(True)
            self.init_combo_from_settings(self.cboGeomColumn, key + "geom_column")
        elif str(self.data_type) == str(DataType.GPKG.value):
            self.cboGeomColumn.clear()
            self.cboGeomColumn.addItem("")
            self.cboGeomColumn.setEnabled(False)

        self.setup_form()

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
        self.chkMarkerTime.setChecked(settings.value("marker_time_enabled", True, type=bool))
        self.spinMarkerTime.setValue(settings.value("marker_time", 5000, type=int) / 1000)
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
        except Exception as e:
            self.conn = None
            self.lblMessage.setText("<font color=red>"+ str(e.args) +"</font>")
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
        if str(self.data_type) == str(DataType.POSTGRES.value):
            if self.conn is None: return
            tables = dbutils.list_tables(self.conn.cursor(), self.cboSchema.currentText())
        elif str(self.data_type) == str(DataType.GPKG.value):
            tables = gpkg_utils.list_gpkg_layers(self.cboFile.currentText())
        else:
            tables = []
        print("set tables " + str(tables))
        for table in tables:
            self.cboTable.addItem(table)

    def populate_columns(self):
        cbos = [self.cboSearchColumn, self.cboGeomColumn, self.cboDisplayColumn1, self.cboDisplayColumn2,
                self.cboDisplayColumn3, self.cboDisplayColumn4, self.cboDisplayColumn5]
        for cbo in cbos:
            cbo.clear()
            cbo.addItem("")

        if str(self.data_type) == str(DataType.GPKG.value):
            columns = gpkg_utils.list_gpkg_fields(self.cboFile.currentText(), self.cboTable.currentText())
        elif str(self.data_type) == str(DataType.POSTGRES.value):
            if self.conn is None: return
            columns = dbutils.list_columns(self.conn.cursor(), self.cboSchema.currentText(), self.cboTable.currentText())
        else:
            columns=[]
        print("set columns ")
        for cbo in cbos:
            for column in columns:
                cbo.addItem(column)

    def setup_form(self):
        widgets = {DataType.POSTGRES.value: [self.cboConnection, self.cboSchema, self.label, self.label_2],
                    DataType.GPKG.value: [self.cboFile, self.label_10, self.fileButton]}
        for type in widgets.keys():
            for w in widgets[type]:
                w.setEnabled(int(type) == int(self.data_type))
                w.setVisible(int(type) == int(self.data_type))

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

        # TODO case for data_type
        settings.setValue(key + "data_type", self.get_data_type())
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
        self.set_form_fields()
        self.cboName.setText(txt)
        self.postgresButton.setChecked(True)
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
            self.set_form_fields("")
            self.enable_form(False)
            self.key = ""

    def config_selection_changed(self):
        if not self.configOptions.count(): return
        if self.configOptions.currentIndex() < 0: return

        self.key = self.configOptions.currentText()
        self.set_form_fields(self.key)

    def data_type_changed(self):
        print('data_type_changed')
        if self.postgresButton.isChecked():
            self.data_type = DataType.POSTGRES.value
        elif self.geopackageButton.isChecked():
            self.data_type = DataType.GPKG.value
        else:
            self.data_type = DataType.POSTGRES.value

        self.config_selection_changed()

    def browse_file_db(self):
        dialog = QFileDialog(self)
        dialog.setWindowTitle('Open Geopackage/Spatialite')
        dialog.setNameFilters(['*.gpkg','*.sqlite'])
        dialog.setFileMode(QFileDialog.ExistingFile)
        if dialog.exec_() == QDialog.Accepted:
            filename = dialog.selectedFiles()[0]
            if self.cboFile.findText(filename) < 0:
                self.cboFile.addItem(filename)
            self.cboFile.setCurrentIndex(self.cboFile.findText(filename))

    def get_data_type(self):
        if self.postgresButton.isChecked():
            return DataType.POSTGRES.value
        else:
            return DataType.GPKG.value

    # VECTOR LAYER

    # WORKING WITH GEOPACKAGE
    def populate_gpkg_tables(self):
        path = self.cboFile.currentText()
        layer_names = gpkg_utils.list_gpkg_layers(path)
        self.cboTable.clear()
        self.cboTable.addItem('')
        for gpkg_layer in layer_names:
            self.cboTable.addItem(gpkg_layer)


    def show_help(self):
        QDesktopServices.openUrl(QUrl("http://www.lutraconsulting.co.uk/products/discovery/"))
