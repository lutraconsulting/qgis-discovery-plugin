from osgeo import ogr, gdal
from qgis.core import QgsVectorLayer, QgsDataSourceUri
from qgis.PyQt.QtSql import QSqlDatabase

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


def get_search_sql(gpkg_path):
    gpkg_dr = ogr.GetDriverByName( 'GPKG' )
    gpkg_ds = gpkg_dr.Open(gpkg_path, update=1)
    result_set = gpkg_ds.ExecuteSQL("SELECT * FROM test1;")
    f = result_set.GetNextFeature()
    geom_read = f.GetGeometryRef()
    print(geom_read)

    # geom = ogr.CreateGeometryFromWkt('LINESTRING(5 5,10 5,10 10,5 10)')
    # feat = ogr.Feature(lyr.GetLayerDefn())
    # feat.SetGeometry(geom)

    gpkg_ds.ReleaseResultSet(result_set)
    pass

# TODO @vsklencar
def search_sqlite(path):
    # Get file path
    #pass
    #uri = QgsDataSourceUri(layer.dataProvider().dataSourceUri())
    # Create DB connexion to do SQL
    db = QSqlDatabase.addDatabase("QSQLITE");
    # Reuse the path to DB to set database name
    db.setDatabaseName(path)
    # Open the connection
    db.open()
    # query the table
    query = db.exec_("""select * from test1""")
    # Play with results (not efficient, just for demo)
    while query.next():
        values = []
        record = query.record()
        for index in range(record.count()):
            # We exclude the geometry to join attributes data
            values.append(str(record.value(index)))
        print (';').join(values)