# -*- coding: utf-8 -*-
"""
Created on Wed Sep 25 2024

Program to creat a 1km2 grid over all switzerland
this grid is used for placement data to cluster
the output is the .gpkp file and a map of the grid
the assigned "number" of every square is later also assigned to the raw data

@author: Simon In-Albon
"""
import geopandas as gpd
import shapely
import folium
import webbrowser
import pyproj
import os
import pandas as pd
import numpy as np
import time
import sys
import csv
import math
import matplotlib.pyplot as plt
from tqdm import tqdm
from datetime import datetime
from folium.plugins import FloatImage
import rioxarray
import dask_geopandas as dg

#%% 
# =========================== User Inputs ===================================== 

# Result_path
data_path = '../02_Data/'
map_path = '../03_Results/RawData_Maps/'
file_name = 'Swiss_1km2_map'

#==============================================================================
print ('\n=====================================================================')
print ('----- All user inputs are saved -----')
print ('=====================================================================')
#%% Import Functions and precalculated Data
print ('\n=====================================================================')
print ('----- Start Raw Data import -----')
print ('=====================================================================')

from explore_map import *
from df_empty_main import *
from gpkg_importer import *

os.chdir(data_path)

#import border data
try :
    df_border = gpd.read_file('swiss_border_poly.gpkp')
    border_poly = df_border.geometry[0]
except:
    print ('\n=====================================================================')
    print( '---ERROR---\n Swiss boarder file does not exist!\n Run the Code "swiss_border_polygon.py"\n or save the file "swiss_border_poly.gpkp" in the Data-Folder! ')
    print ('\n=====================================================================')
    exit
#%% create grid size in switzerland to cluster data

sqr_size = 1000

start_x = 2485410
end_x = 2833859
start_y = 1075269
end_y = 1295934

dist_x = end_x - start_x
dist_y = end_y - start_y
num_x = int(dist_x/sqr_size)
num_y = int(dist_y/sqr_size)

lst_x_coords = list(range(start_x,start_x+(num_x+2)*sqr_size,sqr_size))
lst_y_coords = list(range(start_y,start_y+(num_y+2)*sqr_size,sqr_size))

df_calc = pd.DataFrame(columns=['x', 'y', 'geometry', 'number', 'on_border'])
counter = 0
for k in tqdm(range(num_y+1)):
    for j in range(num_x+1):
        df_calc.loc[counter,'x'] = int((lst_x_coords[j]+lst_x_coords[j+1])/2)
        df_calc.loc[counter,'y'] = int((lst_y_coords[k]+lst_y_coords[k+1])/2) 
        df_calc.loc[counter, 'geometry'] = shapely.geometry.Polygon([(lst_x_coords[j], lst_y_coords[k]), (lst_x_coords[j+1], lst_y_coords[k]), (lst_x_coords[j+1], lst_y_coords[k+1]), (lst_x_coords[j], lst_y_coords[k+1])])
        counter += 1
        
df_sqr = gpd.GeoDataFrame(data = df_calc[['x', 'y', 'number']], geometry=df_calc.geometry, crs='EPSG:2056')  

print ('\n----- Erasing all squares outside switzerland -----')
print ('\nThis takes time... \nno rush...')

mask = df_sqr.geometry.intersects(border_poly)
df_sqr = df_sqr[mask]
df_sqr = df_sqr.reset_index(drop = True)
print ('----- Done-----')

# sort dataframe such that x,y are sorted (way faster for later use!)
df_sqr.sort_values(by=['x', 'y'], ascending=[True, True], inplace=True)
df_sqr.reset_index(inplace=True)
df_sqr.drop(['index'], axis=1, inplace=True)

#assign the square number
df_sqr.loc[:, 'number'] = df_sqr.index
print ('----- Checking which square is on the border -----')
# assign if a square is touching the border
borderline = border_poly.boundary
df_sqr['on_border'] = df_sqr.geometry.intersects(borderline)
# save that grid and reuse it allways
print ('----- Saving file-----')

df_sqr.to_parquet(file_name+'.parquet')
map_plotter(df_sqr, (file_name+'_map.html'), map_path)
