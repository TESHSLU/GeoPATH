# -*- coding: utf-8 -*-
"""
Created on Wed Jun 19

This is the file where all energy stystem models are coded as classes
The provided "empty model" below can be seen as what is required to implement
a new model.

@author: Simon In-Albon
"""
from tqdm import tqdm
import pandas as pd
from data_worker import df_multiHead
import numpy as np
from gpkg_importer import gpkg_importer
import sys
from data_worker import df_multiHead, flatten_columns, unflatten_columns, str_to_list, convert_column_types, string_operator_converter, sqr_expansion, merge_touch_polygons, grid_cluster
from data_worker import point_to_sqr, grid_assignment, coor_to_points, convert_series_elements, points_to_concavehull, custom_dbscan, connection_finder, group_by_middle_overlap
from data_worker import group_by_masked_overlap
import raw_data_classes as rdc
import geopandas as gpd
import networkx as nx
import matplotlib.pyplot as plt
from pyvis.network import Network
import os
import matplotlib.colors as mcolors
import shapely
from itertools import chain
from collections import defaultdict
import GeoPATH



#%% BASELINE MODEL CLASS -! DON'T CHANGE !-

class energy_system():
    def __init__(self):
        self.dic_energy = {}
        self.dic_place = {}
        self.dic_clust = {}                                                                                     # cluster dictionary
        self.dic_connect = {}                                                                                   # connection dictionary
        self.dic_obj = {}                                                                                       # dictionary that defines demand and supply
        self.dic_con_place = {}                                                                                 # connection to placement dictionary
        self.lst_RDD = list(set([key[0] for key in self.dic_energy.keys()]))                                    # required raw data
        self.lst_binary_bc = [key[0]+'_'+key[1] for key in self.dic_energy.keys()]                              # defines the name of the columes for boundary conditions check!
        self.lst_RPD = list(dict.fromkeys(spec["placement_data"] for spec in self.dic_place.values()))          # required raw data placement
        self.lst_place_bc = [f"{spec['placement_data']}_{spec['value']}" for spec in self.dic_place.values()]   # defines the name of the columes for placement check!
        self.lst_demand = [value for key, value in self.dic_obj.items() if key[1] == 'D']
        self.lst_supply = [value for key, value in self.dic_obj.items() if key[1] == 'S']
        # connection data
        first_elements = []
        for config in self.dic_connect.values():
            first_elements.append(config['demand'][0])
            first_elements.append(config['supply'][0])
            for connector in config['connectors']:
                first_elements.append(connector[0])
                
        self.node_labels = list(dict.fromkeys(first_elements))
            
    def binary_conditions(self, df_map, limit):
        
        # binary boundary conditions are defined as "MUST HAVE" conditions
        # there needs to be a way to determine how "much" a binary BC is not fulfilled
        # if an area does not fullfill every binary BC but its total BC is above the limit it is not filltered
        # the idea is that maybe by increasing the area it will fulfill the binary BC
        
        #creating a dataframe to count the scores of the BC and how much their weight should be
        df_check = pd.DataFrame(columns=self.lst_binary_bc+['Score'], index=df_map.index)
        df_check[self.lst_binary_bc] = False
        
        
        for key in self.dic_energy.keys():
            #check if the column has lists in it
            contains_lists = df_map[key].apply(lambda x: isinstance(x, list)).any()
            if contains_lists:
                # Check if any list in contains strings
                any_list_contains_strings = df_map[key][df_map[key].apply(lambda x: isinstance(x, list))].apply(
                    lambda x: any(isinstance(item, str) for item in x)).any()
                # Check if any list in contains numbers
                any_list_contains_numbers = df_map[key][df_map[key].apply(lambda x: isinstance(x, list))].apply(
                    lambda x: any(isinstance(item, (int, float)) for item in x)).any()
                
                if any_list_contains_strings:
                    # if it's about the obj_ID then count the number of objects
                    if key[1] == 'obj_ID':
                        # we check a list with strings - therefore the number of objects in the list is compared
                        if self.dic_energy[key][0] == 'eq':
                            df_check[key[0]+'_'+key[1]] = df_map[key].str.len() == self.dic_energy[key][1]
                        elif self.dic_energy[key][0] == 'ge':
                            df_check[key[0]+'_'+key[1]] = df_map[key].str.len() >= self.dic_energy[key][1]
                        elif self.dic_energy[key][0] == 'le':
                            df_check[key[0]+'_'+key[1]] = df_map[key].str.len() <= self.dic_energy[key][1]
                        elif self.dic_energy[key][0] == 'gt':
                            df_check[key[0]+'_'+key[1]] = df_map[key].str.len() > self.dic_energy[key][1]
                        elif self.dic_energy[key][0] == 'lt':
                            df_check[key[0]+'_'+key[1]] = df_map[key].str.len() < self.dic_energy[key][1]
                        else:
                            print('*********************************************************************')
                            print(f'WARNING: dic_energy has the wrong string: {self.dic_energy[key][0]} at {key}\nChange this in energy_system_models!')
                            print('*********************************************************************')
                            sys.exit()
                    # else we check if the string is in the list
                    else:   
                        df_check[key[0]+'_'+key[1]] = df_map[key].apply(lambda x: self.dic_energy[key][1] in x if isinstance(x, list) else False)
                        

                if any_list_contains_numbers:
                    # we check a list with number - therefore it is checked if any of the values in the list fullfill the requirements
                    if self.dic_energy[key][0] == 'eq':
                        df_check[key[0]+'_'+key[1]] = df_map[key].dropna().apply(lambda lst: any(item == self.dic_energy[key][1] for item in lst))
                    elif self.dic_energy[key][0] == 'ge':
                        df_check[key[0]+'_'+key[1]] = df_map[key].dropna().apply(lambda lst: any(item >= self.dic_energy[key][1] for item in lst))
                    elif self.dic_energy[key][0] == 'le':
                        df_check[key[0]+'_'+key[1]] = df_map[key].dropna().apply(lambda lst: any(item <= self.dic_energy[key][1] for item in lst))
                    elif self.dic_energy[key][0] == 'gt':
                        df_check[key[0]+'_'+key[1]] = df_map[key].dropna().apply(lambda lst: any(item > self.dic_energy[key][1] for item in lst))
                    elif self.dic_energy[key][0] == 'lt':
                        df_check[key[0]+'_'+key[1]] = df_map[key].dropna().apply(lambda lst: any(item < self.dic_energy[key][1] for item in lst))
                    else:
                        print('*********************************************************************')
                        print(f'WARNING: dic_energy has the wrong string: {self.dic_energy[key][0]} at {key}\nChange this in energy_system_models!')
                        print('*********************************************************************')
                        sys.exit()               

            else:
                # there is no list in this column (it doesn't check for strings!)
                if self.dic_energy[key][0] == 'eq':
                    df_check[key[0]+'_'+key[1]] = df_map[key] == self.dic_energy[key][1]
                elif self.dic_energy[key][0] == 'ge':
                    df_check[key[0]+'_'+key[1]] = df_map[key] >= self.dic_energy[key][1]
                elif self.dic_energy[key][0] == 'le':
                    df_check[key[0]+'_'+key[1]] = df_map[key] <= self.dic_energy[key][1]
                elif self.dic_energy[key][0] == 'gt':
                    df_check[key[0]+'_'+key[1]] = df_map[key] > self.dic_energy[key][1]
                elif self.dic_energy[key][0] == 'lt':
                    df_check[key[0]+'_'+key[1]] = df_map[key] < self.dic_energy[key][1]
                else:
                    print('*********************************************************************')
                    print(f'WARNING: dic_energy has the wrong string: {self.dic_energy[key][0]}\nChange this in energy_system_models!')
                    print('*********************************************************************')
                    sys.exit()

        #calculating weighted score according to all boundary conditions
        # boundary conditions with low probability are weighted higher
        sqr_tot = 0
        for key in self.lst_binary_bc:
            sqr_tot += df_check[key].sum()
        df_check['Score'] = 0
        score_tot = 0
        for key in self.lst_binary_bc:
            df_check['Score'] += df_check[key]*(sqr_tot/df_check[key].sum())
            score_tot += sqr_tot/df_check[key].sum()
        df_check['Score'] = df_check['Score']/score_tot
        # limit can be calculated by using 3-quantile of all scores between 0-1, or only squares with 1 as a score are aproofed
        if limit:
            score_limit = df_check['Score'][(df_check['Score']< 1) & (df_check['Score']> 0)].quantile(0.75)
        else:
            score_limit = 1
        #filter for the squares that score above the limit
        df_proof = df_map[df_check['Score'] == 1]
        df_proof_lim = df_map[(df_check['Score'] > score_limit) & (df_check['Score'] < 1)]
        if limit:
            return df_proof, df_proof_lim
        else:
            return df_proof
# =====================================================================================================================================
    def place_assesment(self, df_map, map_key):
        """
        Parameters
        ----------
        df_map : geopandas dataframe of calculated raw data for placement, with assigned geometry in form of a polygon
            
        map_key : key of the dic_gpkg_geo, defines which requirements are needed

        Returns
        -------
        df_res : Dataframe with multicolumns named by map_key (level0), "Basic"(level1) and "area", "geometry" (level2), 
        here all proofed and merged polygons are stored

        """
        # input is the filtered df of the placement and which conditions are checked
        # output is a dataframe with all polygons that fullfile the requirements
        
        dic_check_place = {
            (spec["placement_data"], spec["value"]): [spec["operator"], spec["requirement_value"]]
            for spec in self.dic_place.values() if spec["placement_data"] == map_key}
        #creating a dataframe to logg if the requirement of placement are fulfilled
        df_check = pd.DataFrame(columns=[key[0]+'_'+key[1] for key in dic_check_place], index=df_map.index)
        df_check.loc[:,:] = False
        
        for key in dic_check_place:
            #check if the column has lists in it
            contains_lists = df_map.apply(lambda x: isinstance(x, list)).any()
            if contains_lists:
                # Check if any list in contains strings
                any_list_contains_strings = df_map[df_map.apply(lambda x: isinstance(x, list))].apply(
                    lambda x: any(isinstance(item, str) for item in x)).any()
                # Check if any list in contains numbers
                any_list_contains_numbers = df_map[df_map.apply(lambda x: isinstance(x, list))].apply(
                    lambda x: any(isinstance(item, (int, float)) for item in x)).any()
                
                if any_list_contains_strings:
                    # we check a list with strings - therefore the number of objects in the list is compared
                    if dic_check_place[key][0] == 'eq':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() == dic_check_place[key][1]
                    elif dic_check_place[key][0] == 'ge':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() >= dic_check_place[key][1]
                    elif dic_check_place[key][0] == 'le':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() <= dic_check_place[key][1]
                    elif dic_check_place[key][0] == 'gt':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() > dic_check_place[key][1]
                    elif dic_check_place[key][0] == 'lt':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() < dic_check_place[key][1]
                    else:
                        print('*********************************************************************')
                        print(f'WARNING: dic_place has the wrong string: {dic_check_place[key][0]} at {key[1]}\nChange this in user inputs!')
                        print('*********************************************************************')
                        sys.exit()

                if any_list_contains_numbers:
                    # we check a list with number - therefore it is checked if any of the values in the list fullfill the requirements
                    if dic_check_place[key][0] == 'eq':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item == dic_check_place[key][1] for item in lst))
                    elif dic_check_place[key][0] == 'ge':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item >= dic_check_place[key][1] for item in lst))
                    elif dic_check_place[key][0] == 'le':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item <= dic_check_place[key][1] for item in lst))
                    elif dic_check_place[key][0] == 'gt':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item > dic_check_place[key][1] for item in lst))
                    elif dic_check_place[key][0] == 'lt':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item < dic_check_place[key][1] for item in lst))
                    else:
                        print('*********************************************************************')
                        print(f'WARNING: dic_place has the wrong string: {dic_check_place[key][0]} at {key[1]}\nChange this in user inputs!')
                        print('*********************************************************************')
                        sys.exit()               

            else:
                # there is no list in this column (it doesn't check for strings!)
                if dic_check_place[key][0] == 'eq':
                    df_check[key[0]+'_'+key[1]] = df_map[key[1]] == dic_check_place[key][1]
                elif dic_check_place[key][0] == 'ge':
                    df_check[key[0]+'_'+key[1]] = df_map[key[1]] >= dic_check_place[key][1]
                elif dic_check_place[key][0] == 'le':
                    df_check[key[0]+'_'+key[1]] = df_map[key[1]] <= dic_check_place[key][1]
                elif dic_check_place[key][0] == 'gt':
                    df_check[key[0]+'_'+key[1]] = df_map[key[1]] > dic_check_place[key][1]
                elif dic_check_place[key][0] == 'lt':
                    df_check[key[0]+'_'+key[1]] = df_map[key[1]] < dic_check_place[key][1]
                else:
                    print('*********************************************************************')
                    print(f'WARNING: dic_place has the wrong string: {dic_check_place[key][0]}\nChange this in energy_system_models!')
                    print('*********************************************************************')
                    sys.exit()
                    
        # checks where all requirements are fulfilled                    
        df_check['Result'] = df_check.all(axis=1)
        
        # send the proofed polygons to function to merge clusters that touch each other
        df_res = merge_touch_polygons(df_map[df_check['Result']].geometry)
      
        return df_res
    
# =====================================================================================================================================
    def raw_bc_filter(self, df_map, raw_data_key):
        """
        Parameters
        ----------
        df_map : geoDataFrame or DataFrame
            Raw Dataframe that will be checked.
        raw_data_key : string
            The "name" of the raw data that is checked.

        Returns
        -------
        df_res : DataFrame or GeoDataFrame
            only those rows are send back that fulfill every requirement.
            
        IT IS ONLY CHECKED FOR ENERGY REQUIREMENTS THAT CAN BE CHECKED IN THE RAW DATA!
        """
        
        # check if the requirement is in the raw data or not, if not- delete it from the list
        dic_check = {key: value for key, value in self.dic_energy.items() if (key[0] == raw_data_key) and (key[1] in df_map.columns) }
        # if there are no requirements that can be checked, df_map is the df_res
        if len(dic_check) > 0:
            #creating a dataframe to logg if the requirement of placement are fulfilled
            df_check = pd.DataFrame(columns=[key[0]+'_'+key[1] for key in dic_check], index= df_map.index)
            df_check.loc[:,:] = False
            
            for key in dic_check:
                #check if the column has lists in it
                contains_lists = df_map.apply(lambda x: isinstance(x, list)).any()
                if contains_lists:
                    # Check if any list in contains strings
                    any_list_contains_strings = df_map[df_map.apply(lambda x: isinstance(x, list))].apply(
                        lambda x: any(isinstance(item, str) for item in x)).any()
                    # Check if any list in contains numbers
                    any_list_contains_numbers = df_map[df_map.apply(lambda x: isinstance(x, list))].apply(
                        lambda x: any(isinstance(item, (int, float)) for item in x)).any()
                    
                    if any_list_contains_strings:
                        # if it's about the obj_ID then count the number of objects
                        if key[1] == 'obj_ID':
                            # we check a list with strings - therefore the number of objects in the list is compared
                            if self.dic_energy[key][0] == 'eq':
                                df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() == self.dic_energy[key][1]
                            elif self.dic_energy[key][0] == 'ge':
                                df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() >= self.dic_energy[key][1]
                            elif self.dic_energy[key][0] == 'le':
                                df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() <= self.dic_energy[key][1]
                            elif self.dic_energy[key][0] == 'gt':
                                df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() > self.dic_energy[key][1]
                            elif self.dic_energy[key][0] == 'lt':
                                df_check[key[0]+'_'+key[1]] = df_map[key[1]].str.len() < self.dic_energy[key][1]
                            else:
                                print('*********************************************************************')
                                print(f'WARNING: dic_energy has the wrong string: {self.dic_energy[key][0]} at {key[1]}\nChange this in energy_system_models!')
                                print('*********************************************************************')
                                sys.exit()
                        # else we check if the string is in the list
                        else:   
                            df_check[key[0]+'_'+key[1]] = df_map[key].apply(lambda x: self.dic_energy[key][1] in x if isinstance(x, list) else False)
                          
    
                    if any_list_contains_numbers:
                        # we check a list with number - therefore it is checked if any of the values in the list fullfill the requirements
                        if self.dic_energy[key][0] == 'eq':
                            df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item == self.dic_energy[key][1] for item in lst))
                        elif self.dic_energy[key][0] == 'ge':
                            df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item >= self.dic_energy[key][1] for item in lst))
                        elif self.dic_energy[key][0] == 'le':
                            df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item <= self.dic_energy[key][1] for item in lst))
                        elif self.dic_energy[key][0] == 'gt':
                            df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item > self.dic_energy[key][1] for item in lst))
                        elif self.dic_energy[key][0] == 'lt':
                            df_check[key[0]+'_'+key[1]] = df_map[key[1]].apply(lambda lst: any(item < self.dic_energy[key][1] for item in lst))
                        else:
                            print('*********************************************************************')
                            print(f'WARNING: dic_energy has the wrong string: {self.dic_energy[key][0]} at {key[1]}\nChange this in energy_system_models!')
                            print('*********************************************************************')
                            sys.exit()               
    
                else:
                    # there is no list in this column (it doesn't check for strings!)
                    if self.dic_energy[key][0] == 'eq':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]] == self.dic_energy[key][1]
                    elif self.dic_energy[key][0] == 'ge':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]] >= self.dic_energy[key][1]
                    elif self.dic_energy[key][0] == 'le':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]] <= self.dic_energy[key][1]
                    elif self.dic_energy[key][0] == 'gt':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]] > self.dic_energy[key][1]
                    elif self.dic_energy[key][0] == 'lt':
                        df_check[key[0]+'_'+key[1]] = df_map[key[1]] < self.dic_energy[key][1]
                    else:
                        print('*********************************************************************')
                        print(f'WARNING: dic_energy has the wrong string: {self.dic_energy[key][0]}\nChange this in energy_system_models!')
                        print('*********************************************************************')
                        sys.exit()
                        
            # checks where all requirements are fulfilled                    
            df_check['Result'] = df_check.all(axis=1)
            df_res = df_map[df_check['Result']]
        else:
            df_res = df_map
        return df_res
    
    # =====================================================================================================================================
    def DBSCAN_cluster(self, df_obj, key_req):
        """
        Parameters
        ----------
        df_obj : GeoDataFrame
            raw data type with points as geometry
        key_req : Tuple
            (Name_rawfile, column_to_cluster).

        Returns
        -------
        df_basic : DataFrame 
            DF with concave hull as geometry and clustered data according raw_data_classes

        """
        # cluster boundaries
        obj_key = key_req[0]
        spec = self.dic_clust[obj_key]
        
        eps = spec['max_distance']
        min_value_density = spec['value_density']
        min_value_sum = min_value_density * ((eps**2) * np.pi)
        
        val = spec['clustered_value']
        min_number = spec['min_number_objects']
        cluster = spec['interested_in_cluster']

        #drop all rows with nan at the checked value
        df_obj.dropna(subset=[val], inplace = True)
        
        # ---- GUARD: nothing left to cluster after filtering ----    inserted 28.10.25
        if df_obj.empty:
            # Ensure the caller gets a valid dataframe back (with the expected column name if you add it later)
            df_obj["cluster_no"] = pd.Series(dtype="int64")
            return df_obj
        try:
             df_obj['x']
        except:
            print('!!!!! only points can be clustered !!!')
            sys.exit()
        # send to custom DBSCAN
        # print(f'----- Start DBSCAN for {key_req[0]} -----')
        df_obj['cluster_no'] = custom_dbscan(df_obj, eps, min_value_sum, min_number, val)
        
        lst_cluster = df_obj['cluster_no'].drop_duplicates().tolist()
        lst_cluster.sort()
        # if the clustered points are needed
        if cluster == True:
            # remove unclustered data
            if -1 in lst_cluster:
                lst_cluster.remove(-1)

            # initialise resulting df
            df_basic = df_multiHead(['Basic'], ['geometry', 'area'], ['source', 'data'], [f"{key_req[0]}_clust_{number}" for number in lst_cluster], np.nan)
            # # ensure geometry column is object-typed before assigning Polygons

            for num in lst_cluster:
                # check if minimal number
                if len(df_obj[df_obj['cluster_no'] == num]) >= min_number:
                    poly_new = points_to_concavehull(df_obj[df_obj['cluster_no'] == num].geometry, ratio= 0.01)
                    df_basic.loc[f"{key_req[0]}_clust_{num}", ('Basic', 'geometry')] = poly_new
                    df_basic.loc[f"{key_req[0]}_clust_{num}", ('Basic', 'area')] = poly_new.area

            # recalculate the clustered data according to raw_data_classes                
            my_class = getattr(rdc, key_req[0])
            df_obj_clust = my_class(df_basic[('Basic','geometry')], df_obj, key_req[0])
            df_basic = pd.concat([df_basic, df_obj_clust.df_res], axis=1)
            # drop top level of columns
            df_basic.columns = df_basic.columns.droplevel(0)
        
        # if instead all unclustered objects are needed, only those will be returned
        else:
            df_basic = df_obj[df_obj['cluster_no']== -1]
            
        return df_basic
    
    # =====================================================================================================================================
    # function to display the connections given by the user
    def Connection_graph(self, name, save_path, color_palette="Dark2"):
        
        cmap = plt.get_cmap(color_palette, len(self.dic_connect))
        colors = [mcolors.to_hex(cmap(i)) for i in range(len(self.dic_connect))]
        
        net = Network(height="500px", width="100%", directed=True)
        net.barnes_hut()  # Layout algorithm for nice spacing
        
        net.add_nodes(self.node_labels, label = self.node_labels,font={'size': 20})
        net.set_options('{"nodes": {"font": {"size": 15}}}')        # add all edges
        count = 0
        for dict_now in self.dic_connect.values():
            edge_color = colors[count]
            # if there are connectors:
            if len(dict_now['connectors']) != 0:
                for i in range(len(dict_now['connectors'])):
                    if i == 0:
                        a = dict_now['demand'][0]
                    else:
                        a = dict_now['connectors'][i-1][0]
                    b = dict_now['connectors'][i][0]
                    
                    net.add_edge(b, a, color= edge_color)
                    
                a = dict_now['connectors'][i][0]
                b = dict_now['supply'][0]
                net.add_edge(b, a, color= edge_color)
                count += 1
            
            # if there are no connectors:
            else:
                a = dict_now['demand'][0]
                b = dict_now['supply'][0]
                net.add_edge(b, a, color= edge_color)
                count += 1
        #save the graph and show it
        original_dir = os.getcwd()
        os.chdir(save_path)
        net.show(name, notebook=False)
        os.chdir(original_dir)

    # =====================================================================================================================================
    # function that handles the connection defined by the user, sends the relevant raw data to the connection_finder
    def Network_Handler(self, dic_all_df_raw, max_value):
        
        # this function handles the building of connections
        
        """
        1. Get all connections from class
        2. sort the connections in the best possible way (not implemented)
        3. get all data needed (if there is no limit to one source or sink, the column is called "None" and the values are all the sum of the total demand or supply that should be covered, such that potentialy one object can cover everything)
        
        4. loop over every connection:
            4.1 send information to connection_finder
            4.2 erase objects from data if there were no connections found
        5. return connection_gdf
        
        """
        # ---------------- replace self with self ---------------------
        no_data_error = 0
        
        # unpack dict_all raw data
        for dic_key in dic_all_df_raw.keys():
            #find all needed data of this column
            res_columns = []
            for config in self.dic_connect.values():
                # Check 'demand' tuple
                if config['demand'][0] == dic_key:
                    res_columns.append(config['demand'][1])
                # Check 'supply' tuple
                if config['supply'][0] == dic_key:
                    res_columns.append(config['supply'][1])
                # Check each connector tuple
                for connector in config['connectors']:
                    if connector[0] == dic_key:
                        res_columns.append(connector[1])
            res_columns = list(dict.fromkeys(res_columns))
            res_columns.append('geometry')
            
            if len(res_columns) != 0:
                if 'None' in res_columns:
                    vars()[dic_key] = dic_all_df_raw[dic_key]
                    vars()[dic_key]['None'] =  max_value
                    #assign the needed data
                    vars()[dic_key] = vars()[dic_key][res_columns]
                else:
                    vars()[dic_key] = dic_all_df_raw[dic_key][res_columns]
                # drop all object which have one nan!
                vars()[dic_key] = vars()[dic_key].dropna()
                
                if len(vars()[dic_key]) == 0:
                    print(f'!!!!! NO DATA FOUND IN <<{dic_key}>> RAW DATA FOR THIS AREA !!!!!')
                    print('!!!!! NO CONNECTIONS POSSIBLE !!!!!')
                    no_data_error = 1 
                    
        if no_data_error == 0:
            #create result dataframe
            # find all energy_types defined by the user
            lst_energy_type = list({v['energy_type'] for v in self.dic_connect.values()})
            column_energy_type = ['Network_' + etype for etype in lst_energy_type]
            dic_energy_type_keys = {energy_key: [f'Connections_{k}' for k, v in self.dic_connect.items() 
                                                 if v['energy_type'] == energy_key.split('_')[1]] for energy_key in column_energy_type}
            column_con = ['Connections_' + str(num) for num in list(self.dic_connect.keys())]
            lst_basic_columns =  ['objs', 'value', 'distance', 'distance/value', 'geometry', 'Network']
            df_res_network = df_multiHead(column_con + column_energy_type + ['Network_total'], lst_basic_columns, ['type', 'data'], [], np.nan)
            
            # iterate through each connection
            iter_count = 0
            for con_key, dict_now in self.dic_connect.items(): 
                # prepare demand
                df_demand = vars()[dict_now['demand'][0]][[dict_now['demand'][1], 'geometry']].copy()
                df_demand[dict_now['demand'][1]] = df_demand[dict_now['demand'][1]] * dict_now['demand'][2]
                # prepare supply
                df_supply = vars()[dict_now['supply'][0]][[dict_now['supply'][1], 'geometry']].copy()
                df_supply[dict_now['supply'][1]] = df_supply[dict_now['supply'][1]] * dict_now['supply'][2]
                df_connectors = []
                # if needed prepare connectors:
                if len(dict_now['connectors']) != 0:
                    for con in dict_now['connectors']:
                        df_add = vars()[con[0]][[con[1], 'geometry']].copy()
                        df_add[con[1]] = df_add[con[1]] * con[2]
                        df_connectors.append(df_add)
                if dict_now['value_distance']:
                    dist_typus = 'variable'
                else:
                    dist_typus = 'fix'
                #~~~~~~~~~~~~~~~~~~    Connection_Finder
                # send all information to the connection_finder
                df_con = connection_finder(df_supply, df_demand, dist_typus, dict_now['max_distance'], df_a= df_connectors)         
                # sys.exit()
                # if no connections found - exit loop
                if len(df_con) == 0:
                    break
                else:
                    # check if there is the same connection multiple times
                    # Step 1: Sort the lists to normalize order
                    df_con['tags_key'] = df_con['objs'].apply(lambda x: tuple(sorted(x)))
                    # Step 2: Group by the normalized key
                    df_con = df_con.groupby('tags_key', as_index=False).agg({
                        'objs': 'first',       # Keep the first original list (for display)
                        'value': 'sum',         # Sum the values
                        'distance': 'sum',         # Sum the values
                        'distance/value': 'mean',         # Sum the values
                        'geometry': 'first',         # Sum the values
                    })
                    df_con = df_con.drop(columns='tags_key')
                    df_con.index = [f'Con_{i}' for i in range(len(df_con))]
                   
                    #~~~~~~~~~~~~~~~~~~    UPDATE RAW DATA
                    #update demand object in this connection - only the objects connected stay
                    objs_connected = list(dict.fromkeys(item if not isinstance(item := entry[0], list) else item for entry in df_con['objs']))
                    vars()[dict_now['demand'][0]] = vars()[dict_now['demand'][0]].loc[objs_connected,:]
                    #update supply object in this connection - only the objects connected stay
                    objs_connected = list(dict.fromkeys(item if not isinstance(item := entry[-1], list) else item for entry in df_con['objs']))
                    vars()[dict_now['supply'][0]] = vars()[dict_now['supply'][0]].loc[objs_connected,:]
                    #if needed update all objects that are connectors
                    if len(dict_now['connectors']) != 0:
                        counter = 1
                        for con in dict_now['connectors']:
                            objs_connected = list(dict.fromkeys(item if not isinstance(item := entry[counter], list) else item for entry in df_con['objs']))
                            vars()[con[0]] = vars()[con[0]].loc[objs_connected,:]
                            counter +=1
                        del counter
                    #~~~~~~~~~~~~~~~~~~    CREATE NETWORKS FOR THIS CONNECTION
                    # create networks with this connection
                    # ----------old version -----------------
                    # create networks if the middle object is the same
                    # df_con_net = group_by_middle_overlap(df_con, 'objs')
                    # ---------------------------
                    # new version takes user defined inputs if an object can be a connection hub or not
                    # check which ones are connection hubs
                    mask_hubs = [dict_now['demand'][3],  # from 'demand'
                        *[connector[3] for connector in dict_now.get('connectors', [])],  # all from 'connectors' if any
                        dict_now['supply'][3]  ]
                    df_con_net = group_by_masked_overlap(df_con, 'objs', mask_hubs)
                    
                    def combine_multilines(multis):
                        lines = []
                        for mls in multis:
                            lines.extend(mls.geoms)  # extract LineStrings from each MultiLineString
                        return shapely.MultiLineString(lines)
                    df_con_net['value'] = df_con_net['value'].apply(sum)
                    df_con_net['distance'] = df_con_net['distance'].apply(sum)
                    df_con_net['distance/value'] = df_con_net['distance']/df_con_net['value']
                    df_con_net['geometry'] = df_con_net['geometry'].apply(combine_multilines)
                    df_con_net = gpd.GeoDataFrame(data = df_con_net, geometry=df_con_net['geometry'], crs ='EPSG:2056')
                    df_con_net.index = [f'Network_{i}' for i in range(len(df_con_net))]
                    df_con_net['Network'] = [i for i in range(len(df_con_net))]

                    #~~~~~~~~~~~~~~~~~~    Save Network in resulting DataFrame
                    if iter_count == 0:
                        # if it's the first connection, simply save it
                        df_res_network[(f'Connections_{con_key}')] = df_con_net.copy()
                    else:
                        #check each new network to which existing network it belongs
                        for h in df_con_net.index:
                            #list of network objs
                            lst_net_objs = [item for sublist, flag in zip(df_con_net.loc[h,'objs'], mask_hubs) if flag for item in sublist]
                            # Check which positions match
                            all_obj_df = df_res_network.loc[:, [(col, 'objs') for col in column_con]]
                            all_obj_df = all_obj_df.applymap(lambda x: [] if x != x else x)  
                            
                            def row_contains_elements(row, elements_to_check):
                                for cell in row:
                                    for sublist in cell:
                                        for elem in elements_to_check:
                                            if elem in sublist:
                                                return True
                                return False
                            
                            mask = all_obj_df.apply(lambda row: row_contains_elements(row, lst_net_objs), axis=1)
                            matching_indices = all_obj_df[mask].index.tolist()
                            if not matching_indices:
                                new_index = f'Network_{len(df_res_network)}'
                                df_res_network.loc[new_index, f'Connections_{con_key}'] = df_con_net.loc[h, :].values.copy()
                            else:
                                # take the first element of the list matching_indices (not the best way to do that)
                                multi_cols = pd.MultiIndex.from_product([[f'Connections_{con_key}'], lst_basic_columns])
                                df_res_network.loc[matching_indices[0], multi_cols] = df_res_network.loc[matching_indices[0], multi_cols].astype('object')
                                df_res_network.loc[matching_indices[0], multi_cols] = df_con_net.loc[h, :].values.copy()
                iter_count += 1
             
            # find which Networks are not complete and drop them
            nan_rows = df_res_network[column_con][df_res_network[column_con].isna().any(axis=1)].index
            df_res_network = df_res_network.drop(index=nan_rows)
            
            # calculate all add up columns: energy type related and total
            for ener_type in column_energy_type:
                multi_cols = pd.MultiIndex.from_product([dic_energy_type_keys[ener_type], ['value']])
                df_res_network.loc[:,(ener_type,'value')] = df_res_network[multi_cols].sum(axis=1)
                multi_cols = pd.MultiIndex.from_product([dic_energy_type_keys[ener_type], ['distance']])
                df_res_network.loc[:,(ener_type,'distance')] = df_res_network[multi_cols].sum(axis=1)
                df_res_network.loc[:,(ener_type,'distance/value')] = df_res_network.loc[:,(ener_type,'distance')]/df_res_network.loc[:,(ener_type,'value')]
                multi_cols = pd.MultiIndex.from_product([dic_energy_type_keys[ener_type], ['geometry']])
                df_res_network.loc[:,(ener_type,'geometry')] = df_res_network[multi_cols].apply(lambda row: combine_multilines(row), axis=1)
            
            #calculate total networks
            multi_cols = pd.MultiIndex.from_product([column_con, ['value']])
            df_res_network.loc[:,('Network_total','value')] = df_res_network[multi_cols].sum(axis=1)
            multi_cols = pd.MultiIndex.from_product([column_con, ['distance']])
            df_res_network.loc[:,('Network_total','distance')] = df_res_network[multi_cols].sum(axis=1)
            df_res_network.loc[:,('Network_total','distance/value')] = df_res_network.loc[:,('Network_total','distance')]/df_res_network.loc[:,('Network_total','value')]
            multi_cols = pd.MultiIndex.from_product([column_con, ['geometry']])
            df_res_network.loc[:,('Network_total','geometry')] = df_res_network[multi_cols].apply(lambda row: combine_multilines(row), axis=1)
            def merge_nested_to_dict_with_prefixes(prefixes, *cols):
                seen = set()
                grouped = {p: [] for p in prefixes}
            
                for col in cols:
                    for sublist in col:
                        for item in sublist:
                            if item not in seen:
                                seen.add(item)
                                # Find first matching prefix
                                prefix_match = next((p for p in prefixes if item.startswith(p + '_')), None)
                                if prefix_match:
                                    grouped[prefix_match].append(item)
            
                # Remove empty groups if desired
                return {k: v for k, v in grouped.items() if v}
            multi_cols = pd.MultiIndex.from_product([column_con, ['objs']])
            df_res_network.loc[:,('Network_total','objs')] = df_res_network[multi_cols].apply(lambda row: merge_nested_to_dict_with_prefixes(list(dic_all_df_raw.keys()), *row), axis=1)
            
            # drop all unused infos like which objects are involved
            cols_to_drop = [col for col in df_res_network.columns if col[1] == 'Network']
            df_res_network = df_res_network.drop(columns=cols_to_drop)
            cols_to_drop = [col for col in df_res_network.columns if (col[1] == 'objs') and (col[0] in column_energy_type)]
            df_res_network = df_res_network.drop(columns=cols_to_drop)
            
        else:
            #create result dataframe with 0 as value - no data to create connections
            # find all energy_types defined by the user
            lst_energy_type = list({v['energy_type'] for v in self.dic_connect.values()})
            column_energy_type = ['Network_' + etype for etype in lst_energy_type]
            dic_energy_type_keys = {energy_key: [f'Connections_{k}' for k, v in self.dic_connect.items() 
                                                 if v['energy_type'] == energy_key.split('_')[1]] for energy_key in column_energy_type}
            column_con = ['Connections_' + str(num) for num in list(self.dic_connect.keys())]
            lst_basic_columns =  ['objs', 'value', 'distance', 'distance/value', 'geometry', 'Network']
            df_res_network = df_multiHead(column_con + column_energy_type + ['Network_total'], lst_basic_columns, ['type', 'data'], ['Network_0'], 0)
                    
        return df_res_network
        
    # =====================================================================================================================================      


#%% vertical hydrogen storage
class tes_gis_model(energy_system):
    
    def __init__(self):
        self.dic_energy   = GeoPATH.get_dic_energy()       
        self.dic_place    = GeoPATH.get_dic_place()
        self.dic_obj      = GeoPATH.get_dic_obj()
        self.dic_clust    = GeoPATH.get_dic_clust()
        self.dic_connect  = GeoPATH.get_dic_connect()
        self.dic_site     = GeoPATH.get_dic_site()
        
    def get_dic_site(self):
        return self.dic_site
    
    def set_dic_site(self, index, value):
        self.dic_site[index] = value
    
    def get_dic_energy(self):
        return self.dic_energy
    
    def set_dic_energy(self, index, value):
        self.dic_energy[index] = value
    
    def get_dic_place(self):
        return self.dic_place
    
    def set_dic_place(self, index, value):
        self.dic_place[index] = value
    
    def get_dic_clust(self):
        return self.dic_clust
    
    def set_dic_clust(self, index, value):
        self.dic_clust[index] = value
    
    def get_dic_obj(self):
        return self.dic_obj
    
    def set_dic_obj(self, index, value):
        self.dic_obj[index] = value
    
    def get_dic_connect(self):
        return self.dic_connect
    
    def set_dic_connect(self, index, value):
        self.dic_connect[index] = value


    
    
        
        
    # ======================================
    # predefined parameter that constantly update-! DON'T CHANGE !-
    @property
    def lst_RDClust(self):
        return list(self.dic_clust.keys())                               # required raw data to cluster
    @property
    def lst_RDD(self):
        return list(set([key[0] for key in self.dic_energy.keys()]))     # required raw data energy
    @property
    def lst_binary_bc(self):
        return [key[0]+'_'+key[1] for key in self.dic_energy.keys()]     # defines the name of the columes for boundary conditions check!
    @property
    def lst_RPD(self):
        return list(dict.fromkeys(spec["placement_data"] for spec in self.dic_place.values()))          # required raw data placement
    @property
    def lst_RCD(self):                                                   # required raw data for connection
        rcd_set = set()
        
        for connection in self.dic_connect.values():
            # Add demand
            rcd_set.add(connection['demand'][0])
    
            # Add supply
            rcd_set.add(connection['supply'][0])
    
            # Add all connectors
            for conn in connection.get('connectors', []):
                rcd_set.add(conn[0])
    
        return list(rcd_set)

        
#%%
               
        
