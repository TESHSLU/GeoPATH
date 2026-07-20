# -*- coding: utf-8 -*-
"""
Created on Fri May 10 09:24:01 2024

@author: Simon In-Albon

this program is only to analyse raw geodata to help create calulation class in << raw_data_classes.py >>

"""

import geopandas as gpd
from tqdm import tqdm
from explore_map import map_plotter
from data_worker import find_data_path
orig_path = 'C:/Users/username/Hochschule Luzern/CC TES - Dokumente/Projekte/11.51.00278.00_SWEET_Pathfndr/07_WPs/WP3/08_GIS_Analysis/02_Data/'
data_path = find_data_path(orig_path)
del orig_path

#%% user input
map_path = ''
additional_data_path = ''

file = {'swiss_map': 'SMV1000.gpkg'}

map_creator = False

#%% import raw data

for key in tqdm(file):
    vars()[f'df_{key}'] = gpd.read_file(data_path+additional_data_path+file[key])
    # add a unique object ID    
    id_numbers = list(range(len(vars()[f'df_{key}'])))
    vars()[f'df_{key}']['obj_ID'] = [f'{key}_' + str(number) for number in id_numbers]
    vars()[f'df_{key}'].index = vars()[f'df_{key}']['obj_ID']
    vars()[f'df_{key}'] = vars()[f'df_{key}'].drop(['obj_ID'], axis=1)
    # if wanted, create interactive map
    if map_creator:
        map_plotter(vars()[f'df_{key}'], f'Map_{key}.html', map_path)


        




