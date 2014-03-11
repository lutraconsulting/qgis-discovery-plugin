# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui_postgissearch.ui'
#
# Created: Fri Mar 07 17:53:28 2014
#      by: PyQt4 UI code generator 4.10.3
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    def _fromUtf8(s):
        return s

try:
    _encoding = QtGui.QApplication.UnicodeUTF8
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig, _encoding)
except AttributeError:
    def _translate(context, text, disambig):
        return QtGui.QApplication.translate(context, text, disambig)

class Ui_PostGISSearch(object):
    def setupUi(self, PostGISSearch):
        PostGISSearch.setObjectName(_fromUtf8("PostGISSearch"))
        PostGISSearch.resize(577, 458)
        self.searchText = QtGui.QLineEdit(PostGISSearch)
        self.searchText.setGeometry(QtCore.QRect(220, 60, 251, 20))
        self.searchText.setObjectName(_fromUtf8("searchText"))
        self.title = QtGui.QLabel(PostGISSearch)
        self.title.setGeometry(QtCore.QRect(210, 20, 141, 16))
        font = QtGui.QFont()
        font.setPointSize(15)
        self.title.setFont(font)
        self.title.setObjectName(_fromUtf8("title"))
        self.title_2 = QtGui.QLabel(PostGISSearch)
        self.title_2.setGeometry(QtCore.QRect(100, 60, 111, 16))
        font = QtGui.QFont()
        font.setPointSize(15)
        self.title_2.setFont(font)
        self.title_2.setObjectName(_fromUtf8("title_2"))
        # self.tableWidget = QtGui.QTableWidget(PostGISSearch)
        # self.tableWidget.setGeometry(QtCore.QRect(20, 120, 531, 291))
        # self.tableWidget.setObjectName(_fromUtf8("tableWidget"))
        # self.tableWidget.setColumnCount(0)
        # self.tableWidget.setRowCount(0)
        self.tableView = QtGui.QTableView(PostGISSearch)
        self.tableView.setGeometry(QtCore.QRect(20, 120, 531, 291))
        self.tableView.setSelectionMode(QtGui.QTableView.SingleSelection)
        self.tableView.setSelectionBehavior(QtGui.QTableView.SelectRows)
        self.tableView.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)
<<<<<<< HEAD
        self.tableView.setAlternatingRowColors(True)
        self.tableView.horizontalHeader().setStretchLastSection(True)
=======
>>>>>>> 16ee3d1452f9b6ae6ebbf1f03620b1d71d0e468d
        self.resultsLabel = QtGui.QLabel(PostGISSearch)
        self.resultsLabel.setGeometry(QtCore.QRect(20, 100, 46, 13))
        self.resultsLabel.setObjectName(_fromUtf8("resultsLabel"))
        self.closeButton = QtGui.QPushButton(PostGISSearch)
        self.closeButton.setGeometry(QtCore.QRect(490, 420, 75, 23))
        self.closeButton.setObjectName(_fromUtf8("closeButton"))

        self.retranslateUi(PostGISSearch)
        QtCore.QObject.connect(self.closeButton, QtCore.SIGNAL(_fromUtf8("pressed()")), PostGISSearch.reject)
        QtCore.QMetaObject.connectSlotsByName(PostGISSearch)

    def retranslateUi(self, PostGISSearch):
        PostGISSearch.setWindowTitle(_translate("PostGISSearch", "PostGISSearch", None))
        self.title.setText(_translate("PostGISSearch", "PostGIS Search", None))
        self.title_2.setText(_translate("PostGISSearch", "Search Text:", None))
        self.resultsLabel.setText(_translate("PostGISSearch", "Results", None))
        self.closeButton.setText(_translate("PostGISSearch", "Close", None))

