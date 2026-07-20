# -*- coding: utf-8 -*-
"""
Created on Wed Jun 25 16:29:13 2025

@author: simon
"""

import geopandas as gpd
import pandas as pd
import shapely
from tqdm import tqdm
from explore_map import map_plotter
from data_worker import find_data_path
orig_path = 'C:/Users/username/Hochschule Luzern/CC TES - Dokumente/Projekte/11.51.00278.00_SWEET_Pathfndr/07_WPs/WP3/08_GIS_Analysis/02_Data/'
data_path = find_data_path(orig_path)
del orig_path

#%% user input
map_path = '../03_Results/RawData_Maps/'
additional_data_path = 'placement_data/'

file = 'traffArea'
check_column = 'objektart'
values = ['Oeffentliches Parkplatzareal', 'Privates Parkplatzareal']

#%%
file_name = data_path+additional_data_path+file+'.parquet'
save_name = data_path+additional_data_path+file+'_new.parquet'
df_place_raw = pd.read_parquet(file_name)


#%% add the new column
# new_column = 'pathfndr_02'
# df_place_raw[new_column] = 0
# df_place_raw.loc[df_place_raw[check_column].isin(values), new_column] = 1


#%% combine two values to one in a new column
new_value = 'Parkplatz'
new_column_name = check_column + '_combined'

# Copy original column and apply mapping
df_place_raw[new_column_name] = df_place_raw[check_column].copy()
df_place_raw.loc[df_place_raw[check_column].isin(values), new_column_name] = new_value



#%% convert geometry to readable shapely geometries
df_place_raw['geometry'] = df_place_raw['geometry'].apply(shapely.wkb.loads)  
df_place_raw = gpd.GeoDataFrame(data=df_place_raw, geometry=df_place_raw['geometry'], crs= "EPSG:2056" )
df_place_raw.to_parquet(save_name)




#%% Remove Z from PolygonZ if needed

from shapely.geometry import Polygon, MultiPolygon
from shapely.geometry import mapping, shape

def drop_z(geom):
    if geom is None:
        return None
    geom_mapping = mapping(geom)
    
    def remove_z(coords):
        return [(x, y) for x, y, *_ in coords]
    
    if geom_mapping['type'] == 'Polygon':
        exterior = remove_z(geom_mapping['coordinates'][0])
        interiors = [remove_z(ring) for ring in geom_mapping['coordinates'][1:]]
        return Polygon(exterior, interiors)
    
    elif geom_mapping['type'] == 'MultiPolygon':
        polygons = []
        for poly_coords in geom_mapping['coordinates']:
            exterior = remove_z(poly_coords[0])
            interiors = [remove_z(ring) for ring in poly_coords[1:]]
            polygons.append(Polygon(exterior, interiors))
        return MultiPolygon(polygons)
    
    else:
        return geom  # Leave other geometries unchanged (like Point, LineString if present)

df_place_raw['geometry'] = df_place_raw['geometry'].apply(drop_z)
df_place_raw.to_parquet(save_name)



