from osgeo import ogr, gdal
from qgis.core import QgsVectorLayer, QgsDataSourceUri, QgsFeatureRequest, QgsExpression
from qgis.PyQt.QtSql import QSqlDatabase, QSqlRecord

def list_gpkg_layers(pckg_path):
    layer_names = []
    ds = gdal.OpenEx(pckg_path)
    lyr_count = ds.GetLayerCount()
    for i in range(lyr_count):
        lyr = ds.GetLayer(i)
        if lyr.GetGeomType() == ogr.wkbNone:
            continue
        lyr_name = lyr.GetName()
        layer_names.append(lyr_name)
    ds = None
    return layer_names


def list_gpkg_fields(gpkg_path, name, bar_warning=None):
    try:
        layer = QgsVectorLayer(gpkg_path + '|layername=' + name, name, 'ogr')
        fields = layer.fields()
        columns=[]
        for f in fields:
            columns.append(f.name())
        return columns
    except RuntimeError as e:
        if bar_warning:
            bar_warning('Cannot read GeoPackage layer!')
        return []


def search_gpkg(search_text, search_field, display_fields, layer):
    expr_str = "{0} ILIKE '%{1}%'".format(search_field, search_text)
    expr = QgsExpression(expr_str)
    it = layer.getFeatures(QgsFeatureRequest(expr))
    result = []

    for f in it:
        featureInfo = []
        geom = f.geometry().asWkt()
        epsg = layer.crs().authid()
        featureInfo.append(geom)
        featureInfo.append(epsg)
        extra_info = []
        for fields in display_fields:
            extra_info.append(f[fields])
        featureInfo.append(extra_info)
        result.append(featureInfo)
    return result


# DEPRECATED
def get_search_sql():
    query = """SELECT
                GeomFromWKB(geom) AS geom,
                 "NAME1"
                                       || CASE WHEN "NAME1" IS NOT NULL THEN
                                                     ', ' || "NAME1"
                                                 ELSE
                                                     ''
                                                 END
                                            || CASE WHEN "COUNTRY" IS NOT NULL THEN
                                                     ', ' || "COUNTRY"
                                                 ELSE
                                                     ''
                                                 END
                                            AS suggestion_string 
                  FROM
                        test1
                     WHERE
                        "NAME1" LIKE
                     '%ROAD%'
                  ORDER BY
                        "NAME1"
                    LIMIT 10;"""
    return query, {}


def get_search_sql2(search_text, search_field, display_fields, gpkg_path):
    gpkg_dr = ogr.GetDriverByName( 'GPKG' )
    gpkg_ds = gpkg_dr.Open(gpkg_path, update=1)
    query = "SELECT {0} FROM test1 WHERE {0} LIKE '%{1}%';".format(search_field, search_text)
    print(query)
    result_set = gpkg_ds.ExecuteSQL(query)
    f = result_set.GetNextFeature()
    geom_read = f.GetGeometryRef()
    print(geom_read)

    # geom = ogr.CreateGeometryFromWkt('LINESTRING(5 5,10 5,10 10,5 10)')
    # feat = ogr.Feature(lyr.GetLayerDefn())
    # feat.SetGeometry(geom)

    gpkg_ds.ReleaseResultSet(result_set)
    pass


# TODO @vsklencar
def search_sqlite(search_text, search_field, display_fields, gpkg_path):
    print(search_sqlite)
    # Create DB connexion to do SQL
    db = QSqlDatabase.addDatabase("QSQLITE")
    # Reuse the path to DB to set database name
    db.setDatabaseName(gpkg_path)
    # Open the connection
    db.open()

    db.exec_("""SELECT load_extension('libspatialite-4.dll')""")
    geom_column = "geom"
    # query the table
    query_text = """ SELECT
                            name1, 
                            ST_AsText("%s") AS geom
                            FROM test1
                            LIMIT 10;
                     """ % (geom_column)
    print(query_text)
    query = db.exec_(query_text)
    print(query.lastError().text())

    if query.lastError().text():
        return []

    results = []
    while query.next():
        record = query.record()
        print(type(record))
        print(record)

        results.append(record.field('geom'))
        # for index in display_fields:
        #     # We exclude the geometry to join attributes data
        #     values.append(str(record.value(index)))
    print(results)
    return results


def spatialite_connect(path):
    import sqlite3
    print("spatialite_connect")
    con = sqlite3.connect(path)
    con.enable_load_extension(True)
    cur = con.cursor()
    libs = [
        # SpatiaLite >= 4.2 and Sqlite >= 3.7.17, should work on all platforms
        ("mod_spatialite", "sqlite3_modspatialite_init"),
        # SpatiaLite >= 4.2 and Sqlite < 3.7.17 (Travis)
        ("mod_spatialite.so", "sqlite3_modspatialite_init"),
        # SpatiaLite < 4.2 (linux)
        ("libspatialite.so", "sqlite3_extension_init")
        ]
    found = False
    for lib, entry_point in libs:
        try:
            print("lib trying " + str(lib))
            cur.execute("select load_extension('{}', '{}')".format(lib, entry_point))
        except sqlite3.OperationalError:
            continue
        else:
            found = True
            break
    if not found:
        raise RuntimeError("Cannot find any suitable spatialite module")
    cur.close()
    #con.enable_load_extension(False)
    return con

def spatialite_connect2(*args, **kwargs):
    """returns a dbapi2.Connection to a SpatiaLite db
using the "mod_spatialite" extension (python3)"""
    import sqlite3
    con = sqlite3.dbapi2.connect(*args, **kwargs)
    con.enable_load_extension(True)
    cur = con.cursor()
    libs = [
        # SpatiaLite >= 4.2 and Sqlite >= 3.7.17, should work on all platforms
        ("mod_spatialite", "sqlite3_modspatialite_init"),
        # SpatiaLite >= 4.2 and Sqlite < 3.7.17 (Travis)
        ("mod_spatialite.so", "sqlite3_modspatialite_init"),
        # SpatiaLite < 4.2 (linux)
        ("libspatialite.so", "sqlite3_extension_init")
    ]
    found = False
    for lib, entry_point in libs:
        try:
            cur.execute("select load_extension('{}', '{}')".format(lib, entry_point))
        except sqlite3.OperationalError:
            continue
        else:
            found = True
            break
    if not found:
        raise RuntimeError("Cannot find any suitable spatialite module")
    cur.close()
    con.enable_load_extension(False)
    return con




