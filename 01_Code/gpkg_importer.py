# -*- coding: utf-8 -*-
"""
Created on Tue Jul  9 13:43:05 2024

gpkg-Importer

@author: Simon In-Albon
"""
import geopandas as gpd
import shapely
import folium
import webbrowser
import os
import pandas as pd
import numpy as np
import time
import sys
import csv
import math
import matplotlib.pyplot as plt
from tqdm import tqdm

from data_worker import convert_series_elements, str_to_list

import importlib, gpkg_importer
importlib.reload(gpkg_importer)

#%% function to extract coordinates from multipoints

def extract_coordinates(multipoint):
    x_coords = [point.x for point in multipoint.geoms]
    y_coords = [point.y for point in multipoint.geoms]
    return x_coords, y_coords

#%%
def gpkg_importer(dic_gpkg, lst_import, path):
    """
    Import raw .gpkg data listed in lst_import using dic_gpkg mapping.
    Returns a list of GeoDataFrames in the same order as lst_import.
    """
    lst_df_raw = []
    for key in tqdm(lst_import):
        # check that the dataset is defined
        if key not in dic_gpkg:
            print('*********************************************************************')
            print(f'WARNING: The raw data of <<{key}>> is not defined in <<dic_gpkg_data>>!\nSYSTEM FAILURE')
            print('*********************************************************************')
            lst_df_raw.append(pd.DataFrame())
            continue

        # import data
        file_path = os.path.join(path, dic_gpkg[key])
        gdf = gpd.read_file(file_path)

        # add a unique object ID
        id_numbers = list(range(len(gdf)))
        gdf['obj_ID'] = [f'{key}_' + str(number) for number in id_numbers]
        gdf.set_index('obj_ID', inplace=True)

        # extract coordinates depending on geometry type
        geom0 = gdf.geometry.iloc[0]
        if isinstance(geom0, shapely.geometry.point.Point):
            gdf['x'] = gdf.geometry.x
            gdf['y'] = gdf.geometry.y

        elif isinstance(geom0, shapely.geometry.multipoint.MultiPoint):
            # keep x/y as LISTS (one list per row)
            xy_lists = gdf.geometry.apply(extract_coordinates)  # -> (xs, ys)
            gdf['x'] = xy_lists.apply(lambda t: t[0])
            gdf['y'] = xy_lists.apply(lambda t: t[1])

        elif isinstance(geom0, shapely.geometry.polygon.Polygon):
            # centroid coordinates
            gdf['x'] = gdf.geometry.centroid.x
            gdf['y'] = gdf.geometry.centroid.y

        elif isinstance(geom0, shapely.geometry.linestring.LineString):
            # no default x/y extraction for lines
            pass

        else:
            print('*********************************************************************')
            print(f'WARNING: The geometry of {key} is not known!\n'
                  f'Program to extract coordinates from type:\n{type(geom0)}')
            print('*********************************************************************')
            sys.exit()

        lst_df_raw.append(gdf)

    # NOTE: do NOT change working directory here
    return lst_df_raw