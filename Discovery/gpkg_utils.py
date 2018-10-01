from osgeo import ogr, gdal
from qgis.core import QgsVectorLayer

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