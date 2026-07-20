# -*- coding: utf-8 -*-
"""
Created on Thu May  2 08:22:14 2024

@author: Simon In-Albon

Program to create a Polygon of switzerland,
Raw Data from: https://www.swisstopo.admin.ch/de/landschaftsmodell-swissboundaries3d
Download the file: .gpkg
Place it in the working folder and name it: Swiss_Boundaries.gpkg
Let the program run
The Program creates an html file that shows a map with the created polygon
The program saves the polygon in a dataframe, .gpkg file that can later easy be used

"""


import geopandas as gpd
import shapely
import folium
import webbrowser
import os
import pandas as pd
from tqdm import tqdm

#%% import border and regional data of switzerland
# where is the file located? Input here
os.chdir('../02_Data')

df_Swiss = gpd.read_file('swiss_boundaries.gpkg')
df_Swiss.drop(columns=['uuid','datum_aenderung', 'datum_erstellung', 'erstellung_jahr',
       'erstellung_monat', 'grund_aenderung', 'herkunft', 'herkunft_jahr',
       'herkunft_monat', 'revision_jahr', 'revision_monat',
       'revision_qualitaet'], inplace=True)
df_Swiss.objektart = pd.to_numeric(df_Swiss.objektart)
df_border = df_Swiss[df_Swiss.objektart == 1]
df_border = df_border[df_border.icc != 'AT#LI']
df_border.typ = 'border'
df_border['Nr'] = df_border.index

## !!!!! Find all the borders that are inside switzerland!!! (done by hand - use map below:)
# explore_map = df_border.explore(legend=False)
# map_path = '/border_swiss.html'
# explore_map.save(map_path)
## open the map in a webbrowser
# webbrowser.open_new_tab('border_swiss.html')

df_border.loc[[5629, 6501, 3966, 1752, 3070],'typ'] = 5*['DE_enclave']
df_border.loc[[4707, 4650, 4741, 4706, 4707],'typ'] = 5*['IT_enclave']
df_outline_border = df_border[df_border.typ == 'border']

df_outline_border = df_outline_border.reset_index(drop = True)
df_outline_border['Nr'] = df_outline_border.index

#find all starting and ending points in the linestrings
lst_start = []
lst_end = []
for k in tqdm(range(len(df_outline_border))):
    lst_start.append(df_outline_border.loc[k, 'geometry'].coords[0])
    lst_end.append(df_outline_border.loc[k, 'geometry'].coords[-1])
df_outline_border['start'] = lst_start
df_outline_border['end'] = lst_end
df_outline_border['Nr_new'] = 0

#find the right order of all linestrings
prev_line = 0
current_line = 0
for j in tqdm(range(len(df_outline_border))):
    next_line = df_outline_border[df_outline_border.start == df_outline_border.end[current_line]].index
    # there is a possibility that a linestring is "the wrong way around"
    if len(next_line) == 0 or next_line==prev_line:
        lst_search = []
        # check if an end of an other linestring would fit to the current linestring end
        lst_search.extend(df_outline_border[df_outline_border.end == df_outline_border.end[current_line]].Nr)
        # drop all connections to the current line and the previous line
        lst_search = list(filter(lambda x: x not in [prev_line, current_line], lst_search))
        next_line= lst_search[0]
        # switch the orientation of the next linestring, such that the program goes the same direction from here on!
        new_start_list = df_outline_border.start.to_list()
        new_end_list = df_outline_border.end.to_list()
        new_start_list[next_line] = df_outline_border.loc[next_line, 'geometry'].coords[-1]
        new_end_list[next_line] = df_outline_border.loc[next_line, 'geometry'].coords[0]
        df_outline_border.start = new_start_list
        df_outline_border.end = new_end_list
        df_outline_border.loc[next_line, 'geometry'] = shapely.geometry.LineString(list(df_outline_border.loc[next_line, 'geometry'].coords)[::-1])
        
    else:
        next_line = next_line[0]
        
    df_outline_border.loc[next_line,'Nr_new'] = j+1
    prev_line = current_line
    current_line = next_line


df_outline_border.sort_values(by='Nr_new', inplace=True)
combined_coords = []
for linestring in df_outline_border.geometry.tolist():
    combined_coords.extend(linestring.coords)
combined_linestring = shapely.geometry.LineString(combined_coords)
combined_linestring = shapely.geometry.LineString([(x, y) for x, y, z in combined_linestring.coords])
points_list = [tuple(coord) for coord in combined_linestring.coords]
polygon = shapely.geometry.Polygon(points_list)
df_new = pd.DataFrame(columns=['Land', 'geometry'])
df_new.loc[0,'Land'] = 'Schweiz'
df_new['geometry'] = polygon
df_poly_swiss = gpd.GeoDataFrame(df_new, geometry=df_new.geometry, crs='EPSG:2056')
#create a map to check if the polygon is correct
explore_map = df_poly_swiss.explore(legend=False)
map_path = '../03_Results/RawData_Maps/df_poly_swiss.html'
explore_map.save(map_path)
#open the map in a webbrowser
os.chdir('../03_Results/RawData_Maps')
webbrowser.open_new_tab('df_poly_swiss.html')
os.chdir('../../02_Data')

#save the data of the polygon
df_poly_swiss.to_file('swiss_border_poly.gpkp', driver= 'GPKG')

exit







