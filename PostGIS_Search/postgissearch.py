# -*- coding: utf-8 -*-
"""
/***************************************************************************
 PostGISSearch
                                 A QGIS plugin
 Plugin for searching data in PostGIS Database
                              -------------------
        begin                : 2014-03-07
        copyright            : (C) 2014 by Tim Martin
        email                : tjmgis@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
# from qgis.core import *
# from PyQt4.QtSql import *
# Initialize Qt resources from file resources.py
# import resources
# Import the code for the dialog
# from postgissearchdialog import PostGISSearchDialog
import os.path
import psycopg2
from ConfigParser import SafeConfigParser

from qgis.core import *
from qgis.gui import *
from qgis.utils import *
from qgis.core import QgsGeometry  # , QgsPoint


class PostGISSearch:

    def __init__(self, _iface):
        # Save reference to the QGIS interface
        self.iface = _iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', 'postgissearch_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)

            if qVersion() > '4.3.3':
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
        self.query_sql = ''
        self.query_text = ''
        self.query_dict = {}
        self.db_idle_time = 60.0  # s

        self.search_results = []
        self.tool_bar = None
        self.search_line_edit = None
        self.completer = None

    def initGui(self):

        # Read config
        self.read_ini()

        # Create a new toolbar
        self.tool_bar = self.iface.addToolBar('PostGIS Search')

        # Add toolbar items
        self.tool_bar.addWidget(QLabel(' Search for '))
        self.search_line_edit = QLineEdit()
        self.search_line_edit.setMaximumWidth(512)
        self.tool_bar.addWidget(self.search_line_edit)

        # Set up the completer
        self.completer = QCompleter([])  # Initialise with en empty list
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setMaxVisibleItems(20)
        self.completer.setModelSorting(QCompleter.UnsortedModel)  # Sorting done in PostGIS
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)  # Show all fetched possibilities
        self.completer.activated[QModelIndex].connect(self.on_result_selected)
        self.completer.highlighted[QModelIndex].connect(self.on_result_highlighted)
        self.search_line_edit.setCompleter(self.completer)

        # Create action that will start plugin configuration
        # self.action = QAction(
        #     QIcon(":/plugins/postgissearch/postgissearch_logo.png"),
        #     u"PostGIS Search", self.iface.mainWindow())
        # connect the action to the run method
        # self.action.triggered.connect(self.run)
        # self.tool_bar.addAction(self.action)

        # Connect any signals
        self.search_line_edit.textEdited.connect(self.on_search_text_changed)

        # Add menu item
        # self.iface.addPluginToMenu(u"&PostGIS Search", self.action)

        # Search results
        self.search_results = []

        # Set up a timer to periodically perform db queries as required
        self.db_timer.timeout.connect(self.do_db_operations)
        self.db_timer.start(100)

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
        # Remove the plugin menu item and icon
        # self.iface.removePluginMenu(u"&PostGIS Search", self.action)
        # Remove the new toolbar
        self.tool_bar.clear()  # Clear all actions
        self.iface.mainWindow().removeToolBar(self.tool_bar)

    def clear_suggestions(self):
        model = self.completer.model()
        model.setStringList([])

    def on_search_text_changed(self, new_search_text):

        # This function is called whenever the user modified the search text

        self.query_text = new_search_text

        if len(new_search_text) < 3:
            # Clear any previous suggestions in case the user is 'backspacing'
            self.clear_suggestions()
            return

        """
            Open a database connection
            Make the query, getting:
                Joined columns (e.g. match in search column, county, country)
                Point geometry
                TODO: the bounding box grometry
            Update the QStringListModel with these results
            Store the other details in self.search_results

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
        for part in new_search_text.split():
            wildcarded_search_string += '%' + part
        wildcarded_search_string += '%'
        q_dic = {'search_text': wildcarded_search_string}
        query_text = """ SELECT
                            ST_AsText(geom) AS geom,
                            ST_SRID(geom) AS epsg,
                     """
        query_text += """"%s"
                      """ % self.postgissearchcolumn
        for display_column in self.postgisdisplaycolumn.split(','):
            query_text += """ || CASE WHEN "%s" IS NOT NULL THEN
                                    ', ' || "%s"
                                ELSE
                                    ''
                                END
                          """ % (display_column, display_column)
        query_text += """ AS suggestion_string
                      FROM
                            "%s"."%s"
                         WHERE
                            "%s" ILIKE
                      """ % (self.postgisschema, self.postgistable, self.postgissearchcolumn)
        query_text += """   %(search_text)s
                      """
        query_text += """ORDER BY
                            "%s"
                        LIMIT 20
                      """ % self.postgissearchcolumn

        self.schedule_search(query_text, q_dic)

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
        for geom, epsg, suggestion_text in cur.fetchall():
            self.search_results.append((geom, epsg))
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
        geometry_text, src_epsg = self.search_results[result_index.row()]
        location_geom = QgsGeometry.fromWkt(geometry_text)
        canvas = self.iface.mapCanvas()
        dst_srid = canvas.mapRenderer().destinationCrs().authid()
        transform = QgsCoordinateTransform(QgsCoordinateReferenceSystem(src_epsg),
                                           QgsCoordinateReferenceSystem(dst_srid))
        # Ensure the geometry from the DB is reprojected to the same SRID as the map canvas
        location_geom.transform(transform)
        location_centroid = location_geom.centroid().asPoint()

        # Adjust map canvas extent
        zoom_method = 'Move and Zoom'
        if zoom_method == 'Move and Zoom':
            scale = 250
            rect = QgsRectangle(location_centroid.x()-scale,
                                location_centroid.y()-scale,
                                location_centroid.x()+scale,
                                location_centroid.y()+scale)
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
            if len(self.postgisusername) == 0:
                self.db_conn = psycopg2.connect(database=self.postgisdatabase)
            else:
                self.db_conn = psycopg2.connect(database=self.postgisdatabase,
                                                user=self.postgisusername,
                                                password=self.postgispassword,
                                                host=self.postgishost,
                                                port=self.postgisport)
            self.db_conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        return self.db_conn.cursor()

    def read_ini(self):
        # the following code reads the configuration file which setups the plugin to search in the correct database,
        # table and method
        plugin_path = os.path.dirname(os.path.realpath(__file__))

        fname = os.path.join(plugin_path, "postgis.ini")

        if not os.path.exists(fname):
            iface.messageBar().pushMessage("Error", "No config file found", level=QgsMessageBar.CRITICAL, duration=5)
            return

        parser = SafeConfigParser()

        try:
            parser.read(fname)
            self.postgisdatabase = parser.get('postgis', 'postgisdatabase')
            self.postgisusername = parser.get('postgis', 'postgisusername')
            self.postgispassword = parser.get('postgis', 'postgispassword')
            self.postgishost = parser.get('postgis', 'postgishost')
            self.postgisport = parser.get('postgis', 'postgisport')
            self.postgisschema = parser.get('postgis', 'postgisschema')
            self.postgistable = parser.get('postgis', 'postgistable')
            self.postgissearchcolumn = parser.get('postgis', 'postgissearchcolumn')
            self.postgisdisplaycolumn = parser.get('postgis', 'postgisdisplaycolumn')
            self.postgisgeomname = parser.get('postgis', 'postgisgeomname')
            self.searchmethod = parser.get('postgis', 'searchmethod')
        except:
            iface.messageBar().pushMessage("Error", "Something wrong in the config file", level=QgsMessageBar.CRITICAL,
                                           duration=5)
            return

"""
    Original code, commented for the moment

    # run method that performs all the real work
    def run(self):
        self.read_ini()
        #declare the dlg
        self.dlg = PostGISSearchDialog()
        # show the dialog
        self.dlg.show()

        #Info box explaining the problems using SQL query.
        if self.searchmethod == "SQL":
            QMessageBox.warning(None, "Info", "Querying a large dataset by SQL search method may cause the search box to " +
                                              "become unresponsive. So type slowly and wait for results to appear. If " +
                                              "possible create a Full Text Search (FTS) column and change the search method.")

        #tie the line edit to the function
        self.dlg.ui.searchText.textChanged.connect(self.addPostGISLayer)

        # Run the dialog event loop
        result = self.dlg.exec_()


    #following function takes the contents of the line edit and uses it to query the declared database
    def addPostGISLayer(self, string):
        if (len(string) > 4) or (" " in string):
                uri = QgsDataSourceURI()
                # set host name, port, database name, username and password
                uri.setConnection(self.postgishost, self.postgisport, self.postgisdatabase, self.postgisusername,
                self.postgispassword)

               #need a different SQL query based on the search method declared in the postgis.ini file
                if self.searchmethod == 'SQL':
                    querystring = (string + "%")
                    sql = """"""SELECT %s, ST_X(%s) as x, ST_Y(%s) as y from %s.%s WHERE LOWER(%s) LIKE LOWER('%s')
                    LIMIT 100""""""%(self.postgisdisplaycolumn, self.postgisgeomname, self.postgisgeomname, self.postgisschema,
                    self.postgistable, self.postgissearchcolumn, querystring)

                elif self.searchmethod == 'FTS':
                    sql = """"""SELECT %s, ST_X(%s) as x, ST_Y(%s) as y FROM %s.%s WHERE %s @@ plainto_tsquery('english', '%s')
                    LIMIT 100""""""%(self.postgisdisplaycolumn, self.postgisgeomname, self.postgisgeomname, self.postgisschema,
                    self.postgistable, self.postgissearchcolumn, string)

                else:
                    iface.messageBar().pushMessage("Error", "Wrong search method declared in config file",
                                                   level=QgsMessageBar.CRITICAL, duration=5)

                #specify the type of database to query - in principla this could be changed to other databases
                self.db = QSqlDatabase.addDatabase('QPSQL')

                # check to see if it is valid
                if self.db.isValid():
                    self.db.setHostName(uri.host())
                    self.db.setDatabaseName(uri.database())
                    self.db.setPort(int(uri.port()))
                    self.db.setUserName(uri.username())
                    self.db.setPassword(uri.password())
                    # open (create) the connection
                    if self.db.open():
                        #setup model and run the query and then set the model to the results
                        self.projectModel = QSqlQueryModel()
                        self.projectModel.setQuery(sql,self.db)
                        self.dlg.ui.tableView.setModel(self.projectModel)
                        #close connection to database
                        self.db.close()
                        self.db.removeDatabase('QPSQL')
                        #tweak the table based on the results
                        self.dlg.ui.tableView.resizeColumnsToContents()
                        #tie table to function for adding point to map canvas
                        self.dlg.ui.tableView.selectionModel().currentChanged.connect(self.cellClicked)

    #the following function runs when the user clicks a row of the search results
    def cellClicked(self):
        iface.mapCanvas().refresh()

        #get the selected row from table view
        if self.dlg.ui.tableView.currentIndex():
            index = self.dlg.ui.tableView.currentIndex().row()

            # need just one attribute for the label, this will be the first attribute if more than one is returned by the
            # SQL query

            if "," in self.postgisdisplaycolumn:
                labelcolumn = self.postgisdisplaycolumn.split(",")[0]
            else:
                labelcolumn = self.postgisdisplaycolumn

            #setup the x and y variables which are used to create a memory point on the map canvas
            self.x = self.projectModel.record(index).value("x")
            self.y = self.projectModel.record(index).value("y")
            self.label = str(self.projectModel.record(index).value(labelcolumn))

        canvas = self.iface.mapCanvas()
        dest_crs = canvas.mapRenderer().destinationCrs()

        #create memory layer for the new point
        self.pinLayer =  QgsVectorLayer("Point?&field=Description:string(120)&field=X_Coordinate:double&field=Y_Coordinate:" +
                                         double&index=yes", self.label, "memory")
        self.provider = self.pinLayer.dataProvider()
        QgsMapLayerRegistry.instance().addMapLayer(self.pinLayer)

        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPoint(QgsPoint(self.x,self.y)))
        #depending on the version of QGIS adding the feature to the memory layer is different
        if QGis.QGIS_VERSION_INT > 10800:
            feature.setAttributes([self.label, self.x, self.y])
            self.pinLayer.startEditing()
            self.pinLayer.addFeature(feature, True)
            self.pinLayer.commitChanges()
        else:
            feature.setAttributeMap( {0 : QVariant(self.description),
                1 : QVariant(self.x),
                2 : QVariant(self.y)})
            self.provider.addFeatures([feature])
            self.pinLayer.updateExtents()

        #based on the feature move and scale the map accodingly
        scale = 1200
        rect = QgsRectangle(float(self.x)-scale,float(self.y)-scale,float(self.x)+scale,float(self.y)+scale)
        canvas.setExtent(rect)
        canvas.refresh()

        #close the dialogue do user can see map automcatically
        self.dlg.close()
"""


if __name__ == "__main__":
    pass
