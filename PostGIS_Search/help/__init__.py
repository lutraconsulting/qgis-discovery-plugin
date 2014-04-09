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
 This script initializes the plugin, making it known to QGIS.
"""

def classFactory(iface):
    # load PostGISSearch class from file PostGISSearch
    from postgissearch import PostGISSearch
    return PostGISSearch(iface)
