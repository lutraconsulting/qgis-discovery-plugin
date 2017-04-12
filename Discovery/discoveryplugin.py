# -*- coding: utf-8 -*-

# Discovery Plugin
#
# Copyright (C) 2015 Lutra Consulting
# info@lutraconsulting.co.uk
#
# Thanks to Tim Martin of Ordnance Survey for his original PostGIS Search
# plugin which inspired and formed the foundation of Discovery.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import uic

import time
import types
import os.path
import psycopg2

from qgis.core import *
from qgis.gui import *
from qgis.utils import iface

import config_dialog
import dbutils


def eval_expression(expr_text, extra_data, default=None):
    """ Helper method to evaluate an expression. E.g.
         eval_expression("1+a", {"a": 2}) will return 3
    """
    if expr_text is None or len(expr_text) == 0:
        return default

    flds = QgsFields()
    for extra_col, extra_value in extra_data.iteritems():
        if isinstance(extra_value, types.IntType):
            t = QVariant.Int
        elif isinstance(extra_value, types.FloatType):
            t = QVariant.Double
        else:
            t = QVariant.String
        flds.append(QgsField(extra_col, t))
    f = QgsFeature(flds)
    for extra_col, extra_value in extra_data.iteritems():
        f[extra_col] = extra_value
    expr = QgsExpression(expr_text)
    res = expr.evaluate(f)
    return default if expr.hasEvalError() else res


def bbox_str_to_rectangle(bbox_str):
    """ Helper method to convert "xmin,ymin,xmax,ymax" to QgsRectangle - or return None on error
    """
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


class DiscoveryPlugin:

    def __init__(self, _iface):
        # Save reference to the QGIS interface
        self.iface = _iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)

        # Variables to facilitate delayed queries and database connection management
        self.db_timer = QTimer()
        self.line_edit_timer = QTimer()
        self.line_edit_timer.setSingleShot(True)
        self.line_edit_timer.timeout.connect(self.reset_line_edit_after_move)
        self.next_query_time = None
        self.last_query_time = time.time()
        self.db_conn = None
        self.search_delay = 0.5  # s
        self.query_sql = ''
        self.query_text = ''
        self.query_dict = {}
        self.db_idle_time = 60.0  # s

        self.search_results = []
        self.tool_bar = None
        self.search_line_edit = None
        self.completer = None
        self.conn_info = {}

        self.marker = QgsVertexMarker(iface.mapCanvas())
        self.marker.setIconSize(15)
        self.marker.setPenWidth(2)
        self.marker.setColor(QColor(226,27,28)) #51,160,44))
        self.marker.setZValue(11)
        self.marker.setVisible(False)
        self.marker2 = QgsVertexMarker(iface.mapCanvas())
        self.marker2.setIconSize(16)
        self.marker2.setPenWidth(4)
        self.marker2.setColor(QColor(255,255,255,200))
        self.marker2.setZValue(10)
        self.marker2.setVisible(False)
        self.display_time = settings.value("display_time", "", type=int)
        self.is_displayed = False


    def initGui(self):

        # Create a new toolbar
        self.tool_bar = self.iface.addToolBar('Discovery')
        self.tool_bar.setObjectName('Discovery_Plugin')

        # Create action that will start plugin configuration
        self.action_config = QAction(
             QIcon(os.path.join(self.plugin_dir, "discovery_logo.png")),
             u"Configure Discovery", self.tool_bar)
        self.action_config.triggered.connect(self.show_config_dialog)
        self.tool_bar.addAction(self.action_config)

        # Add search edit box
        self.search_line_edit = QgsFilterLineEdit()
        self.search_line_edit.setPlaceholderText('Search for...')
        self.search_line_edit.setMaximumWidth(768)
        self.tool_bar.addWidget(self.search_line_edit)

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
        self.read_config()

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

        query_text, query_dict = dbutils.get_search_sql(
                                    new_search_text,
                                    self.postgisgeomcolumn,
                                    self.postgissearchcolumn,
                                    self.echosearchcolumn,
                                    self.postgisdisplaycolumn,
                                    self.extra_expr_columns,
                                    self.postgisschema,
                                    self.postgistable)

        self.schedule_search(query_text, query_dict)

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

        cur = self.get_db_cur()
        cur.execute(self.query_sql, self.query_dict)

        self.search_results = []
        suggestions = []
        for row in cur.fetchall():
            geom, epsg, suggestion_text = row[0], row[1], row[2]
            extra_data = {}
            for idx, extra_col in enumerate(self.extra_expr_columns):
                extra_data[extra_col] = row[3+idx]
            self.search_results.append((geom, epsg, extra_data))
            suggestions.append(suggestion_text)

        model = self.completer.model()
        model.setStringList(suggestions)
        self.completer.complete()

    def schedule_search(self, query_text, query_dict):
        # Update the search text and the time after which the query should be executed
        self.query_sql = query_text
        self.query_dict = query_dict
        self.next_query_time = time.time() + self.search_delay

    def on_result_selected(self, result_index):
        # What to do when the user makes a selection
        geometry_text, src_epsg, extra_data = self.search_results[result_index.row()]
        location_geom = QgsGeometry.fromWkt(geometry_text)
        canvas = self.iface.mapCanvas()
        dst_srid = canvas.mapRenderer().destinationCrs().authid()
        transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem(src_epsg),
                                           QgsCoordinateReferenceSystem(dst_srid))
        # Ensure the geometry from the DB is reprojected to the same SRID as the map canvas
        location_geom.transform(transform)
        location_centroid = location_geom.centroid().asPoint()

        # show temporary marker
        self.show_marker(location_centroid)

        # Adjust map canvas extent
        zoom_method = 'Move and Zoom'
        if zoom_method == 'Move and Zoom':
            # with higher priority try to use exact bounding box to zoom to features (if provided)
            bbox_str = eval_expression(self.bbox_expr, extra_data)
            rect = bbox_str_to_rectangle(bbox_str)
            if rect is not None:
                # transform the rectangle in case of OTF projection
                rect = transform.transformBoundingBox(rect)
            else:
                # bbox is not available - so let's just use defined scale
                # compute target scale. If the result is 2000 this means the target scale is 1:2000
                scale_denom = eval_expression(self.scale_expr, extra_data, default=2000.)
                rect = canvas.mapSettings().extent()
                rect.scale(scale_denom / canvas.scale(), location_centroid)
            canvas.setExtent(rect)
        elif zoom_method == 'Move':
            current_extent = QgsGeometry.fromRect(self.iface.mapCanvas().extent())
            dx = location_centroid.x() - location_centroid.x()
            dy = location_centroid.y() - location_centroid.y()
            current_extent.translate(dx, dy)
            canvas.setExtent(current_extent.boundingBox())
        canvas.refresh()
        self.line_edit_timer.start(0)

    def on_result_highlighted(self, result_idx):
        self.line_edit_timer.start(0)

    def reset_line_edit_after_move(self):
        self.search_line_edit.setText(self.query_text)

    def get_db_cur(self):
        # Create a new new connection if required
        if self.db_conn is None:
            self.db_conn = dbutils.get_connection(self.conn_info)
        return self.db_conn.cursor()

    def read_config(self):
        # the following code reads the configuration file which setups the plugin to search in the correct database,
        # table and method

        settings = QSettings()
        settings.beginGroup("/Discovery")
        connection = settings.value("connection", "", type=str)
        self.postgisschema = settings.value("schema", "", type=str)
        self.postgistable = settings.value("table", "", type=str)
        self.postgissearchcolumn = settings.value("search_column", "", type=str)
        self.echosearchcolumn = settings.value("echo_search_column", True, type=bool)
        self.postgisdisplaycolumn = settings.value("display_columns", "", type=str)
        self.postgisgeomcolumn = settings.value("geom_column", "", type=str)
        self.dont_hide_marker = settings.value("timer_checked", "", type=bool)
        if not self.dont_hide_marker:
        	self.display_time = settings.value("display_time", "", type=int)

        scale_expr = settings.value("scale_expr", "", type=str)
        bbox_expr = settings.value("bbox_expr", "", type=str)

        if self.is_displayed:
            self.hide_marker()
            self.is_displayed = False

        self.make_enabled(False)   # assume the config is invalid first
        self.db_conn = None
        self.conn_info = dbutils.get_postgres_conn_info(connection)
        self.extra_expr_columns = []
        self.scale_expr = None
        self.bbox_expr = None

        if len(connection) == 0 or len(self.postgisschema) == 0 or len(self.postgistable) == 0 or \
           len(self.postgissearchcolumn) == 0 or len(self.postgisgeomcolumn) == 0:
            #iface.messageBar().pushMessage("Discovery", "Please configure the plugin", level=QgsMessageBar.INFO)
            return

        if len(self.conn_info) == 0:
            iface.messageBar().pushMessage("Discovery", "The database connection '%s' does not exist!" % connection,
                                           level=QgsMessageBar.CRITICAL)
            return

        self.make_enabled(True)

        # optional scale expression when zooming in to results
        if len(scale_expr) != 0:
            expr = QgsExpression(scale_expr)
            if expr.hasParserError():
                iface.messageBar().pushMessage("Discovery", "Invalid scale expression: " + expr.parserErrorString(),
                                               level=QgsMessageBar.WARNING)
            else:
                self.scale_expr = scale_expr
                self.extra_expr_columns += expr.referencedColumns()

        # optional bbox expression when zooming in to results
        if len(bbox_expr) != 0:
            expr = QgsExpression(bbox_expr)
            if expr.hasParserError():
                iface.messageBar().pushMessage("Discovery", "Invalid bbox expression: " + expr.parserErrorString(),
                                               level=QgsMessageBar.WARNING)
            else:
                self.bbox_expr = bbox_expr
                self.extra_expr_columns += expr.referencedColumns()


    def show_config_dialog(self):

        dlg = config_dialog.ConfigDialog()
        if dlg.exec_():
            dlg.write_config()
            self.read_config()

    def make_enabled(self, enabled):
        self.search_line_edit.setEnabled(enabled)
        self.search_line_edit.setPlaceholderText("Search for..." if enabled else "Search disabled: check configuration")

    def show_marker(self, point):
        for m in [self.marker, self.marker2]:
            m.setCenter(point)
            m.setOpacity(1.0)
            m.setVisible(True)
        if self.dont_hide_marker:
        	self.is_displayed = True
        else:
        	QTimer.singleShot(self.display_time, self.hide_marker)

    def hide_marker(self):
        opacity = self.marker.opacity()
        if opacity > 0.:
            # produce a fade out effect
            opacity -= 0.1
            self.marker.setOpacity(opacity)
            self.marker2.setOpacity(opacity)
            QTimer.singleShot(100, self.hide_marker)
        else:
            self.marker.setVisible(False)
            self.marker2.setVisible(False)
