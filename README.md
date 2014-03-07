#PostGIS Search Plugin For QGIS#
##Background##

This plugin is designed to enable fast autocomplete like searching on a PostGIS database.

It was considered there were two possible methods of giving the plugin as much flexbility as possible.

#Option 1: PostGIS Configuration File#
This option would use a PostGIS configuration file that the plugin would read on opening to get the correct database connection settings, including:
- Host
- Port
- Username
- Database name
- Database table
- Database schema
- Database column
- Search method

This would enable a much simple UI that would allow for straight forward autocomplete searching with results displaying in a table.

!(PostGIS_Search_Tool_Option1.png "Option 1: PostGIS Configuration File")