# Discovery Plugin
#
# Copyright (C) 2020 Lutra Consulting
# info@lutraconsulting.co.uk
#
# Thanks to Tim Martin of Ordnance Survey for his original PostGIS Search
# plugin which inspired and formed the foundation of Discovery.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

import os.path
import time

import psycopg2
from PyQt5.QtCore import QCoreApplication, QModelIndex, QSettings, Qt, QTimer, QTranslator, QVariant
from PyQt5.QtGui import QColor, QIcon
from PyQt5.QtWidgets import QAction, QApplication, QComboBox, QCompleter, QMessageBox
from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsExpression,
    QgsExpressionContext,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsRectangle,
    QgsSettings,
    QgsVectorLayer,
    QgsWkbTypes,
)
from qgis.gui import QgsFilterLineEdit, QgsRubberBand, QgsVertexMarker
from qgis.utils import iface

from Discovery import gpkg_utils, mssql_utils, oracle_utils

from . import config_dialog, dbutils, locator_filter


def eval_expression(expr_text, extra_data, default=None):
    """Helper method to evaluate an expression. E.g.
    eval_expression("1+a", {"a": 2}) will return 3
    """
    if expr_text is None or len(expr_text) == 0:
        return default

    flds = QgsFields()
    for extra_col, extra_value in extra_data.items():
        if isinstance(extra_value, int):
            t = QVariant.Int
        elif isinstance(extra_value, float):
            t = QVariant.Double
        else:
            t = QVariant.String
        flds.append(QgsField(extra_col, t))
    f = QgsFeature(flds)
    for extra_col, extra_value in extra_data.items():
        f[extra_col] = extra_value
    expr = QgsExpression(expr_text)
    ctx = QgsExpressionContext()
    ctx.setFeature(f)
    res = expr.evaluate(ctx)
    return default if expr.hasEvalError() else res


def bbox_str_to_rectangle(bbox_str):
    """Helper method to convert "xmin,ymin,xmax,ymax" to QgsRectangle - or return None on error"""
    if bbox_str is None or len(bbox_str) == 0:
        return None

    coords = bbox_str.split(",")
    if len(coords) != 4:
        return None

    try:
        xmin = float(coords[0])
        ymin = float(coords[1])
        xmax = float(coords[2])
        ymax = float(coords[3])
        return QgsRectangle(xmin, ymin, xmax, ymax)
    except ValueError:
        return None


def delete_config_from_settings(key, settings):
    settings.remove(key + "data_type")
    settings.remove(key + "file")
    settings.remove(key + "connection")
    settings.remove(key + "schema")
    settings.remove(key + "table")
    settings.remove(key + "search_column")
    settings.remove(key + "escape_spec_chars")
    settings.remove(key + "echo_search_column")
    settings.remove(key + "display_columns")
    settings.remove(key + "geom_column")
    settings.remove(key + "scale_expr")
    settings.remove(key + "bbox_expr")


class DiscoveryPlugin:

    def __init__(self, _iface):
        # Save reference to the QGIS interface
        self.iface = _iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Localize
        locale = QSettings().value("locale/userLocale")[0:2]
        localePath = os.path.join(self.plugin_dir, "i18n", "discovery_{}.qm".format(locale))
        if os.path.exists(localePath):
            self.translator = QTranslator()
            self.translator.load(localePath)
            QCoreApplication.installTranslator(self.translator)

        # Variables to facilitate delayed queries and database connection management
        self.db_timer = QTimer()
        self.line_edit_timer = QTimer()
        self.line_edit_timer.setSingleShot(True)
        self.line_edit_timer.timeout.connect(self.reset_line_edit_after_move)
        self.next_query_time = None
        self.last_query_time = time.time()
        self.db_conn = None
        self.search_delay = 0.5  # s
        self.query_sql = ""
        self.query_text = ""
        self.query_dict = {}
        self.db_idle_time = 60.0  # s
        self.display_time = 5000  # ms
        self.bar_info_time = 30  # s

        self.search_results = []
        self.limit_results = 1000
        self.tool_bar = None
        self.search_line_edit = None
        self.completer = None
        self.conn_info = {}

        self.marker = QgsVertexMarker(iface.mapCanvas())
        self.marker.setIconSize(15)
        self.marker.setPenWidth(2)
        self.marker.setColor(QColor(226, 27, 28))  # 51,160,44))
        self.marker.setZValue(11)
        self.marker.setVisible(False)
        self.marker2 = QgsVertexMarker(iface.mapCanvas())
        self.marker2.setIconSize(16)
        self.marker2.setPenWidth(4)
        self.marker2.setColor(QColor(255, 255, 255, 200))
        self.marker2.setZValue(10)
        self.marker2.setVisible(False)
        self.is_displayed = False

        self.rubber_band = QgsRubberBand(iface.mapCanvas(), QgsWkbTypes.PolygonGeometry)
        self.rubber_band.setVisible(False)
        self.rubber_band.setWidth(3)
        self.rubber_band.setStrokeColor(QColor(226, 27, 28))
        self.rubber_band.setFillColor(QColor(226, 27, 28, 63))

    def initGui(self):

        # Create a new toolbar
        self.tool_bar = self.iface.addToolBar("Discovery")
        self.tool_bar.setObjectName("Discovery_Plugin")

        # Create action that will start plugin configuration
        self.action_config = QAction(
            QIcon(os.path.join(self.plugin_dir, "discovery_logo.png")), "Configure Discovery", self.tool_bar
        )
        self.action_config.triggered.connect(self.show_config_dialog)
        self.tool_bar.addAction(self.action_config)

        # Add combobox for configs
        self.config_combo = QComboBox()
        settings = QgsSettings()
        settings.beginGroup("/Discovery")
        config_list = settings.value("config_list")

        if config_list:
            for conf in config_list:
                self.config_combo.addItem(conf)
        elif settings.childGroups():
            # support for prev version
            key = "Config1"
            config_list = []
            config_list.append(key)
            settings.setValue("config_list", config_list)
            self.config_combo.addItem(key)

            settings.setValue(key + "data_type", settings.value("data_type"))
            settings.setValue(key + "file", settings.value("file"))
            settings.setValue(key + "connection", settings.value("connection"))
            settings.setValue(key + "schema", settings.value("schema"))
            settings.setValue(key + "table", settings.value("table"))
            settings.setValue(key + "search_column", settings.value("search_column"))
            settings.setValue(key + "escape_spec_chars", settings.value("escape_spec_chars"))
            settings.setValue(key + "echo_search_column", settings.value("echo_search_column"))
            settings.setValue(key + "display_columns", settings.value("display_columns"))
            settings.setValue(key + "geom_column", settings.value("geom_column"))
            settings.setValue(key + "scale_expr", settings.value("scale_expr"))
            settings.setValue(key + "bbox_expr", settings.value("bbox_expr"))

            delete_config_from_settings("", settings)
        self.tool_bar.addWidget(self.config_combo)

        # Add search edit box
        self.search_line_edit = QgsFilterLineEdit()
        self.search_line_edit.setPlaceholderText("Search for...")
        self.search_line_edit.setMaximumWidth(768)
        self.tool_bar.addWidget(self.search_line_edit)

        self.config_combo.currentIndexChanged.connect(self.change_configuration)

        # Set up the completer
        self.completer = QCompleter([])  # Initialise with en empty list
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setMaxVisibleItems(1000)
        self.completer.setModelSorting(QCompleter.UnsortedModel)  # Sorting done in PostGIS
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)  # Show all fetched possibilities
        self.completer.activated[QModelIndex].connect(self.on_result_selected)
        self.completer.highlighted[QModelIndex].connect(self.on_result_highlighted)
        self.search_line_edit.setCompleter(self.completer)

        # Connect any signals
        self.search_line_edit.textEdited.connect(self.on_search_text_changed)

        # Search results
        self.search_results = []

        # Set up a timer to periodically perform db queries as required
        self.db_timer.timeout.connect(self.do_db_operations)
        self.db_timer.start(100)

        # Read config
        self.read_config(config_list[0] if config_list else "")

        self.locator_filter = locator_filter.DiscoveryLocatorFilter(self)
        self.iface.registerLocatorFilter(self.locator_filter)

        # Debug
        # import pydevd; pydevd.settrace('localhost', port=5678)

    def unload(self):
        # Stop timer
        self.db_timer.stop()
        # Disconnect any signals
        self.db_timer.timeout.disconnect(self.do_db_operations)
        self.completer.highlighted[QModelIndex].disconnect(self.on_result_highlighted)
        self.completer.activated[QModelIndex].disconnect(self.on_result_selected)
        self.search_line_edit.textEdited.disconnect(self.on_search_text_changed)
        # Remove the new toolbar
        self.tool_bar.clear()  # Clear all actions
        self.iface.mainWindow().removeToolBar(self.tool_bar)

        self.iface.deregisterLocatorFilter(self.locator_filter)
        self.locator_filter = None

    def clear_suggestions(self):
        model = self.completer.model()
        model.setStringList([])

    def on_search_text_changed(self, new_search_text):
        """
        This function is called whenever the user modified the search text

        1. Open a database connection
        2. Make the query
        3. Update the QStringListModel with these results
        4. Store the other details in self.search_results
        """

        self.query_text = new_search_text

        if len(new_search_text) < 3:
            # Clear any previous suggestions in case the user is 'backspacing'
            self.clear_suggestions()
            return

        if self.data_type == "postgres":
            query_text, query_dict = dbutils.get_search_sql(
                new_search_text,
                self.postgisgeomcolumn,
                self.postgissearchcolumn,
                self.echosearchcolumn,
                self.postgisdisplaycolumn,
                self.extra_expr_columns,
                self.postgisschema,
                self.postgistable,
                self.escapespecchars,
                self.limit_results,
            )
            self.schedule_search(query_text, query_dict)

        elif self.data_type == "gpkg":
            query_text = (
                new_search_text,
                self.postgissearchcolumn,
                self.echosearchcolumn,
                self.postgisdisplaycolumn.split(","),
                self.extra_expr_columns,
                self.layer,
                self.limit_results,
            )
            self.schedule_search(query_text, None)

        elif self.data_type == "mssql":
            query_text = mssql_utils.get_search_sql(
                new_search_text,
                self.postgisgeomcolumn,
                self.postgissearchcolumn,
                self.echosearchcolumn,
                self.postgisdisplaycolumn,
                self.extra_expr_columns,
                self.postgisschema,
                self.postgistable,
                self.limit_results,
            )
            self.schedule_search(query_text, None)

        elif self.data_type == "oracle":
            query_text = oracle_utils.get_search_sql(
                new_search_text,
                self.postgisgeomcolumn,
                self.postgissearchcolumn,
                self.echosearchcolumn,
                self.postgisdisplaycolumn,
                self.extra_expr_columns,
                self.postgisschema,
                self.postgistable,
                self.limit_results,
            )
            self.schedule_search(query_text, None)

    def do_db_operations(self):
        if self.next_query_time is not None and self.next_query_time < time.time():
            # It's time to run a query
            self.next_query_time = None  # Prevent this query from being repeated
            self.last_query_time = time.time()
            self.perform_search()
        else:
            # We're not performing a query, close the db connection if it's been open for > 60s
            if time.time() > self.last_query_time + self.db_idle_time:
                self.db_conn = None

    def perform_search(self):
        db = self.get_db()
        if db is None and self.data_type != "gpkg":
            return

        self.search_results = []
        suggestions = []
        if self.data_type == "postgres":
            cur = db.cursor()
            try:
                cur.execute(self.query_sql, self.query_dict)
            except psycopg2.Error as e:
                err_info = "Failed to execute the search query. Please, check your settings. Error message:\n\n"
                err_info += "{}".format(e.pgerror)
                QMessageBox.critical(None, "Discovery", err_info)
                return
            result_set = cur.fetchall()
        elif self.data_type == "mssql":
            result_set = mssql_utils.execute(db, self.query_sql)
        elif self.data_type == "oracle":
            result_set = oracle_utils.execute(db, self.query_sql)
        elif self.data_type == "gpkg":
            result_set = gpkg_utils.search_gpkg(*self.query_sql)

        for row in result_set:
            geom, epsg, suggestion_text = row[0], row[1], row[2]
            extra_data = {}
            for idx, extra_col in enumerate(self.extra_expr_columns):
                extra_data[extra_col] = row[3 + idx]
            self.search_results.append((geom, epsg, suggestion_text, extra_data))
            suggestions.append(suggestion_text)
        model = self.completer.model()
        model.setStringList(suggestions)
        self.completer.complete()

    def schedule_search(self, query_text, query_dict):
        # Update the search text and the time after which the query should be executed
        self.query_sql = query_text
        self.query_dict = query_dict
        self.next_query_time = time.time() + self.search_delay

    def show_bar_info(self, info_text):
        """Optional show info bar message with selected result information"""
        self.iface.messageBar().clearWidgets()
        if self.bar_info_time:
            self.iface.messageBar().pushMessage("Discovery", info_text, level=Qgis.Info, duration=self.bar_info_time)

    def on_result_selected(self, result_index):
        # What to do when the user makes a selection
        self.select_result(self.search_results[result_index.row()])

    def select_result(self, result_data):
        geometry_text, src_epsg, suggestion_text, extra_data = result_data
        location_geom = QgsGeometry.fromWkt(geometry_text)
        location_geom_type = location_geom.type()
        if location_geom_type in {QgsWkbTypes.UnknownGeometry, QgsWkbTypes.NullGeometry}:
            # Unknown geometry or no geometry at all
            pass
        else:
            canvas = self.iface.mapCanvas()
            dst_srid = canvas.mapSettings().destinationCrs().authid()
            transform = QgsCoordinateTransform(
                QgsCoordinateReferenceSystem.fromEpsgId(int(src_epsg)),
                QgsCoordinateReferenceSystem(dst_srid),
                canvas.mapSettings().transformContext(),
            )
            # Ensure the geometry from the DB is reprojected to the same SRID as the map canvas
            location_geom.transform(transform)
            location_centroid = location_geom.centroid().asPoint()

            # show temporary marker
            if location_geom_type == QgsWkbTypes.PointGeometry:
                self.show_marker(location_centroid)
            elif location_geom_type == QgsWkbTypes.LineGeometry or location_geom_type == QgsWkbTypes.PolygonGeometry:
                self.show_line_rubber_band(location_geom)
            else:
                # unsupported geometry type
                pass

            # Adjust map canvas extent
            zoom_method = "Move and Zoom"
            if zoom_method == "Move and Zoom":
                # with higher priority try to use exact bounding box to zoom to features (if provided)
                bbox_str = eval_expression(self.bbox_expr, extra_data)
                rect = bbox_str_to_rectangle(bbox_str)
                if rect is not None:
                    # transform the rectangle in case of OTF projection
                    rect = transform.transformBoundingBox(rect)
                else:
                    # bbox is not available - so let's just use defined scale
                    # compute target scale. If the result is 2000 this means the target scale is 1:2000
                    rect = location_geom.boundingBox()
                    if rect.isEmpty():
                        scale_denom = eval_expression(self.scale_expr, extra_data, default=2000.0)
                        rect = canvas.mapSettings().extent()
                        rect.scale(scale_denom / canvas.scale(), location_centroid)
                    else:
                        # enlarge geom bbox to have some margin
                        rect.scale(1.2)
                canvas.setExtent(rect)
            elif zoom_method == "Move":
                current_extent = QgsGeometry.fromRect(self.iface.mapCanvas().extent())
                dx = location_centroid.x() - location_centroid.x()
                dy = location_centroid.y() - location_centroid.y()
                current_extent.translate(dx, dy)
                canvas.setExtent(current_extent.boundingBox())
            canvas.refresh()
        self.line_edit_timer.start(0)
        if self.info_to_clipboard:
            QApplication.clipboard().setText(suggestion_text)
            suggestion_text += " (copied to clipboard)"
        self.show_bar_info(suggestion_text)

    def on_result_highlighted(self, result_idx):
        self.line_edit_timer.start(0)

    def reset_line_edit_after_move(self):
        self.search_line_edit.setText(self.query_text)

    def get_db(self):
        # Create a new connection if required
        QApplication.setOverrideCursor(Qt.WaitCursor)
        if self.db_conn is None:
            if self.data_type == "postgres":
                try:
                    self.db_conn = dbutils.get_connection(self.conn_info)
                except psycopg2.Error as e:
                    err_info = "Failed to connect to the server. Error message:\n\n"
                    err_info += f"{e.pgerror} - {e}"
                    QMessageBox.critical(None, "Discovery", err_info)
                    QApplication.restoreOverrideCursor()
                    return
            elif self.data_type == "mssql":
                self.db_conn = mssql_utils.get_mssql_conn(self.conn_info)
            elif self.data_type == "oracle":
                self.db_conn = oracle_utils.get_oracle_conn(self.conn_info)
        QApplication.restoreOverrideCursor()
        return self.db_conn

    def change_configuration(self):
        self.search_line_edit.setText("")
        self.line_edit_timer.start(0)
        self.read_config(self.config_combo.currentText())

    def read_config(self, key=""):
        # the following code reads the configuration file which setups the plugin to search in the correct database,
        # table and method

        settings = QgsSettings()
        settings.beginGroup("/Discovery")

        connection = settings.value(key + "connection", "", type=str)
        self.data_type = settings.value(key + "data_type", "", type=str)
        self.file = settings.value(key + "file", "", type=str)
        self.postgisschema = settings.value(key + "schema", "", type=str)
        self.postgistable = settings.value(key + "table", "", type=str)
        self.postgissearchcolumn = settings.value(key + "search_column", "", type=str)
        self.escapespecchars = settings.value(key + "escape_spec_chars", False, type=bool)
        self.echosearchcolumn = settings.value(key + "echo_search_column", True, type=bool)
        self.postgisdisplaycolumn = settings.value(key + "display_columns", "", type=str)
        self.postgisgeomcolumn = settings.value(key + "geom_column", "", type=str)
        if settings.value("marker_time_enabled", True, type=bool):
            self.display_time = settings.value("marker_time", 5000, type=int)
        else:
            self.display_time = -1
        if settings.value("bar_info_time_enabled", True, type=bool):
            self.bar_info_time = settings.value("bar_info_time", 30, type=int)
        else:
            self.bar_info_time = 0
        self.limit_results = settings.value(key + "limit_results", 1000, type=int)
        self.info_to_clipboard = settings.value("info_to_clipboard", True, type=bool)

        scale_expr = settings.value(key + "scale_expr", "", type=str)
        bbox_expr = settings.value(key + "bbox_expr", "", type=str)

        m_color = QColor()
        m_color_name = settings.value(key + "highlight_color", "#e21b1c", type=str)
        m_color.setNamedColor(m_color_name)
        self.marker.setColor(m_color)
        self.rubber_band.setStrokeColor(m_color)
        f_color = m_color
        f_color.setAlpha(63)
        self.rubber_band.setFillColor(f_color)

        if self.is_displayed:
            self.hide_marker()
            self.hide_rubber_band()
            self.is_displayed = False

        self.make_enabled(False)  # assume the config is invalid first

        self.db_conn = None
        if self.data_type == "postgres":
            self.conn_info = dbutils.get_postgres_conn_info(connection)
            self.layer = None

            if (
                len(connection) == 0
                or len(self.postgisschema) == 0
                or len(self.postgistable) == 0
                or len(self.postgissearchcolumn) == 0
                or len(self.postgisgeomcolumn) == 0
            ):
                return

            if len(self.conn_info) == 0:
                iface.messageBar().pushMessage(
                    "Discovery", "The database connection '%s' does not exist!" % connection, level=Qgis.Critical
                )
                return
        elif self.data_type == "mssql":
            self.conn_info = mssql_utils.get_mssql_conn_info(connection)
            self.layer = None

            if (
                len(connection) == 0
                or len(self.postgisschema) == 0
                or len(self.postgistable) == 0
                or len(self.postgissearchcolumn) == 0
                or len(self.postgisgeomcolumn) == 0
            ):
                return

            if len(self.conn_info) == 0:
                iface.messageBar().pushMessage(
                    "Discovery", "The database connection '%s' does not exist!" % connection, level=Qgis.Critical
                )
                return
        elif self.data_type == "oracle":
            self.conn_info = oracle_utils.get_oracle_conn_info(connection)
            self.layer = None

            if (
                len(connection) == 0
                or len(self.postgisschema) == 0
                or len(self.postgistable) == 0
                or len(self.postgissearchcolumn) == 0
                or len(self.postgisgeomcolumn) == 0
            ):
                return

            if len(self.conn_info) == 0:
                iface.messageBar().pushMessage(
                    "Discovery", "The database connection '%s' does not exist!" % connection, level=Qgis.Critical
                )
                return
        elif self.data_type == "gpkg":
            self.layer = QgsVectorLayer(self.file + "|layername=" + self.postgistable, self.postgistable, "ogr")
            self.conn_info = None
        self.extra_expr_columns = []
        self.scale_expr = None
        self.bbox_expr = None

        self.make_enabled(True)

        # optional scale expression when zooming in to results
        if len(scale_expr) != 0:
            expr = QgsExpression(scale_expr)
            if expr.hasParserError():
                iface.messageBar().pushMessage(
                    "Discovery", "Invalid scale expression: " + expr.parserErrorString(), level=Qgis.Warning
                )
            else:
                self.scale_expr = scale_expr
                self.extra_expr_columns += expr.referencedColumns()

        # optional bbox expression when zooming in to results
        if len(bbox_expr) != 0:
            expr = QgsExpression(bbox_expr)
            if expr.hasParserError():
                iface.messageBar().pushMessage(
                    "Discovery", "Invalid bbox expression: " + expr.parserErrorString(), level=Qgis.Warning
                )
            else:
                self.bbox_expr = bbox_expr
                self.extra_expr_columns += expr.referencedColumns()

    def show_config_dialog(self):
        dlg = config_dialog.ConfigDialog()
        if self.config_combo.currentIndex() >= 0:
            dlg.configOptions.setCurrentIndex(self.config_combo.currentIndex())

        if dlg.exec_():
            dlg.write_config()
            self.config_combo.clear()
            for key in [dlg.configOptions.itemText(i) for i in range(dlg.configOptions.count())]:
                self.config_combo.addItem(key)

            self.config_combo.setCurrentIndex(dlg.configOptions.currentIndex())
            self.change_configuration()

    def make_enabled(self, enabled):
        self.search_line_edit.setEnabled(enabled)
        self.search_line_edit.setPlaceholderText("Search for..." if enabled else "Search disabled: check configuration")

    def show_marker(self, point):
        for m in [self.marker, self.marker2]:
            m.setCenter(point)
            m.setOpacity(1.0)
            m.setVisible(True)
        if self.display_time == -1:
            self.is_displayed = True
        else:
            QTimer.singleShot(self.display_time, self.hide_marker)

    def hide_marker(self):
        opacity = self.marker.opacity()
        if opacity > 0.0:
            # produce a fade out effect
            opacity -= 0.1
            self.marker.setOpacity(opacity)
            self.marker2.setOpacity(opacity)
            QTimer.singleShot(100, self.hide_marker)
        else:
            self.marker.setVisible(False)
            self.marker2.setVisible(False)

    def show_line_rubber_band(self, geom):
        self.rubber_band.reset(geom.type())
        self.rubber_band.setToGeometry(geom, None)
        self.rubber_band.setVisible(True)
        self.rubber_band.setOpacity(1.0)
        self.rubber_band.show()
        if self.display_time == -1:
            self.is_displayed = True
        else:
            QTimer.singleShot(self.display_time, self.hide_rubber_band)
        pass

    def hide_rubber_band(self):
        opacity = self.rubber_band.opacity()
        if opacity > 0.0:
            # produce a fade out effect
            opacity -= 0.1
            self.rubber_band.setOpacity(opacity)
            QTimer.singleShot(100, self.hide_rubber_band)
        else:
            self.rubber_band.setVisible(False)
            self.rubber_band.hide()
