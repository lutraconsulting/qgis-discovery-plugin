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
from qgis.core import *
from PyQt4.QtSql import *
# Initialize Qt resources from file resources.py
import resources_rc
# Import the code for the dialog
from postgissearchdialog import PostGISSearchDialog
import os.path
from ConfigParser import SafeConfigParser

from qgis.core import *
from qgis.gui import *
from qgis.utils import *
from qgis.core import QgsGeometry, QgsPoint


class PostGISSearch:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value("locale/userLocale")[0:2]
        localePath = os.path.join(self.plugin_dir, 'i18n', 'postgissearch_{}.qm'.format(locale))

        if os.path.exists(localePath):
            self.translator = QTranslator()
            self.translator.load(localePath)

            if qVersion() > '4.3.3':
                QCoreApplication.installTranslator(self.translator)

        plugin_path = os.path.dirname(os.path.realpath(__file__))


        fname = os.path.join(plugin_path, "postgis.ini")

        if os.path.exists(fname):
            pass

        else:
            iface.messageBar().pushMessage("Error", "No config file found", level=QgsMessageBar.CRITICAL, duration=5)


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
            iface.messageBar().pushMessage("Error", "Something wrong in the config file", level=QgsMessageBar.CRITICAL, duration=5)
        # Create the dialog (after translation) and keep reference
        self.dlg = PostGISSearchDialog()

        #self.connect(self.dlg.self.searchText, SIGNAL("triggered()"), self.addPostGISLayer)
        self.dlg.searchText.textChanged.connect(self.addPostGISLayer)

    def initGui(self):
        # Create action that will start plugin configuration
        self.action = QAction(
            QIcon(":/plugins/postgissearch/icon.png"),
            u"PostGIS Search", self.iface.mainWindow())
        # connect the action to the run method
        self.action.triggered.connect(self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(u"&PostGIS Search", self.action)

    def unload(self):
        # Remove the plugin menu item and icon
        self.iface.removePluginMenu(u"&PostGIS Search", self.action)
        self.iface.removeToolBarIcon(self.action)

    def cellClicked(self):

        index = self.dlg.tableView.currentIndex()

        rownumber = index.row()

        hmodel = self.dlg.tableView.horizontalHeader().model()
        for column in range(hmodel.columnCount()):
            if hmodel.headerData(column, Qt.Horizontal) == "x":
                xcolumn = column

            elif hmodel.headerData(column, Qt.Horizontal) == "y":
                ycolumn = column

            elif hmodel.headerData(column, Qt.Horizontal) == self.postgisdisplaycolumn:
                descriptioncolumn = column

        x = self.projectModel.index(rownumber, xcolumn).data()
        y = self.projectModel.index(rownumber, ycolumn).data()
        description = self.projectModel.index(rownumber, descriptioncolumn).data()

        layer =  QgsVectorLayer("Point",description,"memory")
        QgsMapLayerRegistry.instance().addMapLayer(layer)
        feature = QgsFeature()
        feature.setGeometry( QgsGeometry.fromPoint(QgsPoint(x,y)) )

        layer.startEditing()
        layer.addFeature(feature, True)
        layer.commitChanges()

        iface.mapCanvas().setExtent(QgsRectangle(x,y,x,y))
        iface.mapCanvas().zoomScale(10000)
        iface.mapCanvas().refresh()

        self.dlg.searchText.setText("")

        self.projectModel.clear()

        self.dlg.tableView.clearSelection()

        self.dlg.close()


    def addPostGISLayer(self, string):
        if len(string) > 4:
            uri = QgsDataSourceURI()
            # set host name, port, database name, username and password
            uri.setConnection(self.postgishost, self.postgisport, self.postgisdatabase, self.postgisusername, self.postgispassword)
            # set database schema, table name, geometry column and optionaly
            # subset (WHERE clause)
            if self.searchmethod == 'SQL':
                querystring = ("%" + string + "%")
                sql = "select %s.*, ST_X(%s) as x, ST_Y(%s) as y from %s.%s WHERE LOWER(%s) LIKE LOWER('%s') LIMIT 1000"%(self.postgistable, self.postgisgeomname, self.postgisgeomname, self.postgisschema, self.postgistable, self.postgissearchcolumn, querystring)

            elif self.searchmethod == 'FTS':
                sql = """SELECT %s.*, ST_X(%s) as x, ST_Y(%s) as y FROM %s.%s WHERE %s @@ plainto_tsquery('english', '%s') LIMIT 100"""%(self.postgistable, self.postgisgeomname, self.postgisgeomname, self.postgisschema, self.postgistable, self.postgissearchcolumn, string)

            else:
                iface.messageBar().pushMessage("Error", "Wrong search method declared in config file", level=QgsMessageBar.CRITICAL, duration=5)

            db = QSqlDatabase.addDatabase('QPSQL')
            # check to see if it is valid
            if db.isValid():
                iface.messageBar().pushMessage("Info", "Successfully connected to database", level=QgsMessageBar.INFO, duration=3)
                db.setHostName(uri.host())
                db.setDatabaseName(uri.database())
                db.setPort(int(uri.port()))
                db.setUserName(uri.username())
                db.setPassword(uri.password())
                # open (create) the connection
                if db.open():
                    self.projectModel = QSqlQueryModel()
                    self.projectModel.setQuery(sql,db)
                    self.dlg.tableView.setModel(self.projectModel)
                    self.dlg.tableView.resizeColumnsToContents()
                    self.dlg.tableView.selectionModel().currentChanged.connect(self.cellClicked)
                    self.dlg.tableView.clicked.connect(self.cellClicked)
                else:
                    iface.messageBar().pushMessage("Error", "Cannot open search on the database", level=QgsMessageBar.CRITICAL, duration=5)

            else:
                iface.messageBar().pushMessage("Error", "DB not valid", level=QgsMessageBar.CRITICAL, duration=5)

    # run method that performs all the real work
    def run(self):
        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result == 1:
            # do something useful (delete the line containing pass and
            # substitute with your code)
            pass