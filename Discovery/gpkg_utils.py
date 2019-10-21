from osgeo import ogr, gdal
from qgis.core import QgsVectorLayer, QgsDataSourceUri, QgsFeatureRequest, QgsExpression

import os
import sys
plugin_dir = os.path.dirname(__file__)
sys.path.insert(0,plugin_dir)
from natsort import natsorted

def list_gpkg_layers(pckg_path):
    if not pckg_path: return []

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


def search_gpkg(search_text, search_field, echo_search_column, display_fields, extra_expr_columns, 
                layer, comparison_mode, case_sensitivity):
    search_string = ''
    if comparison_mode == 'contains':
        for part in search_text.split():
            search_string += '%' + part
        search_string += '%'
        if case_sensitivity:
            expr_str = "{0} LIKE '{1}'".format(search_field, search_string)
        else:
            expr_str = "{0} ILIKE '{1}'".format(search_field, search_string)
    elif comparison_mode == 'begins_with':
        search_string += search_text + '%' 
        if case_sensitivity:
            expr_str = "{0} LIKE '{1}'".format(search_field, search_string)
        else:
            expr_str = "{0} ILIKE '{1}'".format(search_field, search_string)
    elif comparison_mode == 'exact_match':
        search_string += search_text
        if case_sensitivity:
            expr_str = "{0} LIKE '{1}'".format(search_field, search_string)
        else:
            expr_str = "{0} ILIKE '{1}'".format(search_field, search_string)

    expr = QgsExpression(expr_str)
    it = layer.getFeatures(QgsFeatureRequest(expr))
    result = []

    for f in it:
        feature_info = []
        geom = f.geometry().asWkt()
        epsg = layer.crs().authid()
        feature_info.append(geom)
        feature_info.append(epsg)
        available_fields = [field.name() for field in f.fields()]

        display_info = []
        if echo_search_column:
            display_info.append(str(f[search_field]))
        for field_name in display_fields:
            if field_name in available_fields:
                display_info.append(str(f[field_name]))
        feature_info.append(", ".join(display_info))

        for field_name in extra_expr_columns:
            if field_name in available_fields:
                feature_info.append(f[field_name])
            else:
                feature_info.append("")
        result.append(feature_info)
# natural sorting of results
    for f in result:
        f.insert(0,f[2])

    sorted_result = natsorted(result)

    for f in sorted_result:
        f.pop(0)

    return sorted_result
