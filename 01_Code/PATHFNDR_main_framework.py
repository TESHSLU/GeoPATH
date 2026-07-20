# -*- coding: utf-8 -*-
"""
Created on Thu Apr 18 16:48:27 2024

@author: Simon In-Albon

"""
# %% 
import geopandas as gpd
import shapely
import os
import pandas as pd
import numpy as np
import time
import sys
import ast
import matplotlib.pyplot as plt
from tqdm import tqdm
from datetime import datetime
from itertools import chain
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib
import matplotlib.image as mpimg
from matplotlib.ticker import MaxNLocator
import raw_data_classes as rdc
import energy_system_models as esm
from data_worker import df_multiHead, flatten_columns, unflatten_columns, str_to_list, convert_column_types, string_operator_converter, sqr_expansion, merge_touch_polygons, grid_cluster
from data_worker import point_to_sqr, grid_assignment, coor_to_points, convert_series_elements, points_to_concavehull, custom_dbscan, convert_multipoint_to_point
from data_worker import recursive_dfs, connect_geometries_by_shortest_distance, connection_finder, max_dist_connection, lines_to_tuple_list, df_to_array
from data_worker import group_by_middle_overlap, group_by_masked_overlap, covering_circle, explode_geometrycollections, create_inputs_as_txt
from gpkg_importer import gpkg_importer, extract_coordinates
from explore_map import map_plotter, color_map_plotter, final_map_plotter, extract_prefixes, generate_shades
from pathlib import Path
import copy
    
import GeoPATH

# import rioxarray
# import dask_geopandas as dg

from data_worker import find_data_path
#%%
def PATHFNDR_main_framework():
    vars = globals  

#%%    
    overall_time_start = time.time()
    
    data_path = "Path_to_data_folder" 
    
    #1.0 User Inputs
    # =========================== User Inputs ===================================== 


    # --- GET USER INPUTS from GeoPATH.py ---
    # Unit of Results
    res_unit_type = GeoPATH.get_res_unit_type()
    res_unit = GeoPATH.get_res_unit()
    res_SI_unit = GeoPATH.get_res_SI_unit()
    fac_SI_unit = GeoPATH.get_fac_SI_unit()

    sqr_size       = GeoPATH.get_sqr_size()        # [m]
    sqr_size_exp   = GeoPATH.get_sqr_size_exp()    # [m]

    # --- Result path ---
    result_folder  = GeoPATH.get_result_folder()

    # --- Calculation configuration ---
    explore_raw_data = GeoPATH.get_explore_raw_data()
    ReCalcData = GeoPATH.get_ReCalcData()
    
    # --- Energy Data source configuration ---
    data_energy_path = GeoPATH.get_data_energy_path()
    dic_gpkg_data    = GeoPATH.get_dic_gpkg_data()

    # --- Placement Data source configuration geo() ---
    dic_gpkg_geo = GeoPATH.get_dic_gpkg_geo()
    data_placement_path = GeoPATH.get_data_placement_path()
    
    #==============================================================================
    print ('\n=====================================================================')
    print ('----- All user inputs are saved -----')
    print ('=====================================================================')

    lst_model = ['tes_gis_model']
    map_path = data_path +'../03_Results/'+result_folder+'/'
    
    # Create folder for results   
    Path(data_path +'../03_Results/'+result_folder).mkdir(parents=True, exist_ok=False)
    #%% User inputs about the units are checked (new in feb. 2026)
    
    # import excel and create nested dictionary
    energy_meta_excel = 'energy_data_infos.xlsx'
    energy_meta_path = data_path+data_energy_path+'/'+energy_meta_excel
    # Read all sheets
    sheets = pd.read_excel(energy_meta_path, sheet_name=None)
    meta_rows=["Unit of Values","Base-Unit","Unit Factor","Value Type"]
    # creating unit dictionary
    dic_unit={}
    for sheet_name,df in sheets.items():
        first_col=df.columns[0]
        df[first_col]=df[first_col].astype(str).str.strip()
        df_meta=df[df[first_col].isin(meta_rows)].copy().set_index(first_col).reindex(meta_rows)
        sheet_dict={}
        for col in df_meta.columns:
            col_name=str(col).strip()
            sheet_dict[col_name]={k:(None if pd.isna(v) else v) for k,v in df_meta[col].to_dict().items()}
        dic_unit[sheet_name]=sheet_dict

    # check if all object values of dic_obj have the same SI-Unit, if not ask user if they are aware of it!
    si_units=[]
    for sheet,col in GeoPATH.get_dic_obj().keys():
        try:
            si_unit=dic_unit[sheet][col]["Base-Unit"]
            si_units.append((sheet,col,si_unit))
        except KeyError:
            raise KeyError(f"Missing SI-Unit for ({sheet}, {col}) in dic_unit")
    
    unique_units=set(u for _,_,u in si_units)
    
    if len(unique_units)>1:
        print("Warning: Not all objects use the same Base-Unit.")
        for sheet,col,unit in si_units:
            print(f"{sheet} - {col}: {unit}")
        user_input=input("Press Enter to continue or type 'q' to quit: ").strip().lower()
        if user_input in ["q","quit","exit","n"]:
            sys.exit("Execution stopped due to inconsistent Base-Units.")    
    mismatch=[(s,c,u) for s,c,u in si_units if u!=res_SI_unit]
    if mismatch:
        print(f"Result Base-Unit: {res_SI_unit}")
        print("Objects with different Base-Unit:")
        for s,c,u in mismatch:
            print(f"{s} - {c}: {u}")
        user_input=input("Press Enter to continue or type 'q' to quit: ").strip().lower()
        if user_input in ["q","quit","exit","n"]:
            sys.exit("Execution stopped due to SI-Unit mismatch with result Base-Unit.")
            
    # change for each object the factor in dic_obj according to the unit factor
    for (sheet,col),values in GeoPATH.get_dic_obj().items():
        try:
            unit_factor=dic_unit[sheet][col]["Unit Factor"]
            if unit_factor is None:
                raise ValueError(f"No Unit Factor defined for ({sheet},{col})")
            values[1]=values[1]*unit_factor
        except KeyError:
            raise KeyError(f"Missing Unit Factor for ({sheet},{col}) in dic_unit")
    
    del sheets,meta_rows,sheet_name,df,first_col,df_meta,sheet_dict,col,col_name,si_units,unique_units,sheet,unit_factor,values,mismatch,si_unit
    
    #%% Data import and processing
    print ('\n=====================================================================')
    print ('----- Start Raw Data import -----')
    print ('=====================================================================')
    
    #import border data
    try :
        df_border = gpd.read_file(data_path+'swiss_border_poly.gpkg')
        border_poly = df_border.geometry[0]
    except:
        print ('\n=====================================================================')
        print( '---ERROR---\n Swiss border file does not exist!\n Run the Code "swiss_border_polygon.py"\n or save the file "swiss_border_poly.gpkg" in the Data-Folder! ')
        print ('\n=====================================================================')
        sys.exit(0)
    # import metadata of boundary condition files
    try :
        f_name = f'bc_checker_{sqr_size}_{sqr_size_exp}.csv'
        df_bc_check = pd.read_csv(data_path + 'square_maps/' + f_name, index_col=0)
        df_bc_check = df_bc_check.applymap(lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith('{') else x)
    except:
        df_bc_check = pd.DataFrame(columns=['dic'], index= [0], dtype=object)
        dic_dummy = GeoPATH.get_dic_energy()
        
    # confirme your choice of recalculation
    if ReCalcData:
        Req = input('\n*********************************************************************\n Do you really want to recalculate all values?: [y/n]')
        print ('*********************************************************************\n')
        if Req == 'y':
            pass
        else:
            print('***** Change ReCalcData to FALSE! *****\n')
            ReCalcData = False
    
    checker = 0
    # load calculated data:
    if not ReCalcData:
        print ('----- Looking for pre calculated data -----')
        sqr_file = f'sqr_data_swiss_{sqr_size}.gpkg'
        while checker == 0:
            try:
                #import gpkp file
                df_calc = gpd.read_file(data_path+'square_maps/'+sqr_file)
                print ('----- Found pre calculated data! -----')
                print ('----- Unpacking and formating -----')
                #unpack all strings as lists or numbers
                # Iterate over each column in the DataFrame
                df_calc = convert_column_types(df_calc.copy())
                for column in df_calc.columns:
                    # Check if the column contains strings that could represent lists
                    if df_calc[column].apply(lambda x: isinstance(x, str) and ',' in x).any() or "ID" in column :
                        # Convert comma-separated strings back to lists
                        df_calc[column] = df_calc[column].apply(str_to_list)
                        print(f"Column '{column}' converted from string to list.")
                        df_calc[column] = convert_series_elements(df_calc[column])
    
                
                #unflatten the multicolumn header and name the two columns
                df_calc = unflatten_columns(df_calc.copy())
                df_calc.columns.names = ['source', 'data']
                #rename geometry column an asign it correctly
                df_calc = df_calc.rename(columns={np.nan:'geometry'}, level=1)
                df_calc = df_calc.rename(columns={'geometry':'Basic'}, level=0)
                df_calc = df_calc.set_geometry(('Basic', 'geometry'))
                #create a list of all raw data that is needed to import anyway
                lst_calculated_data = df_calc.columns.levels[0].values.tolist()
                lst_calc_data = list(set(list(dic_gpkg_data.keys()))-set(lst_calculated_data))
                
                checker = 1
                print ('----- Pre-calculated Data is ready! -----')
                if df_calc[df_calc.loc[:,('Basic','within_swiss')]].iloc[0,1] != sqr_size**2:
                    checker = 0
                    print ('!!!! The square size of the loaded file is wrong! change file or recalculate !!!!')
            except:
                Req = input(f'\n*********************************************************************\n No file <<{sqr_file}>> found!\n Want to recalculate all values [ReCalc], load a diffrent File [File] or stop [stop]?')
                print ('*********************************************************************\n')
                if Req == 'ReCalc':
                    ReCalcData = True
                    checker = 1
                elif Req == 'File':
                    sqr_file = input('\n What file [.gpkp] do you want to load:')
                else:
                    checker = 1
                    print('***** Exit *****\n')
                    sys.exit()
    #if no import of already calculated data is possible all raw data needs to be imported
    if ReCalcData :
        lst_calc_data = list(dic_gpkg_data.keys())
    
    print (f'----- The following data needs calculation: -----\n\n gpkg: {lst_calc_data}\n')
    
    #import and process .gpkg raw data
    
    lst_gpkg_raw = gpkg_importer(dic_gpkg_data, lst_calc_data, (data_path+data_energy_path+'/'))
    counter = 0
    for key in lst_calc_data:
        vars()[f'df_{key}'] = lst_gpkg_raw[counter]
        counter += 1
        
    del lst_gpkg_raw
    
    
    print ('\n=====================================================================')
    print ('----- Raw Data successful imported -----')
    print ('=====================================================================')
    
    #%% creating square map
    # square map will only be calculated when a recalculation (different square size, user wants that) is needed
    if ReCalcData:
        print ('\n=====================================================================')
        print (f'----- Creating Squared map with {sqr_size}x{sqr_size}m size -----')
        print ('=====================================================================')
        
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
        
        df_calc = pd.DataFrame(columns=['geometry', 'number'])
        counter = 0
        for k in tqdm(range(num_y+1)):
            for j in range(num_x+1):
                df_calc.loc[counter, 'geometry'] = shapely.geometry.Polygon([(lst_x_coords[j], lst_y_coords[k]), (lst_x_coords[j+1], lst_y_coords[k]), (lst_x_coords[j+1], lst_y_coords[k+1]), (lst_x_coords[j], lst_y_coords[k+1])])
                df_calc.loc[counter, 'number'] = counter
                counter += 1
                
        df_sqr = gpd.GeoDataFrame(df_calc.number, geometry=df_calc.geometry, crs='EPSG:2056')  
        
        print ('\n----- Erasing all squares outside switzerland -----')
        print ('\nThis takes time... \nno rush...')
        
        mask = df_sqr.geometry.intersects(border_poly)
        df_sqr = df_sqr[mask]
        df_sqr = df_sqr.reset_index(drop = True)
        print ('----- Done-----')
        
        lst_basic_columns = ['within_swiss', 'swiss_area']
        #create df_calc with correct multihead and geoDataFrame
        df_calc = df_multiHead(['Basic'], lst_basic_columns, ['source', 'data'], df_sqr.index, np.nan)
        df_calc = gpd.GeoDataFrame(df_calc, geometry=df_sqr.geometry, crs = 'EPSG:2056')
        #rename column of geometry
        df_calc = df_calc.rename(columns={'':'geometry'}, level=1)
        df_calc = df_calc.rename(columns={'geometry':'Basic'}, level=0)
        #reset geometry of df_calc
        df_calc = df_calc.set_geometry(('Basic', 'geometry'))
        print ('\n----- Calculate all basic map values -----')
        print ('\nThis takes time... \nno rush...')
        df_calc[('Basic','within_swiss')] = df_calc[('Basic','geometry')].within(border_poly)
        df_calc[('Basic','swiss_area')] = sqr_size**2
        print ('----- There is even more to calculate -----')
        
        for k in tqdm(range(len(df_calc))):
            if df_calc[('Basic','within_swiss')][k] == False:
                df_calc.loc[k,('Basic','swiss_area')] = round(df_calc[('Basic','geometry')][k].intersection(border_poly).area,0)
        
        if explore_raw_data:
            map_plotter(df_calc, 'Basic_map.html', map_path)
        
        del df_sqr, start_x, end_x, start_y, end_y, dist_x, dist_y, num_x, num_y, lst_x_coords, lst_y_coords
        
        print ('=====================================================================')
        print ('----- Squared map is ready to work with -----')
        print ('=====================================================================')
      
#%% calculating results and store it in square map
    if len(lst_calc_data) > 0:
        print ('=====================================================================')
        print ('----- Start to calculate raw Data -----')
        print ('=====================================================================')
        
        for key in lst_calc_data:
            my_class = getattr(rdc, key)
            df_sqr_data = my_class(pd.Series(df_calc[('Basic','geometry')]), vars()[f'df_{key}'], key)
            df_calc = pd.concat([df_calc, df_sqr_data.df_res], axis=1)
        
        print ('=====================================================================')
        print ('----- Done, I am happy for you! -----')
        print ('=====================================================================')
#%%Save the geodataframe
    if len(lst_calc_data) > 0:
        print ('=====================================================================')
        print ('----- Let us save that for later -----')
        print ('=====================================================================\n')
        
        #flatten the Geodataframe to save
        
        df_final = flatten_columns(df_calc.copy())
        df_final = df_final.set_geometry('Basic*geometry')
        
        #convert lists of the geo-df to strings
        for column in df_final.columns:
            # Check if the column contains lists
            if df_final[column].apply(lambda x: isinstance(x, list)).any():
                # Convert lists to comma-separated strings
                df_final[column] = df_final[column].apply(lambda x: ','.join(map(str, x)) if isinstance(x, list) else x)
                print(f"Column '{column}' converted from list to string.")
            
        #define the name of saved file
        final_file = f'sqr_data_swiss_{sqr_size}.gpkg'
        path = data_path+'square_maps/'+final_file
        #check if there exist already a file, if yes - rename it backup
        if os.path.exists(path):
            date_time_now = datetime.now().strftime('%Y%m%d_%H%M')
            final_file_new = f'backup_sqr{sqr_size}_{date_time_now}.gpkg'
            path_new = data_path+'square_maps/'+final_file_new
            os.rename(path, path_new)
           
        try:# Save GeoDataframe as File
        
            df_final.to_file(path, driver='GPKG')
            print('---- saving precious data ----\n')
        except:
            print('***** Please ensure you gave the correct name ***** \n!!! You need to run the < Save the geodataframe > again !!!')
            sys.exit()
        print ('=====================================================================')
        print (f'----- Successfully saved the the file << {final_file} >> -----')
        print ('=====================================================================\n')    
    
    #%% binary boundary conditions
    print ('=====================================================================')
    print ('----- Check if this case has been done before -----')
    print ('=====================================================================\n')
    bc_mask = df_bc_check.dic.apply(lambda x: x == GeoPATH.get_dic_energy())
    file_num = list(df_bc_check.index[bc_mask])  
    if len(file_num) == 0:
        print ('----- No calculated sqr_proof found -----')
    
        print ('=====================================================================')
        print (f'----- Apply the {lst_model[0]} to the raw data -----')
        print ('=====================================================================\n')
        #define model class according to user (an iteration over multiple energy models could be implemented here):
        model_class = getattr(esm, lst_model[0])
        es_model = model_class()
        
        #check if all needed raw data is available
        req_raw_data_bc = list(dict.fromkeys(es_model.lst_RDD))
        lst_calc_raw = df_calc.columns.levels[0].values.tolist()
        lost_raw_data = list(set(req_raw_data_bc) - set(lst_calc_raw))
        if lost_raw_data != []:
            print('*********************************************************************')
            print(f'WARNING: The following raw data has not been calculated:\n{lost_raw_data}')
            print('To find the error check\n-is there a class to calculate the raw data?\n-is there a raw data available in the correct directory?')
            print('*********************************************************************')
            sys.exit()
            
        # check if the raw data of the needed sources is present or needs to be loaded
        load_raw_gpkg = []
        for key in req_raw_data_bc:
            name_df = f'df_{key}'
            if name_df not in locals():
                load_raw_gpkg.append(key)
        # load the needed raw data
        if len(load_raw_gpkg) > 0:
            print ('=====================================================================')
            print (f'We need to load some raw data:\n{load_raw_gpkg}')
            print ('=====================================================================\n')
        lst_gpkg_raw = gpkg_importer(dic_gpkg_data, load_raw_gpkg, (data_path+data_energy_path+'/'))
        counter = 0
        for key in load_raw_gpkg:
            vars()[f'df_{key}'] = lst_gpkg_raw[counter]
            vars()[f'df_{key}'] = vars()[f'df_{key}'].set_geometry('geometry')   
            counter += 1
        del lst_gpkg_raw
        
        print ('=====================================================================')
        print ('----- Boundary conditions are filtered -----')
        print ('...')
        # use the function of binary boundary conditions
        # this brings back two dataframes: one with all sqares that fulfille 100% (df_proof1), the second (df_proof_q3) are all squares that are above 3th quantile of fullfilling the BC
        df_proof1, df_proof_q3 = es_model.binary_conditions(df_calc,True)
        # # print the map if wanted
        # if explore_raw_data:
        #     color_map_plotter([df_proof1, df_proof_q3], ['dodgerblue', 'orangered'], ['Aprooved', 'Further Check'], 
        #                       'basic_filter_map.html', map_path, display_columns= es_model.lst_binary_bc, dic_BC= es_model.dic_energy)
        lst_basic = [('Basic','geometry'), ('Basic','swiss_area'), ('Basic','within_swiss')]
        
        
        if len(df_proof_q3) > 0:
            print (f'----- Found {len(df_proof_q3)} squares that are not approved but look promising  -----')
            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            #the dataframe with the squares that not jet fulfille all BC is further checked:
            # only send df with basic information to the expander
            print ('----- check for more in an expanded area  -----')
            df_proof_q3_exp = sqr_expansion(df_proof_q3.loc[:,lst_basic], sqr_size_exp)
            #recalculate the raw data input in the expanded squares
            for key in req_raw_data_bc:
                my_class = getattr(rdc, key)
                df_sqr_data = my_class(df_proof_q3_exp[('Basic','geometry')], vars()[f'df_{key}'], key)
                df_proof_q3_exp = pd.concat([df_proof_q3_exp, df_sqr_data.df_res], axis=1)
            #send this dataframe again to the binary BC function, the returning DF are all extended squares that fullfille BC 100%
            print ('----- we will see if they now get approval -----')
            df_proof_q3_add = es_model.binary_conditions(df_proof_q3_exp,False)
            print (f'----- {len(df_proof_q3_add)} squares got additional approval -----')
            # if explore_raw_data:
            #     color_map_plotter([df_proof1, df_proof_q3, df_proof_q3_exp, df_proof_q3_add], ['dodgerblue', 'orangered', 'green', 'dodgerblue'], ['Aprooved', 'Further Check', 'Expanded', 'Exp_aprooved'], 
            #                       'BC_sqr_map.html', map_path, display_columns= es_model.lst_binary_bc, dic_BC= es_model.dic_energy)
                
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        #all of the areas in df_proof1 are expanded to a user defined limit
        print ('----- Expanding all areas so we dont miss any potential -----')
        df_proof1_exp = sqr_expansion(df_proof1.loc[:,lst_basic], sqr_size_exp)
        #recalculate the raw data input in the expanded squares
        for key in req_raw_data_bc:
            my_class = getattr(rdc, key)
            df_sqr_data = my_class(df_proof1_exp[('Basic','geometry')], vars()[f'df_{key}'], key)
            df_proof1_exp = pd.concat([df_proof1_exp, df_sqr_data.df_res], axis=1)
        
        if len(df_proof_q3) > 0:
            #fusion of df_proof1 and df_proof_q3_add
            df_proof_exp = pd.concat([df_proof1_exp, df_proof_q3_add], axis=0)
            df_proof_exp.sort_index(inplace = True)
        else:
            df_proof_exp = df_proof1_exp.copy()
        
        print ('----- Merging areas that overlap -----')
        # merge overlapping areas and create a final DataFrame
        df_proof = merge_touch_polygons(df_proof_exp.loc[:,('Basic','geometry')])
        # if the new polygons are bigger than the avg. Canton, cut them along the canton boarder
        max_poly_area = 2000  # km2
        # max_poly_area = 250  # km2
        # --------- IDENTIFY TOO BIG POLYGONS ----------
        condition = df_proof[('Basic', 'area_km2')] >= max_poly_area
        num_big_poly = condition.sum()
        
        if num_big_poly != 0:
            print(f'----- {num_big_poly} polygons are too big -----')
            print('----- Cutting them along canton borders -----')
        
            # Separate big polygons
            df_poly_big = df_proof[condition].copy()
            # Keep the rest
            df_proof = df_proof[~condition].copy()
        
            # Load canton boundaries
            df_canton = gpd.read_file(data_path + 'swissBOUNDARIES_canton.gpkg')
            # df_canton = gpd.read_file(data_path + 'swissBOUNDARIES_bezirk.gpkg')
            
            df_canton = df_canton.geometry
        
            result_list = []
        
            # --------- CUTTING PROCESS ----------
            for canton_idx, canton_geom in df_canton.items():
                for poly_idx, poly_geom in df_poly_big[('Basic', 'geometry')].items():
                    intersection = poly_geom.intersection(canton_geom)
        
                    if not intersection.is_empty:
                        # If the result is a MultiPolygon, split it
                        if intersection.geom_type == 'MultiPolygon':
                            for part in intersection.geoms:
                                result_list.append({
                                    ('Basic', 'geometry'): part,
                                    ('meta', 'canton_index'): canton_idx,
                                    ('meta', 'poly_index'): poly_idx
                                })
                        else:
                            result_list.append({
                                ('Basic', 'geometry'): intersection,
                                ('meta', 'canton_index'): canton_idx,
                                ('meta', 'poly_index'): poly_idx
                            })
        
            # --------- CREATE GeoDataFrame FROM RESULTS ----------
            result_gdf = gpd.GeoDataFrame(result_list, geometry=('Basic', 'geometry'))
            result_gdf.set_crs(df_canton.crs, inplace=True)
            # Compute area in km²
            result_gdf[('Basic', 'area_km2')] = result_gdf[('Basic', 'geometry')].area * 1e-6
            # Keep only relevant columns matching df_proof
            result_gdf = result_gdf[[('Basic', 'geometry'), ('Basic', 'area_km2')]]
            # --------- CONCATENATE BACK ----------
            df_proof = pd.concat([df_proof, result_gdf], ignore_index=True)
            df_proof = df_proof.reset_index(drop=True)
        
            print('----- Cutting finished, MultiPolygons exploded, and polygons updated -----')
            
        #recalculate the raw data input in the expanded squares
        for key in req_raw_data_bc:
            my_class = getattr(rdc, key)
            df_sqr_data = my_class(df_proof[('Basic','geometry')], vars()[f'df_{key}'], key)
            df_proof = pd.concat([df_proof, df_sqr_data.df_res], axis=1)
        
        # Create a mask for rows where any cell is None or NaN
        mask_none = df_proof.isna().any(axis=1) | (df_proof.applymap(lambda x: x is None)).any(axis=1)
        # Drop those rows
        df_proof = df_proof[~mask_none].reset_index(drop=True)
        
        if explore_raw_data:
            if len(df_proof_q3_add) != 0:
                color_map_plotter([df_proof1, df_proof_q3, df_proof_q3_exp, df_proof_q3_add, df_proof], ['dodgerblue', 'orangered', 'green', 'dodgerblue', 'yellow'], ['Aprooved', 'Further Check', 'Expanded', 'Exp_aprooved', 'Final_aprooved'], 
                              'BC_cluster_map.html', map_path, display_columns= es_model.lst_binary_bc, dic_BC= es_model.dic_energy)
            else:
                color_map_plotter([df_proof1, df_proof_q3, df_proof_q3_exp, df_proof], ['dodgerblue', 'orangered', 'green', 'yellow'], ['Aprooved', 'Further Check', 'Expanded', 'Final_aprooved'], 
                              'BC_cluster_map.html', map_path, display_columns= es_model.lst_binary_bc, dic_BC= es_model.dic_energy)
                    
                
        total_area = df_proof[('Basic','area_km2')].sum()
        print (f'----- Found an total area of {total_area} km2 with enough energy potential -----')
        print ('----- Done with Boundary Conditions -----')
        print ('=====================================================================')
        try:
            del df_proof1, df_proof1_exp, df_proof_exp, df_proof_q3, df_proof_q3_add, df_proof_q3_exp
        except:
            pass
        print ('=====================================================================')
        print ('----- Let us save that for later -----')
        print ('=====================================================================\n')
        
        #flatten the Geodataframe to save
        
        df_final = flatten_columns(df_proof.copy())
        df_final = df_final.set_geometry('Basic*geometry')
        
        #convert lists of the geo-df to strings
        for column in df_final.columns:
            # Check if the column contains lists
            if df_final[column].apply(lambda x: isinstance(x, list)).any():
                # Convert lists to comma-separated strings
                df_final[column] = df_final[column].apply(lambda x: ','.join(map(str, x)) if isinstance(x, list) else x)
                print(f"Column '{column}' converted from list to string.")
            
        #define the name of saved file
        file_num_new = len(df_bc_check)
        final_file = f'df_proof_{sqr_size}_{sqr_size_exp}_{file_num_new}.gpkg'
        path = data_path+'square_maps/'+final_file
        #check if there exist already a file, if yes - rename it backup
        if os.path.exists(path):
            date_time_now = datetime.now().strftime('%Y%m%d_%H%M')
            final_file_new = f'backup_df_proof_{sqr_size}_{sqr_size_exp}_{file_num_new}_{date_time_now}.gpkg'
            path_new = data_path+'square_maps/'+final_file_new
            os.rename(path, path_new)
           
        try:# Save GeoDataframe as File
        
            df_final.to_file(path, driver='GPKG')
            print('---- saving precious data ----\n')
        except:
            print('***** Please ensure you gave the correct name ***** \n!!! You need to run the < Save the geodataframe > again !!!')
            sys.exit()
        print(df_bc_check)
        df_bc_dummy = pd.DataFrame(columns = ['dic'], data = pd.Series([GeoPATH.get_dic_energy()]))
        df_bc_check = pd.concat([df_bc_check, df_bc_dummy], ignore_index=True)
        df_bc_check.to_csv(data_path + 'square_maps/' + f_name)
        print ('=====================================================================')
        print (f'----- Successfully saved the the file << {final_file} >> -----')
        print ('=====================================================================\n')
    
    # Load previous df_proof and raw data
    else:
        print ('=====================================================================')
        print ('----- Nice, df_proof has been calculated before! -----')
        print ('=====================================================================\n')
        #define model class according to user (an iteration over multiple energy models could be implemented here):
        model_class = getattr(esm, lst_model[0])
        es_model = model_class()
        
        # check which precalculated file has to be loaded
        file_num = file_num[0]
        proof_file     = f'df_proof_{sqr_size}_{sqr_size_exp}_{file_num}.gpkg'

        #check if all needed raw data is available
        req_raw_data_bc = list(dict.fromkeys(es_model.lst_RDD)) 
            
        # check if the raw data of the needed sources is present or needs to be loaded
        load_raw_gpkg = []
        for key in req_raw_data_bc:
            name_df = f'df_{key}'
            if name_df not in locals():
                load_raw_gpkg.append(key)
        # load the needed raw data
        if len(load_raw_gpkg) > 0:
            print ('=====================================================================')
            print (f'We need to load some raw data:\n{load_raw_gpkg}')
            print ('=====================================================================\n')
        lst_gpkg_raw = gpkg_importer(dic_gpkg_data, load_raw_gpkg, (data_path+data_energy_path+'/'))
        counter = 0
        for key in load_raw_gpkg:
            vars()[f'df_{key}'] = lst_gpkg_raw[counter]
            vars()[f'df_{key}'] = vars()[f'df_{key}'].set_geometry('geometry')   
            counter += 1
        del lst_gpkg_raw
        checker = 0
        print ('----- Looking for pre calculated data -----')
        while checker == 0:
            try:
                #import gpkp file sqr_file
                df_proof = gpd.read_file(data_path+'square_maps/'+proof_file)
                print ('----- Found pre calculated data! -----')
                print ('----- Unpacking and formating -----')
                #unpack all strings as lists or numbers
                # Iterate over each column in the DataFrame
                df_proof = convert_column_types(df_proof.copy())
                for column in df_proof.columns:
                    # Check if the column contains strings that could represent lists
                    if df_proof[column].apply(lambda x: isinstance(x, str) and ',' in x).any() or "ID" in column :
                        # Convert comma-separated strings back to lists
                        df_proof[column] = df_proof[column].apply(str_to_list)
                        print(f"Column '{column}' converted from string to list.")
                        df_proof[column] = convert_series_elements(df_proof[column])
        
                
                #unflatten the multicolumn header and name the two columns
                df_proof = unflatten_columns(df_proof.copy())
                df_proof.columns.names = ['source', 'data']
                #rename geometry column an asign it correctly
                df_proof = df_proof.rename(columns={np.nan:'geometry'}, level=1)
                df_proof = df_proof.rename(columns={'geometry':'Basic'}, level=0)
                df_proof = df_proof.set_geometry(('Basic', 'geometry'))
                
                #create a list of all raw data that is needed to import anyway
                lst_calculated_data = df_proof.columns.levels[0].values.tolist()
                lst_calc_data = list(set(list(dic_gpkg_data.keys()))-set(lst_calculated_data))
                
                checker = 1
                print ('----- Pre-calculated Data is ready! -----')
    
            except:
                Req = input(f'\n*********************************************************************\n No file <<{proof_file}>> found!\n Want to recalculate all values [ReCalc], load a diffrent File [File] or stop [stop]?')
                print ('*********************************************************************\n')
                if Req == 'ReCalc':
                    ReCalcData = True
                    checker = 1
                elif Req == 'File':
                    proof_file = input('\n What file [.gpkp] do you want to load:')
                else:
                    checker = 1
                    print('***** Exit *****\n')
                    sys.exit()
    
    #%% Main calculations (Placement Assessment, Supply+Demand, Connections, Placement Connection)
    map_path = data_path +'../03_Results/'+result_folder+'/'
    
    dic_par_iteration = GeoPATH.get_dic_par_iteration()
    # make a copy of all original user dictionaries that can be part of the sensitivity analsis
    dic_place_orig = copy.deepcopy(es_model.dic_place)
    dic_clust_orig = copy.deepcopy(es_model.dic_clust)
    dic_connect_orig = copy.deepcopy(es_model.dic_connect)
    dic_site_orig = copy.deepcopy(es_model.dic_site)
    
    # total needed raw data
    req_raw_data_all = list(dict.fromkeys(
        req_raw_data_bc
        + [k[0] for k in es_model.dic_obj.keys()]
        + list(es_model.dic_clust.keys())
        + es_model.lst_RCD
        + ([es_model.dic_site['value'][0]] if (isinstance(es_model.dic_site.get('value',None),tuple) and es_model.dic_site['value'][0] in es_model.lst_RDD) else [])))
    # check if the raw data of the needed sources is present or needs to be loaded
    load_raw_gpkg = []
    for key in req_raw_data_all:
        name_df = f'df_{key}'
        if name_df not in locals():
            load_raw_gpkg.append(key)
    # load the needed raw data
    if len(load_raw_gpkg) > 0:
        print ('=====================================================================')
        print (f'We need to load some raw data:\n{load_raw_gpkg}')
        print ('=====================================================================\n')
    lst_gpkg_raw = gpkg_importer(dic_gpkg_data, load_raw_gpkg, (data_path+data_energy_path+'/'))
    counter = 0
    for key in load_raw_gpkg:
        vars()[f'df_{key}'] = lst_gpkg_raw[counter]
        vars()[f'df_{key}'] = vars()[f'df_{key}'].set_geometry('geometry')   
        counter += 1
    del lst_gpkg_raw
    
    map_path_orig = map_path
    for o in dic_par_iteration.keys():
        lst_parameter = dic_par_iteration[o]['values']
        print('-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/')
        print(f'starting with {o}: {lst_parameter}')
        print('-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/-/\n')

        map_path = map_path_orig+o+'/'
        name_parameter = o
        model_class = getattr(esm, lst_model[0])
        es_model = model_class()
        
        # Reset all parameter to the original user dictionaries
        es_model.dic_place = copy.deepcopy(dic_place_orig)
        es_model.dic_clust = copy.deepcopy(dic_clust_orig)
        es_model.dic_connect = copy.deepcopy(dic_connect_orig)
        es_model.dic_site = copy.deepcopy(dic_site_orig)
        # Create subfolder for results 
        z = 0
        while True:
            suffix = f"_{z}" if z > 0 else ""
            buffered_result = result_folder + suffix
            try:
                Path(data_path + '../03_Results/' + buffered_result + '/' + o + '/').mkdir(parents=True, exist_ok=False)
                break
            except FileExistsError:
                z += 1
        

        
        
        # initialise result dataframe
        df_res_parameter = pd.DataFrame(columns= ['Total_Supply', 'Total_Demand', 'Avg_Cluster_Supply', 'Avg_Cluster_Demand', 
                                                  'Total_Connected', 'Total_Placed', 'Avg_Cluster_Connected', 'Avg_Cluster_Placed',
                                                  'Total_Value_Network', 'Avg_Value_Network', 'Median_Value_Network',
                                                  'Total_Distance_Network', 'Avg_Distance_Network', 'Median_Distance_Network',
                                                  'Avg_Distance/Value_Network', 'Median_Distance/Value_Network',
                                                  'Total_Distance_Site_Connections', 'Avg_Distance_Site_Connections', 'Median_Distance_Site_Connections',
                                                  'Total_Value_Placed_Energy_Systems', 'Avg_Value_Placed_Energy_Systems', 'Median_Value_Placed_Energy_Systems',
                                                  'Total_Area_Placed_Energy_Systems', 'Avg_Area_Placed_Energy_Systems', 'Median_Area_Placed_Energy_Systems',
                                                  'Avg_ValueFactor_Placed_Energy_Systems', 'Median_ValueFactor_Placed_Energy_Systems'
                                                      ], index = lst_parameter)
        for u in lst_parameter:
            
            # change the right parameter in the right dictionary
            path_iteration = dic_par_iteration[o]['path']
            dic_iteration = getattr(es_model, path_iteration[0])

            if len(dic_par_iteration[o]['path']) == 3:
                dic_iteration[path_iteration[1]][path_iteration[2]] = u
            elif len(dic_par_iteration[o]['path']) == 2:
                dic_iteration[path_iteration[1]] = u
            else:
                print('----- ERROR: False input in dic_par_iteration -----\n CHECK AND RESTART')
                sys.exit()
                        
            #check if u is a string and if so that it has no space in it
            def shorten_if_needed(u: str) -> str:
                if len(u) <= 20:
                    return u
                # if longer than 20, take first letters before each _
                parts = u.split('_')
                short_parts = [p[0] if p else '' for p in parts]
                return ''.join(short_parts)
            
            if isinstance(u, str):
                u_title = u
                if ' ' in u_title:
                    u_title = u_title.replace(' ', '_')
                if 'ü' in u:
                    u_title = u_title.replace('ü', 'ue')
                if 'Ü' in u:
                    u_title = u_title.replace('Ü', 'Ue')
                if 'ö' in u:
                    u_title = u_title.replace('ö', 'oe')
                if 'Ö' in u:
                    u_title = u_title.replace('Ö', 'Oe')
                if 'ä' in u:
                    u_title = u_title.replace('ä', 'ae')
                if 'Ä' in u:
                    u_title = u_title.replace('Ä', 'Ae')
                if ':' in u:
                    u_title = u_title.replace(':', '_')
                if '/' in u:
                    u_title = u_title.replace('/', '_')
                if '?' in u:
                    u_title = u_title.replace('?', '_')
                if '!' in u:
                    u_title = u_title.replace('!', '_')
                u_title = shorten_if_needed(u_title)
            else:
                u_title = u
            
            t = time.time()
           
            # import 1km2 map
            try :
                df_sqr_1km2 = gpd.read_parquet(data_path+'swiss_1km2_grid.parquet')
            except:
                print ('\n=====================================================================')
                print( '---ERROR---\n Swiss 1km2 grid file does not exist!\n Run the Code "swiss_grid_creator.py"\n or save the file "swiss_1km2_grid.parquet" in the Data-Folder! ')
                print ('\n=====================================================================')
                sys.exit(0)
            # create a dictionary with keys of proofed clusters, and as values there is a list
            # that contains all squares from sqr_1km2_map
            dic_sqr_req = dict.fromkeys(df_proof.index.tolist(), None)
            for key in dic_sqr_req:
                poly_bounds = df_proof.loc[key,('Basic', 'geometry')]
                dic_sqr_req[key] = df_sqr_1km2[(df_sqr_1km2['x']>= poly_bounds.bounds[0]) & 
                                               (df_sqr_1km2['y']>= poly_bounds.bounds[1]) & 
                                               (df_sqr_1km2['y']< poly_bounds.bounds[3]) & 
                                               (df_sqr_1km2['x']< poly_bounds.bounds[2])].index.tolist()
            
            print('\nChecking if all needed placement data is available')
            # check if all needed data is avialable
            req_place_data = list(dict.fromkeys(es_model.lst_RPD))
            for value in req_place_data:
                file_name = dic_gpkg_geo[value]
                if os.path.exists(data_path+data_placement_path+'/'+file_name):
                    print( f'----- found file <<{file_name}>> -----')
                else:
                    print ('\n=====================================================================')
                    print( f'---ERROR---\n The file <<{file_name}>> does not exist in folder {data_placement_path}!')
                    print(' Check for the file, restart <<Placement calculation>>')
                    print ('=====================================================================')
                    sys.exit(0)
                
            # initialise final result df
            final_columns = ['Supply', 'Demand', 'Connected_Demand_Supply', 'Placed_Energy_System']
            df_result = pd.DataFrame(0,columns = final_columns, index= df_proof.index)
            
            print( '¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦')
            print( '                    Start Evaluation of Potential                      ')
            print( '¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦')
            
            #DataFrame that loggs all proofed placement polygons
            # Create the MultiIndex
            index_array = [
                np.repeat(list(dic_sqr_req.keys()), len(req_place_data)),         
                np.tile(req_place_data, len(list(dic_sqr_req.keys()))),           
                np.tile(['Basic'], len(list(dic_sqr_req.keys())) * len(req_place_data)), 
                np.tile(['geometry'], len(list(dic_sqr_req.keys())) * len(req_place_data))  
            ]
            multi_index = pd.MultiIndex.from_arrays(index_array, names=['cluster', 'key', 'source', 'data'])
            # create final df with enough index for every possible outcome
            df_all_placement = pd.DataFrame(columns=multi_index, index = list(range(int(((sqr_size_exp/25)**2)/2))))
            del multi_index, index_array
            
            
            #DataFrame that loggs all Demand objs
            df_all_demand = pd.DataFrame(columns= ['value', 'geometry'])
            #DataFrame that loggs all Supply objs
            df_all_supply = pd.DataFrame(columns= ['value', 'geometry'])    
            #DataFrame that loggs all Networks
            df_all_networks = pd.DataFrame(columns= ['objs', 'value', 'distance', 'distance/value', 'geometry'])
            #DataFrame that loggs all placements
            df_all_sites = pd.DataFrame(columns= ['objs', 'value', 'value_factor', 'area_needed', 'area_found', 'cluster_no', 'geometry'])
            df_all_site_con = pd.DataFrame(columns= [ 'distance', 'geometry'])
            #DataFrame that loggs all possible placement sites
            df_all_possible_sites = pd.DataFrame(columns= ['geometry'])
            
            #DataFrame that loggs all objects without connections
            df_all_no_con = pd.DataFrame(columns= ['value', 'geometry'])
            #DataFrame that loggs all objects without placement site
            df_all_no_con_site = pd.DataFrame(columns= ['value', 'geometry'])
            
            
            # main iteration over every proofed square
            for key in dic_sqr_req:
                no_data_flag = False
                t_now=time.time()-t
                t_now_h = int(t_now/3600)
                t_now_m = int((t_now - t_now_h*3600)/60)
                t_now_s = int((t_now - t_now_h*3600 - t_now_m*60))
                print( '\n¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦')
                print( f'            Start Evaluation of Potential in Cluster {key} of {len(dic_sqr_req)-1}            ')
                print( f'      Time needed so far for {name_parameter}_{u_title} : {t_now_h}h {t_now_m}min {t_now_s}sec   ') 
                print( '¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦\n')
                #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # prepare raw data of this cluster
                # print( '----- Filter & Prepare Raw Data -----')
                #load the raw data needed and filter it
                for j in req_raw_data_all:
                    # only the objects that intersects with the current sqr
                    obj_req = df_proof.loc[key,(j,'obj_ID')]
                    vars()[f'df_now_{j}'] = vars()[f'df_{j}'].loc[obj_req,:]
                    # apply the boundary conditions to it
                    vars()[f'df_now_{j}'] = es_model.raw_bc_filter(vars()[f'df_now_{j}'], j)
                    # check if df_now has any objects left - if not skip the cluster
                    if len(vars()[f'df_now_{j}']) == 0:
                        no_data_flag = True
                        break
                    # apply the supply and demand defined multiplicator (user defined in dic_obj)
                    used_columns = [key_tuple  for key_tuple  in es_model.dic_obj.keys() if key_tuple [0] == j]
                    for keys_filter in used_columns:
                        vars()[f'df_now_{j}'].loc[:,keys_filter[1]] = vars()[f'df_now_{j}'].loc[:,keys_filter[1]]*es_model.dic_obj[keys_filter][1]  
                if no_data_flag:
                    print( '----- No raw Data found that fulfills BC -----')
                    print( '----- Skiping to the next Cluster -----')
                    continue
                # print( '----- Done, all raw data is ready -----')
                #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # load and prepare every raw placement data
                print( '----- Filter for Placement Sites -----')
                t1 = time.time()
    
                counter = 0
                for j in req_place_data:
                    file_name = data_path+data_placement_path+'/'+dic_gpkg_geo[j]
                    print( f'----- Import cluster data from <<{dic_gpkg_geo[j]}>> -----')
                    df_place_raw = pd.read_parquet(file_name, engine='pyarrow', filters=[('grid_number', 'in', dic_sqr_req[key])])
                    # convert geometry to readable shapely geometries
                    df_place_raw['geometry'] = shapely.from_wkb(df_place_raw['geometry'].values)
                    df_place_raw = gpd.GeoDataFrame(data=df_place_raw, geometry=df_place_raw['geometry'], crs= "EPSG:2056" )
                    # print( f'----- Start filter for the requirement of  <<{j}>> -----')
                    # send the geoDF to the class function, back comes a df with all proofed polygons
                    df_place_now = es_model.place_assesment(df_place_raw, j)
                    # ---------- Handle empty result ----------
                    if len(df_place_now) == 0:
                        print(f'!!!!! No valid geometries after filtering for <<{j}>>. !!!!!')
                        df_non = pd.DataFrame(df_place_now[('Basic', 'geometry')])
                        df_place = gpd.GeoDataFrame(data = df_non, geometry=[], crs="EPSG:2056")
                        df_place = df_place.set_geometry(df_place.columns[0])
                        df_place = df_place.drop(columns=df_place.columns[1])
                        del df_non
                        break 
                    # save the current placement to final df
                    df_all_placement[(key, j, 'Basic', 'geometry')] = df_place_now[('Basic', 'geometry')]
                    # check for the space where every placement requirement is fulfilled
                    if counter == 0:
                        df_place = gpd.GeoDataFrame(geometry= df_place_now[('Basic', 'geometry')], crs= "EPSG:2056")
                    else:        
                        # 1. Prepare GeoDataFrames
                        df_place = df_place.set_geometry('geometry').copy()
                        df_place_now = df_place_now.copy()
                        df_place_now['geometry'] = df_place_now[('Basic', 'geometry')]
                        df_place_now = df_place_now.set_geometry('geometry')
                        
                        # 2. Ensure CRS matches
                        if df_place.crs != df_place_now.crs:
                            df_place_now = df_place_now.to_crs(df_place.crs)
                        
                        # 3. Spatial join for bbox-intersecting pairs
                        joined = gpd.sjoin(df_place, df_place_now, how='inner', predicate='intersects')
                        
                        # 4. Matched geometry arrays
                        geoms_left = joined.geometry.values
                        geoms_right = df_place_now.geometry.iloc[joined.index_right].values
                        
                        # 5. Vectorized intersection (Shapely 2.x)
                        intersections = shapely.intersection(geoms_left, geoms_right)
                        
                        # 6. Filter empty
                        mask = ~shapely.is_empty(intersections)
                        final_intersections = intersections[mask]
                        
                        # 7. Overwrite df_place with intersection result
                        df_place = gpd.GeoDataFrame(
                            geometry=final_intersections,
                            crs=df_place.crs
                        ).reset_index(drop=True)
                        
                        # 8. Explode multipolygons to polygons
                        df_place = df_place.explode(ignore_index=True)
                        # 9. Keep only Polygon geometries
                        df_place = df_place[df_place.geometry.geom_type == "Polygon"].reset_index(drop=True)
                    
                    counter += 1
                t1 = time.time() - t1
                print(f'Needed {round(t1/60,2)} min to calculate')
                if len(df_all_possible_sites) == 0 and len(df_place) != 0:
                    df_all_possible_sites = df_place
                elif len(df_all_possible_sites) != 0 and len(df_place) != 0:
                    df_all_possible_sites = pd.concat([df_all_possible_sites, df_place], ignore_index=True)
                # save space and remove unneeded memory
                try:
                    del df_place_now, df_place_raw
                except:
                    pass
                
                #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # start building cluster according to cluster requirements
                print( '----- Cluster Objects -----')
                for obj_key, spec in es_model.dic_clust.items():
                    
                    key_now = (obj_key, spec['clustered_value'])  # old-style key for DBSCAN_cluster
                    print(f' building cluster out of <<{key_now[0]}>> ')
                               
                    vars()[f'df_unclust_{key_now[0]}'] = vars()[f'df_now_{key_now[0]}'].copy()
                    
                    df_clust = es_model.DBSCAN_cluster(vars()[f'df_now_{key_now[0]}'].copy(), key_now)
                    
                    vars()[f'df_now_{key_now[0]}'] = gpd.GeoDataFrame(df_clust, geometry=df_clust.geometry, crs='EPSG:2056')
                    print(f'----- Found {len(df_clust)} cluster-----')
                    del df_clust
                # print('----- DONE CLUSTERING -----')
                #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                """# Additional distinction between different energy types are needed! NOT IMPLEMENTED"""
                # calculate total demand and supply
                for key_now in es_model.dic_obj.keys():
                    df_dummy = pd.DataFrame(columns = ['value', 'geometry'])
                    # check if the current value has been clustered, if yes take the sum and not the list
                    if key_now[0] in es_model.dic_clust and es_model.dic_clust[key_now[0]]['clustered_value'] == key_now[1]:
                        # check if there is even one cluster in the df_now
                        if len(vars()[f'df_now_{key_now[0]}']) == 0:
                            col_now = pd.Series(data=[0])
                        else:
                            col_now = vars()[f'df_now_{key_now[0]}'].loc[:, key_now[1]+'_sum']
                    else:
                        col_now = vars()[f'df_now_{key_now[0]}'].loc[:, key_now[1]]
                    #check if the column has lists in it
                    contains_lists = col_now.apply(lambda x: isinstance(x, list)).any()
                    if contains_lists:
                        total_sum = sum(chain.from_iterable(col_now))
                        col_now = col_now.apply(sum)
                    else:
                        total_sum = col_now.sum()
                    
                    # save value in df_dummy
                    df_dummy['value'] = col_now.copy()
                    df_dummy['geometry'] = vars()[f'df_now_{key_now[0]}'].loc[:, 'geometry'].copy()
                    df_dummy = df_dummy.dropna()
                    df_dummy = df_dummy[df_dummy['value'] > 0]
                    
                    if es_model.dic_obj[key_now][0] == 'S':
                        df_result.loc[key,'Supply'] += total_sum
                        # add df_dummy to the df_all_supply
                        if not df_dummy.empty and not df_dummy.isna().all(axis=None):
                            df_all_supply = pd.concat([df_all_supply, df_dummy], ignore_index=True)
                    elif es_model.dic_obj[key_now][0] == 'D':
                        df_result.loc[key,'Demand'] += total_sum
                        # add df_dummy to the df_all_demand
                        if not df_dummy.empty and not df_dummy.isna().all(axis=None):
                            df_all_demand = pd.concat([df_all_demand, df_dummy], ignore_index=True)
                    else:
                        print('!!!!! Warning wrong declaration in dic_obj <<{key_now}>> !!!!!')
                        sys.exit()
                #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # start connecting according to connection requirements
                print( '----- Connecting Objects and Creating Networks-----')
                #prepare data to send it to network_handler
                #''''' needs to be implemented later on''''
                # check if the column has a list in it if yes use sum
                #'''''''''''''''''''''''''''''''''''''''''''''
                dic_df_now = {}
                for key_now in es_model.lst_RCD:
                    # check if the column has been clustered before - if yes overwrite the requirement with the _sum
                    if key_now in es_model.lst_RDClust:
                        for connection_num in es_model.dic_connect:
                        
                            if (es_model.dic_connect[connection_num]["demand"][0] == key_now 
                                and es_model.dic_connect[connection_num]["demand"][1] != "None"
                                and not es_model.dic_connect[connection_num]["demand"][1].endswith("_sum")):
                                
                                d = es_model.dic_connect[connection_num]['demand']
                                es_model.dic_connect[connection_num]["demand"] = (d[0], d[1] + "_sum", *d[2:])
                                del d
                            # check supply
                            if (es_model.dic_connect[connection_num]["supply"][0] == key_now 
                                and es_model.dic_connect[connection_num]["supply"][1] != "None"
                                and not es_model.dic_connect[connection_num]["supply"][1].endswith("_sum")):
                                
                                s = es_model.dic_connect[connection_num]['supply']
                                es_model.dic_connect[connection_num]["supply"] = (s[0], s[1] + "_sum", *s[2:])
                                del s
                            # check connectors
                            for q, conn in enumerate(es_model.dic_connect[connection_num]["connectors"]):
                                if conn[0] == key_now and conn[1] != "None" and not conn[1].endswith("_sum"):
                                    es_model.dic_connect[connection_num]["connectors"][q] = (conn[0], conn[1] + "_sum", *conn[2:])
                                    del conn, q
                                
                    dic_df_now[key_now] = vars()[f'df_now_{key_now}'].copy()
                # send all raw data to network_handler + maximum of total demand or supply
                max_needed_value = max(df_result.loc[key,'Demand'], df_result.loc[key,'Supply'])
                df_con_result = es_model.Network_Handler(dic_df_now.copy(), max_needed_value)
                df_con_result.drop(df_con_result[(df_con_result == 0).all(axis = 1)].index, inplace=True) 
                
                # store the total connected energy in results
                df_result.loc[key, 'Connected_Demand_Supply'] = df_con_result['Network_total', 'value'].sum()
                if not df_con_result.empty and not df_con_result.isna().all(axis=None) and len(es_model.dic_connect)!=0:
                    df_all_networks = pd.concat([df_all_networks, df_con_result['Network_total']])
                    
                    # store all objects without network seperatly but drop them in the df_now!
                    objs_con = df_con_result['Network_total']["objs"].values  # numpy array of dicts (fast iteration)
                    keys_con = objs_con[0].keys()  # all dicts share these keys
                    # Unique values per key, order not guaranteed (fast)
                    dic_found_con = {k: list(set(chain.from_iterable(d[k] for d in objs_con))) for k in keys_con}
                    for f in es_model.lst_RDD:
                        # create a dataframe with all objects that found no Network
                        vars()[f'df_no_con_{f}'] = vars()[f'df_now_{f}'].copy()
                        vars()[f'df_no_con_{f}'] = vars()[f'df_no_con_{f}'].drop(index = dic_found_con[f])
                        
                        if len(vars()[f'df_no_con_{f}']) != 0  and len(es_model.dic_connect) != 0: 
                            # erase all objects without from the basic dataframe
                            vars()[f'df_now_{f}'] = vars()[f'df_now_{f}'].drop(index = list(vars()[f'df_no_con_{f}'].index))
                    
                    df_all_networks.index = [f'Network_{i}' for i in range(len(df_all_networks))]
                    df_all_networks.drop(df_all_networks[(df_all_networks == 0).all(axis=1)].index, inplace=True)
                    
                else:
                    for f in es_model.lst_RDD:
                        # create a dataframe with all objects that found no Network
                        vars()[f'df_no_con_{f}'] = vars()[f'df_now_{f}'].copy()
                        if len(es_model.dic_connect) != 0:
                            vars()[f'df_now_{f}'] = vars()[f'df_now_{f}'].drop(index = list(vars()[f'df_no_con_{f}'].index))
                # add all objects without connection to the overall df_all_no_con
                for f in es_model.dic_obj.keys():
                    if len(vars()[f'df_no_con_{f[0]}']) != 0:
                        df_dummy = vars()[f'df_no_con_{f[0]}'][[f[1], 'geometry']].copy()
                        df_dummy.columns = ['value', 'geometry']
                        df_all_no_con = pd.concat([df_all_no_con, df_dummy], ignore_index=True)
                        del df_dummy
                
                print( '\n----- Done with Networks -----')
            
                #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # start placement of Energy System according to dic_site
                print( '----- Let us find some space to build that thing -----')
                print( '----- Connecting Site and Network -----')
                # prepare data of site places
                # check if there is any data in df_place
                if len(df_place) == 0:
                    print( '----- There is no space to set Energy System -----')
                    print( '----- Skiping to the next Cluster -----')
                    continue
                df_now_site = df_place.copy()
                df_now_site['area'] =  df_now_site['geometry'].area
                # prepare data of network
                if es_model.dic_site['value'][0] in df_con_result.columns:
                    df_value = pd.DataFrame(columns = ['value'], index= df_con_result.index)
                    df_value['value'] = df_con_result[es_model.dic_site['value'][0], 'value']
                    # if it is the network data and can be connected to the connection lines
                    geo_data_obj = es_model.dic_site['value'][1]
                    if geo_data_obj == 'None':
                        df_now_network = gpd.GeoDataFrame(data = df_value, 
                                                          geometry = df_con_result[es_model.dic_site['value'][0], 'geometry'], crs= 'EPSG:2056')
                    # if it is the network data but can only be connected to a specific object
                    elif geo_data_obj in dic_df_now.keys():
                        # collect geometry data
                        lst_geo = []
                        for b in df_con_result.index: 
                            lst_obj = df_con_result.loc[b, ('Network_total', 'objs')][geo_data_obj]
                            serie_geo = vars()[f'df_now_{geo_data_obj}'].loc[lst_obj, 'geometry']                
                            lst_geo.append(shapely.ops.unary_union(serie_geo))
                        df_now_network = gpd.GeoDataFrame(data = df_value, 
                                                          geometry = lst_geo, crs= 'EPSG:2056')
                    # if the user wrote something wrong
                    else:
                        print('!!!!! Warning wrong declaration in dic_site  <<value>> !!!!!')
                        sys.exit()
                else:
                    # check if the data wanted is from clustered data or not
                    geo_data_obj = es_model.dic_site['value'][0]
                    geo_data_column = es_model.dic_site['value'][1]
                    # is the data wanted even declared in dic_energy?
                    if geo_data_obj in es_model.lst_RDD:
                        df_value = pd.DataFrame(columns = ['value'], index= vars()[f'df_now_{geo_data_obj}'].index)
                        # is the choosen raw data clustered
                        if geo_data_obj in es_model.lst_RDClust:
                            # is the column clusterd
                            if geo_data_obj in es_model.dic_clust and es_model.dic_clust[geo_data_obj]['clustered_value'] == geo_data_column:
                                # ---- inserted 28.10.25 ----
                                if f"{geo_data_column}_sum" not in vars()[f'df_now_{geo_data_obj}'].columns:
                                    print(f"[WARN] Column {geo_data_column}_sum not found in df_now_{geo_data_obj}. Creating with zeros.")
                                    vars()[f'df_now_{geo_data_obj}'][f"{geo_data_column}_sum"] = 0.0
                                    
                                df_value['value'] = vars()[f'df_now_{geo_data_obj}'][geo_data_column+'_sum']
                                df_now_network = gpd.GeoDataFrame(data = df_value, 
                                                                  geometry = vars()[f'df_now_{geo_data_obj}']['geometry'], crs= 'EPSG:2056')
                            else:
                                print('!!!!! Warning wrong declaration in dic_site  <<value>> !!!!!')
                                print('!!!!! This column has not been clustered, but the rest has been !!!!!')
                                sys.exit()
                        # if the data is not clustered
                        else:
                            df_value['value'] = vars()[f'df_now_{geo_data_obj}'][geo_data_column]
                            df_value['geometry'] = vars()[f'df_now_{geo_data_obj}']['geometry']
                            df_value = df_value.dropna()
                            df_now_network = gpd.GeoDataFrame(data = df_value, geometry = df_value['geometry'], crs= 'EPSG:2056')
                    else:
                        print('!!!!! Warning wrong declaration in dic_site  <<value>> !!!!!')
                        print('!!!!! This Data is not part of the Requirements in dic_energy !!!!!')
                        sys.exit()
            
                # df_result_site for this cluster initilised
                df_res_site = pd.DataFrame(columns= ['objs', 'value', 'value_factor', 'area_needed', 'area_found', 'cluster_no', 'geometry'], index = df_now_network.index)
                df_res_site_con = pd.DataFrame(columns= ['distance', 'geometry'], index = df_now_network.index)
                # only try to place energy system if there are objects or sites to place
                if len(df_now_network)>0 or not len(df_now_site)>0:
                    # start for loop over each network-object
                    for net in df_now_network.index:
                        value_fact = 1
                        value_fact_increment = 0.2
                        while value_fact >= es_model.dic_site['min_value_factor']:
                            # calculate max distance with current object and factor
                            if es_model.dic_site['value_distance']:
                                max_dist_site = df_now_network.loc[net, 'value']*es_model.dic_site['distance']*value_fact*es_model.dic_site['value_factor']
                            else:
                                max_dist_site = es_model.dic_site['distance']*value_fact*es_model.dic_site['value_factor']
                            if es_model.dic_site['max_distance'] != 'None':
                                max_dist_site = min(max_dist_site, es_model.dic_site['max_distance'])
                            # calculate min area needed to install site
                            min_area_site = (df_now_network.loc[net, 'value']*value_fact*es_model.dic_site['value_factor'])/es_model.dic_site['space']
                            # filter out all placement polygons which are already to small
                            df_site = df_now_site[df_now_site['area']>= min_area_site].copy()
                            if len(df_site) == 0:
                                print(f'------ No Site found for Energy System {net} in Cluster {key} -----')
                                break
                            # buffer zone around the network object (multilinestring, multipoint, point, linestring, polygon or multipolygon)
                            geo_buffer = df_now_network.loc[net, 'geometry'].buffer(max_dist_site)
                            # intersect between df_proof_now und buffer zone
                            df_dummy = pd.DataFrame(columns=['area'])
                            geo_intersect = df_site.geometry.intersection(geo_buffer)
                            # calculate area of each intersection polygon
                            df_dummy['area'] = geo_intersect.area
                            # save each intersection polygon in df
                            df_site_intersect = gpd.GeoDataFrame(data=df_dummy, geometry=geo_intersect, crs='EPSG:2056')
                            
                            # Check if any GeometryCollections are in df_site_intersect
                            if (df_site_intersect.geometry.geom_type == 'GeometryCollection').any():
                                df_site_intersect = explode_geometrycollections(df_site_intersect)
                            
                            # filter all out that have an area smaller than needed
                            df_site_intersect = df_site_intersect[df_site_intersect['area']>= min_area_site]                                                                      
                            if len(df_site_intersect) == 0:
                                value_fact -= value_fact_increment
                            else:
                                # check each possible site if it is dominated by thin long arms or compact (outher circle methode)
                                idx_drop = []
                                ratio_limit = 2.5
                                for site in df_site_intersect.index:
                                    result = covering_circle(df_site_intersect.loc[site, 'geometry'])
                                    new_limit = (result['polygon_area']/min_area_site)*ratio_limit
                                    if result['area_ratio'] > new_limit:
                                        idx_drop.append(site)
                                # drop the sites not getting below limit
                                df_site_intersect = df_site_intersect.drop(idx_drop)
                                # if there are some polygons left
                                if len(df_site_intersect) > 0:
                                    # choose the polygon with the smallest possible (if there are multiple equale ones, it takes just the first)
                                    site_choosen = df_site_intersect.loc[df_site_intersect['area'].idxmin()]['geometry']
                                    # erase the choosen polygon from the df_now_site
                                    geo_site_new = df_now_site.geometry.difference(site_choosen)
                                    df_dummy = pd.DataFrame(columns=['area'])
                                    df_dummy['area'] = geo_site_new.area
                                    df_dummy['geometry'] = geo_site_new
                                    df_now_site = gpd.GeoDataFrame(data=df_dummy, geometry=df_dummy['geometry'], crs='EPSG:2056')
                                    df_now_site = df_now_site.explode(ignore_index=True)
                                    df_now_site = df_now_site[df_now_site.geometry.geom_type == "Polygon"].reset_index(drop=True)
                                    # save the path between the objects in Network_df (add to existing Multilinestring or store it as new)
                                    con_line = connect_geometries_by_shortest_distance([site_choosen, df_now_network.loc[net, 'geometry']])[0]
                                    df_res_site_con.loc[net,'geometry'] = con_line
                                    df_res_site_con.loc[net,'distance'] = con_line.length
                                    # save the site information
                                    df_res_site.loc[net,'geometry'] = site_choosen
                                    df_res_site.loc[net,'objs'] = net
                                    df_res_site.loc[net,'value'] = df_now_network.loc[net, 'value']*value_fact*es_model.dic_site['value_factor']
                                    df_res_site.loc[net,'value_factor'] = value_fact
                                    df_res_site.loc[net,'area_found'] = site_choosen.area
                                    df_res_site.loc[net,'area_needed'] = min_area_site
                                    df_res_site.loc[net,'cluster_no'] = key
                                    break
                                else:
                                    value_fact -= value_fact_increment
                    
                    #drop all rows which no site was found
                    df_res_site = df_res_site.dropna()
                    df_res_site_con = df_res_site_con.dropna()
                    
                    df_res_site = gpd.GeoDataFrame(data = df_res_site, geometry=df_res_site['geometry'], crs ='EPSG:2056')
                    df_res_site_con = gpd.GeoDataFrame(data = df_res_site_con, geometry=df_res_site_con['geometry'], crs ='EPSG:2056')
                    # store the total connected energy in results
                    df_result.loc[key, 'Placed_Energy_System'] = df_res_site['value'].sum()
                    if df_res_site['value'].sum() != 0:
                        df_all_sites = pd.concat([df_all_sites, df_res_site], ignore_index=True)
                        df_all_sites.index = [f'Site_{i}' for i in range(len(df_all_sites))]
                        df_all_site_con = pd.concat([df_all_site_con, df_res_site_con], ignore_index=True)
                        df_all_site_con.index = [f'Site_{i}' for i in range(len(df_all_site_con))]
                        print( '----- Placed everythig I can -----')
                        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                        # start saving this region as map
                        print( '----- Saving this Regions Map -----')
                        
                        # find networks without placement site
                        lst_found_site = df_res_site['objs'].unique().tolist()
                        
                        # prep data
                        lst_data_plot = []
                        lst_data_names = []
                        for f in es_model.lst_RDD:
                            if len(vars()[f'df_no_con_{f}']) != 0 : 
                                name_str = f'{f} no Network'
                                lst_data_plot.append(vars()[f'df_no_con_{f}'])
                                lst_data_names.append(name_str)

                            # filter for objects without placement site
                            if es_model.dic_site['value'][0] == f:
                                vars()[f'df_no_site_{f}'] = vars()[f'df_now_{f}'].copy()
                                vars()[f'df_no_site_{f}'] = vars()[f'df_no_site_{f}'].drop(index = lst_found_site, errors = 'ignore')
                                if len(vars()[f'df_no_site_{f}']) != 0 : 
                                    name_str = f'{f} no Placement'
                                    lst_data_plot.append(vars()[f'df_no_site_{f}'])
                                    lst_data_names.append(name_str)
                                    #add the objects without site to the overall df_all_no_con_site
                                    df_dummy = vars()[f'df_no_site_{f}'][[es_model.dic_site['value'][1], 'geometry']].copy()
                                    df_dummy.columns = ['value', 'geometry']
                                    df_all_no_con_site = pd.concat([df_all_no_con_site, df_dummy], ignore_index=True)
                                    del df_dummy
                                            
                                    # erase all objects without from the basic dataframe
                                    vars()[f'df_now_{f}'] = vars()[f'df_now_{f}'].drop(index = list(vars()[f'df_no_site_{f}'].index))
                        
                            lst_data_plot.append(vars()[f'df_now_{f}'])
                            lst_data_names.append(f)    

                        lst_data_names.append('Placement_Site')
                        lst_data_names.append('Placement_Connection')
                        lst_data_plot.append(df_res_site)
                        lst_data_plot.append(df_res_site_con)
            
                        if len(df_con_result) != 0:
                            df_dummy = pd.DataFrame(columns = ['value', 'Network', 'geometry'])
                            multi_cols = pd.MultiIndex.from_product([['Network_total'], ['value', 'geometry']])
                            df_dummy[['value', 'geometry']] = df_con_result[multi_cols]
                            df_dummy['Network'] = df_dummy.index
                            gdf_con_result = gpd.GeoDataFrame(data = df_dummy, geometry= df_dummy.geometry, crs ='EPSG:2056')
                            final_map_plotter(lst_data_plot,f'Region_map_{key}_{name_parameter}_{u_title}.html',
                                          map_path, add_layer_df=[gdf_con_result, 'Network'], layer_name = lst_data_names, open_map=False)
                        
                        else:
                            final_map_plotter(lst_data_plot,f'Region_map_{key}_{name_parameter}_{u_title}.html', 
                                          map_path, layer_name = lst_data_names, open_map=False)
                            
            t=time.time()-t
            print(f'----- Time needed for all calulations: {round(t/60,2)} min -----\n')    
            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # create overall graphic of Switzerland
            print( '----- Creating detailed CH-Plot as html-----')
        
            gdf_sites = gpd.GeoDataFrame(data = df_all_sites[['value', 'cluster_no']], geometry= df_all_sites.geometry, crs ='EPSG:2056')
            gdf_demand = gpd.GeoDataFrame(data = df_all_demand['value'], geometry = df_all_demand.geometry, crs ='EPSG:2056')
            gdf_supply = gpd.GeoDataFrame(data = df_all_supply['value'], geometry = df_all_supply.geometry, crs ='EPSG:2056')
            gdf_site_con = gpd.GeoDataFrame(data = df_all_site_con['distance'], geometry = df_all_site_con.geometry, crs='EPSG:2056') 
            gdf_con = gpd.GeoDataFrame(data = df_all_networks[['distance', 'value']], geometry = df_all_networks.geometry, crs='EPSG:2056') 
            gdf_no_con = gpd.GeoDataFrame(data = df_all_no_con['value'], geometry = df_all_no_con.geometry, crs='EPSG:2056') 
            gdf_no_site = gpd.GeoDataFrame(data = df_all_no_con_site['value'], geometry = df_all_no_con_site.geometry, crs='EPSG:2056') 


            
            # final_map_plotter([gdf_demand, gdf_supply, gdf_sites, gdf_site_con],f'Distribution_results_detailed_{name_parameter}_{u_title}.html', map_path, layer_name = ['Demand', 'Supply', 'Placed Energy Systems', 'Placement Connections', 'Network Connections'], open_map=False)
            # del gdf_demand, gdf_supply, gdf_sites, gdf_site_con
            final_map_plotter([gdf_demand, gdf_supply, gdf_sites, gdf_site_con, gdf_con, gdf_no_con, gdf_no_site],f'Distribution_results_detailed_{name_parameter}_{u_title}.html', map_path, 
                              layer_name = ['Demand', 'Supply', 'Placed Energy Systems', 'Placement Connections', 'Network Connections', 'No Network', 'No Placement'], open_map=False)
            del gdf_demand, gdf_supply, gdf_sites, gdf_site_con, gdf_con, gdf_no_con, gdf_no_site
            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # create overall graphic of Switzerland NEW VERSION
            print( '----- Creating CH-Plot as png-----')
            img = mpimg.imread(data_path + 'swiss_map.png')
            img_height, img_width = img.shape[0], img.shape[1]
            
            # Bounding box from QGIS
            xmin, ymin, xmax, ymax = [2475742.2504, 1073233.2854, 2839210.4888, 1297873.7295]
            # Conversion function (CRS → pixel space)
            def crs_to_pixel(x_crs, y_crs):
                x_pix = (x_crs - xmin) / (xmax - xmin) * img_width
                y_pix = img_height - ((y_crs - ymin) / (ymax - ymin) * img_height)
                return x_pix, y_pix
            # Plot function for any geometry layer
            def plot_geometry_layer(geometry_series, color, alpha, label):
                for geom in geometry_series:
                    if geom.is_empty:
                        continue
                    
                    if geom.geom_type == 'Point':
                        x_pix, y_pix = crs_to_pixel(geom.x, geom.y)
                        ax.plot(x_pix, y_pix, 'o', color=color, markersize=2.5, alpha=alpha, label=label)
            
                    elif geom.geom_type in ['Polygon', 'MultiPolygon']:
                        try:
                            x, y = geom.exterior.xy
                            x_pix, y_pix = crs_to_pixel(np.array(x), np.array(y))
                            ax.fill(x_pix, y_pix, color=color, alpha=alpha, label=label)
                        except:
                            for poly in geom.geoms:
                                x, y = poly.exterior.xy
                                x_pix, y_pix = crs_to_pixel(np.array(x), np.array(y))
                                ax.fill(x_pix, y_pix, color=color, alpha=alpha, label=label)
            
                    elif geom.geom_type in ['LineString', 'MultiLineString']:
                        try:
                            x, y = geom.xy
                            x_pix, y_pix = crs_to_pixel(np.array(x), np.array(y))
                            ax.plot(x_pix, y_pix, color=color, linewidth=1.5, alpha=alpha, label=label)
                        except:
                            for line in geom.geoms:
                                x, y = line.xy
                                x_pix, y_pix = crs_to_pixel(np.array(x), np.array(y))
                                ax.plot(x_pix, y_pix, color=color, linewidth=1.5, alpha=alpha, label=label)
                                
            min_demand = round(df_all_demand['value'].min()*fac_SI_unit, 0)
            max_demand = round(df_all_demand['value'].max()*fac_SI_unit, 0)
            mean_demand = round(df_all_demand['value'].mean()*fac_SI_unit, 0)
            var_demand = round(df_all_demand['value'].var()*fac_SI_unit, 2)
            
            min_supply = round(df_all_supply['value'].min()*fac_SI_unit, 0)
            max_supply = round(df_all_supply['value'].max()*fac_SI_unit, 0)
            mean_supply = round(df_all_supply['value'].mean()*fac_SI_unit, 0)
            var_supply = round(df_all_supply['value'].var()*fac_SI_unit, 2)
            
            min_placed = round(df_all_sites['value'].min()*fac_SI_unit, 0)
            max_placed = round(df_all_sites['value'].max()*fac_SI_unit, 0)
            mean_placed = round(df_all_sites['value'].mean()*fac_SI_unit, 0)
            var_placed = round(df_all_sites['value'].var()*fac_SI_unit, 2)
            
            # Plot image
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.imshow(img)
            ax.set_axis_off()
            titel_stats = 'Stats: max [{res_unit}]/ min [{res_unit}]/ mean [{res_unit}]/ var\n'
            titel_demand = f'Demand: {max_demand}/ {min_demand}/ {mean_demand}/ {var_demand}\n'
            titel_supply = f'Supply: {max_supply}/ {min_supply}/ {mean_supply}/ {var_supply}\n'
            titel_placed = f'Placed: {min_placed}/ {max_placed}/ {mean_placed}/ {var_placed}'
            
            ax.set_title(titel_stats+titel_demand+titel_supply+titel_placed)
            
            # Plot the 3 layers
            plot_geometry_layer(df_all_demand.geometry, color='red', alpha=0.4, label='Demand')
            plot_geometry_layer(df_all_supply.geometry, color='blue', alpha=0.4, label='Supply')
            plot_geometry_layer(df_all_sites.geometry, color='green', alpha=0.4, label='Sites')
            
            red_patch = matplotlib.patches.Patch(color='red', label='Demand', alpha=0.4)
            blue_patch = matplotlib.patches.Patch(color='blue', label='Supply', alpha=0.4)
            green_patch = matplotlib.patches.Patch(color='green', label='Sites', alpha=0.4)
            
            ax.legend(handles=[red_patch, blue_patch, green_patch], framealpha=1, fontsize=8)
            print( '----- Saving that big png file -----')
            plt.savefig(map_path + f'Distribution_results_detailed_{name_parameter}_{u_title}.png', dpi=400, bbox_inches='tight', pad_inches=0)
            plt.close(fig)
            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # create overall graphic of Switzerland circles
            print( '----- Creating CH-Plot-Circle as png-----')
            radius_max = 2500
            radius_min = 100
            max_all = max(max_demand, max_supply, max_placed)
            min_all = min(min_demand, min_supply, min_placed)
            
            demand_centroid = df_all_demand['geometry'].apply(lambda geom: geom.centroid)
            supply_centroid = df_all_supply['geometry'].apply(lambda geom: geom.centroid)
            placed_centroid = df_all_sites['geometry'].apply(lambda geom: geom.centroid)
            
            demand_radius = (df_all_demand['value'] - min_all) / (max_all - min_all) * (radius_max - radius_min) + radius_min
            supply_radius = (df_all_supply['value'] - min_all) / (max_all - min_all) * (radius_max - radius_min) + radius_min
            placed_radius = (df_all_sites['value'] - min_all) / (max_all - min_all) * (radius_max - radius_min) + radius_min
        
            factor_scale =  radius_max/max_all
            demand_geometry = pd.Series([geom.buffer(dist) for geom, dist in zip(demand_centroid, demand_radius)])
            supply_geometry = pd.Series([geom.buffer(dist) for geom, dist in zip(supply_centroid, supply_radius)])
            placed_geometry = pd.Series([geom.buffer(dist) for geom, dist in zip(placed_centroid, placed_radius)])
            # Plot image
            fig, ax = plt.subplots(figsize=(10, 8))
            ax.imshow(img)
            ax.set_axis_off()
            titel_stats = 'Stats: max [{res_unit}]/ min [{res_unit}]/ mean [{res_unit}]/ var\n'
            titel_demand = f'Demand: {max_demand}/ {min_demand}/ {mean_demand}/ {var_demand}\n'
            titel_supply = f'Supply: {max_supply}/ {min_supply}/ {mean_supply}/ {var_supply}\n'
            titel_placed = f'Placed: {min_placed}/ {max_placed}/ {mean_placed}/ {var_placed}'
            
            ax.set_title(titel_stats+titel_demand+titel_supply+titel_placed)
        
            # Plot the 3 layers
            plot_geometry_layer(demand_geometry, color='red', alpha=0.4, label='Demand')
            plot_geometry_layer(supply_geometry, color='blue', alpha=0.4, label='Supply')
            plot_geometry_layer(placed_geometry, color='green', alpha=0.4, label='Sites')
            
            red_patch = matplotlib.patches.Patch(color='red', label='Demand', alpha=0.4)
            blue_patch = matplotlib.patches.Patch(color='blue', label='Supply', alpha=0.4)
            green_patch = matplotlib.patches.Patch(color='green', label='Sites', alpha=0.4)
            
            ax.legend(handles=[red_patch, blue_patch, green_patch], framealpha=1, fontsize=8)
            print( '----- Saving that big png file -----')
            plt.savefig(map_path + f'Distribution_results_{name_parameter}_{u_title}.png', dpi=400, bbox_inches='tight', pad_inches=0)
            plt.close(fig)
            del demand_geometry, supply_geometry, placed_geometry
            #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # create overall plots
            print(f'----- Start creating region_pdf for {name_parameter} {u_title}-----\n')
            pdf_name = f'Region_result_plots_{name_parameter}_{u_title}.pdf'
            with PdfPages(map_path+pdf_name) as pdf:
                #''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
                # Create bar plot for df_results
                unit_scale = fac_SI_unit
                fig, ax = plt.subplots(figsize=(12, 8))
            
                # Bar positions
                x = np.arange(len(df_result.index))
                width = 0.35
                width_center = 0.7
            
                # Plot bars
                # ax.bar(x - width/2, (df_result['Supply'] * unit_scale), width, label='Total Supply', color='lightblue')
                ax.bar(x + width, (df_result['Demand'] * unit_scale), width, label='Total Demand', color='lightcoral')
                # ax.bar(x, (df_result['Connected_Demand_Supply'] * unit_scale), width_center, 
                       # label='Connected Supply & Demand', color='blue', alpha=0.6)
                ax.bar(x, (df_result['Placed_Energy_System'] * unit_scale), width_center, 
                       label='Placed Energy System', color='green', alpha=0.6)
            
                # Labels and titles
                ax.set_title('All Region Results (Grouped)')
                ax.set_ylabel(f'{res_unit_type} [{res_unit}]')
                ax.set_xlabel('Region')
            
                # Keep all ticks, reduce labels
                ax.set_xticks(x)
            
                labels = [label if (i % 5 == 0) else '' for i, label in enumerate(df_result.index)]
                ax.set_xticklabels(labels)
                ax.set_xlim(-0.7, len(x) - 0.3)
            
                # Legend and tight layout
                ax.legend(loc='best')
                plt.tight_layout()
                
                # Save to PDF
                pdf.savefig(fig)
                plt.close(fig)
                #''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
                # # Create bar plots for df_all_networks
                # columns_to_plot = ['value', 'distance', 'distance/value']
                # for col in columns_to_plot:
                #     if col == 'value':
                #         unit_scale = 10**-3 
                #         unit = '[MWh]'
                #     elif col == 'distance':
                #         unit_scale = 1
                #         unit = '[m]'
                #     elif col == 'distance/value':
                #         unit_scale = 10**3
                #         unit = '[m/MWh]'
            
                #     fig, ax = plt.subplots(figsize=(12, 8))
                    
                #     #  Bar positions
                #     x = np.arange(len(df_all_networks.index))
                #     width_center = 0.7
            
                #     #  Plot
                #     ax.bar(
                #         x,
                #         (df_all_networks[col] * unit_scale),
                #         width_center,
                #         label=col,
                #         color='lightblue',
                #         alpha=0.8
                #     )
            
                #     #  Labels and title
                #     ax.set_title(f'{col} per connection')
                #     ax.set_ylabel(f'{col} (scaled)' if col == 'value' else col)
                #     ax.set_xlabel('Connection')
            
                #     #  Keep all ticks but only show every 5th label
                #     ax.set_xticks(x)
                #     labels = [label if (i % 5 == 0) else '' for i, label in enumerate(df_all_networks.index)]
                #     ax.set_xticklabels(labels)
            
                #     #  Legend and tight layout
                #     ax.legend(loc='best')
                #     plt.tight_layout()
            
                #     #  Save each plot to PDF
                #     pdf.savefig(fig)
                #     plt.close(fig)
                #''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
                # Sort dfs for keeping the same order:
                df_all_sites = df_all_sites.sort_values(by='value', ascending=True)
                df_all_site_con = df_all_site_con.reindex(df_all_sites.index)
                
                # Create bar plots for df_all_site_con
                columns_to_plot = ['distance']
                for col in columns_to_plot:
                    if col == 'distance':
                        unit_scale = 1 
                        unit = '[m]'
                    
                    fig, ax = plt.subplots(figsize=(12, 8))
                    
                    #  Bar positions
                    x = np.arange(len(df_all_site_con.index))
                    width_center = 0.7
            
                    #  Plot
                    ax.bar(
                        x,
                        (df_all_site_con[col] * unit_scale),
                        width_center,
                        label=col,
                        color='lightblue',
                        alpha=0.8
                    )
            
                    #  Labels and title
                    # ax.set_title(f'{col} to connect network and placement site')
                    ax.set_title('Distance to connect network and placement site')
                    # ax.set_ylabel(f'{col} {unit}')
                    ax.set_ylabel(f'Distance {unit}')
                    ax.set_xlabel('Placement Site')
                    
                    # Grid
                    # ax.grid(True)
                    ax.grid(True, which='major', axis='y', color='gray', linestyle='-', linewidth=0.4, alpha=0.3)
                    ax.yaxis.set_major_locator(MaxNLocator(nbins=20))
            
                    #  Keep all ticks but only show every 5th label
                    ax.set_xticks(x)
                    # labels = [label if (i % 5 == 0) else '' for i, label in enumerate(df_all_sites.index)]
                    # ax.set_xticklabels(labels)
                    ax.set_xticklabels(df_all_sites.index, rotation=45, ha='right', fontsize=6)
                    ax.set_xlim(-0.7, len(x) - 0.3)
                    
                    #  Legend and tight layout
                    plt.tight_layout()
            
                    #  Save each plot to PDF
                    pdf.savefig(fig)
                    plt.close(fig)
            
                #''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
                # Create bar plots for df_all_sites
                
                # Sort once by 'value' and reuse this ordering for all plots
                # df_all_sites = df_all_sites.sort_values(by='value', ascending=True)   # sorted at the beginning
    
                columns_to_plot = ['value', 'area_found', 'area_needed']
                for col in columns_to_plot:
                    if col == 'value':
                        unit_scale = fac_SI_unit
                        unit = f'[{res_unit}]'
                        title_dummy = res_unit_type
                    elif col == 'value_factor':
                        unit_scale = 1
                        unit = '[-]'
                        title_dummy = "Coverage"
                    elif col == 'area_needed':
                        unit_scale = 10**-6
                        unit = '[km²]'
                        title_dummy = "Area needed for Site"
                    elif col == 'area_found':
                        unit_scale = 10**-6
                        unit = '[km²]'
                        title_dummy = "Area found for Site"
                    fig, ax = plt.subplots(figsize=(12, 8))
                    
                    #  Bar positions
                    x = np.arange(len(df_all_sites.index))
                    width_center = 0.7
                    # Define label
                    if col == 'area_needed':
                        label = "Area Site"
                    elif col == 'area_found':
                        label = "Area found to build Site"
                    else:
                        label = col
                    #  Plot
                    ax.bar(
                        x,
                        (df_all_sites[col] * unit_scale),
                        width_center,
                        label=label,
                        color='lightblue',
                        alpha=0.8
                    )
                    
                    # Add horizontal line ONLY for area plot
                    if col in ['area_needed', 'area_found']:
                        threshold_value = 0.014  # km²
                        ax.axhline(y=threshold_value, color='red', linestyle='--', linewidth=0.8, label='Existing Pit Storage Reference')
                        ax.legend()
                        
                            
                    #  Labels and title
                    ax.set_title(f'{title_dummy} of the placement site')
                    ax.set_ylabel(f'{title_dummy} {unit}')
                    ax.set_xlabel('Placement Site')
                    
                    # Grid
                    # ax.grid(True)
                    ax.grid(True, which='major', axis='y', color='gray', linestyle='-', linewidth=0.4, alpha=0.3)
                    ax.yaxis.set_major_locator(MaxNLocator(nbins=20))
    
                    #  Keep all ticks but only show every 5th label
                    ax.set_xticks(x)
                    # labels = [label if (i % 5 == 0) else '' for i, label in enumerate(df_all_sites.index)]
                    # ax.set_xticklabels(labels)
                    ax.set_xticklabels(df_all_sites.index, rotation=45, ha='right', fontsize=6)
                    ax.set_xlim(-0.7, len(x) - 0.3)
                    
                    #  Legend and tight layout
                    plt.tight_layout()
            
                    #  Save each plot to PDF
                    pdf.savefig(fig)
                    plt.close(fig)
                    
                    
                    
                ######################## repeating plots for analysis (having NOT the original Site numeration) ###########
                # Sort dfs for keeping the same order:
                df_all_sites_cop = df_all_sites.sort_values(by='value', ascending=True).copy() # Sort df_all_sites by 'value'
                df_all_site_con_cop = df_all_site_con.loc[df_all_sites_cop.index].copy() # Use its new index to reindex the other DataFrame
                new_index = [f"Site_{i+1}" for i in range(len(df_all_sites_cop))] # Now reset to clean indices like Site_1, Site_2
                df_all_sites_cop.index = new_index
                df_all_site_con_cop.index = new_index
    
                
                # Create bar plots for df_all_site_con_cop
                columns_to_plot = ['distance']
                for col in columns_to_plot:
                    if col == 'distance':
                        unit_scale = 1 
                        unit = '[m]'
                    
                    fig, ax = plt.subplots(figsize=(12, 8))
                    
                    #  Bar positions
                    x = np.arange(len(df_all_site_con_cop.index))
                    width_center = 0.7
            
                    #  Plot
                    ax.bar(
                        x,
                        (df_all_site_con_cop[col] * unit_scale),
                        width_center,
                        label=col,
                        color='lightblue',
                        alpha=0.8
                    )
            
                    #  Labels and title
                    # ax.set_title(f'{col} to connect network and placement site')
                    ax.set_title('Distance to connect network and placement site')
                    # ax.set_ylabel(f'{col} {unit}')
                    ax.set_ylabel(f'Distance {unit}')
                    ax.set_xlabel('Placement Site')
                    
                    # Grid
                    # ax.grid(True)
                    ax.grid(True, which='major', axis='y', color='gray', linestyle='-', linewidth=0.4, alpha=0.3)
                    ax.yaxis.set_major_locator(MaxNLocator(nbins=20))
                    
                    #  Keep all ticks but only show every 5th label if there are not many
                    num_sites = len(df_all_sites_cop.index)
                    if num_sites < 16:
                        labels = df_all_sites_cop.index.tolist()
                    else:
                        # Show every 5th label starting at index 4 (Site_5)
                        labels = [label if ((i - 4) % 5 == 0) else '' for i, label in enumerate(df_all_sites_cop.index)]               
                    ax.set_xticks(x)
                    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=10)
                    ax.set_xlim(-0.7, len(x) - 0.3)
                    
                    
                    #  Legend and tight layout
                    plt.tight_layout()
            
                    #  Save each plot to PDF
                    pdf.savefig(fig)
                    plt.close(fig)
            
                #''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
                # Create bar plots for df_all_sites_cop
                
                columns_to_plot = ['value', 'area_found', 'area_needed']
                for col in columns_to_plot:
                    if col == 'value':
                        unit_scale = fac_SI_unit 
                        unit = f'[{res_unit}]'
                        title_dummy = res_unit_type
                    elif col == 'value_factor':
                        unit_scale = 1
                        unit = '[-]'
                        title_dummy = "Coverage"
                    elif col == 'area_needed':
                        unit_scale = 10**-6
                        unit = '[km²]'
                        title_dummy = "Area needed by Site"
                    elif col == 'area_found':
                        unit_scale = 10**-6
                        unit = '[km²]'
                        title_dummy = "Area found to build the Site"
                    fig, ax = plt.subplots(figsize=(12, 8))
                    
                    #  Bar positions
                    x = np.arange(len(df_all_sites_cop.index))
                    width_center = 0.7
                    # Define label
                    if col == 'area_needed':
                        label = "Area of Site"
                    elif col == 'area_found':
                        label = "Area found to place Site"
                    else:
                        label = col
                    #  Plot
                    ax.bar(
                        x,
                        (df_all_sites_cop[col] * unit_scale),
                        width_center,
                        label=label,
                        color='lightblue',
                        alpha=0.8
                    )
                    
                    # Add horizontal line ONLY for area plot
                    if col in ['area_needed', 'area_found']:
                        threshold_value = 0.014  # km²
                        ax.axhline(y=threshold_value, color='red', linestyle='--', linewidth=0.8, label='Existing Pit Storage Reference')
                        ax.legend()
                        
                            
                    #  Labels and title
                    ax.set_title(f'{title_dummy} of the placement site')
                    ax.set_ylabel(f'{title_dummy} {unit}')
                    ax.set_xlabel('Placement Site')
                    
                    # Grid
                    # ax.grid(True)
                    ax.grid(True, which='major', axis='y', color='gray', linestyle='-', linewidth=0.4, alpha=0.3)
                    ax.yaxis.set_major_locator(MaxNLocator(nbins=20))
    
                    #  Keep all ticks but only show every 5th label if there are not many
                    num_sites = len(df_all_sites_cop.index)
                    if num_sites < 16:
                        labels = df_all_sites_cop.index.tolist()
                    else:
                        # Show every 5th label starting at index 4 (Site_5)
                        labels = [label if ((i - 4) % 5 == 0) else '' for i, label in enumerate(df_all_sites_cop.index)]               
                    ax.set_xticks(x)
                    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=10)
                    ax.set_xlim(-0.7, len(x) - 0.3)
                    
                    #  Legend and tight layout
                    plt.tight_layout()
            
                    #  Save each plot to PDF
                    pdf.savefig(fig)
                    plt.close(fig)
                    
                    ######################## repeating plots for analysis END ########################
                        
                        
            #''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
            # new html map that shows all possible placement areas (all of switzerland)
            print(f'----- Saving html map of all possible placement sites for {name_parameter} {u_title}-----\n')
            df_all_possible_sites = df_all_possible_sites.reset_index(drop= True)
            def clean_gdf(gdf):
                gdf = gdf.copy()
                gdf = gdf[gdf.geometry.notna()]
                gdf = gdf[~gdf.geometry.is_empty]
                return gdf
            gdf_all_pos_sites = gpd.GeoDataFrame(df_all_possible_sites, geometry=df_all_possible_sites.geometry, crs = 'EPSG:2056')
            final_map_plotter([gdf_all_pos_sites], f'Possible_Sites_{name_parameter}_{u_title}.html', map_path, layer_name=['Possible Sites'])
            #'''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
            # save results as txt file
            df_all_sites.to_string(map_path+f'Placement_results_{name_parameter}_{u_title}.txt')
            df_all_site_con.to_string(map_path+f'Placement_connections_results_{name_parameter}_{u_title}.txt')
            df_all_networks.to_string(map_path+f'Network_results_{name_parameter}_{u_title}.txt')
            df_all_networks.to_string(map_path+f'Network_results_{name_parameter}_{u_title}.txt')
            df_result.to_string(map_path+f'Demand_Supply_results_{name_parameter}_{u_title}.txt')
    
            #''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''''
            print(f'----- Start save results for {name_parameter} {u_title}-----\n')
            # save result in df_res_parameter
            # Main metric assignments
            df_res_parameter.loc[u, 'Total_Supply'] = df_result['Supply'].sum()
            df_res_parameter.loc[u, 'Total_Demand'] = df_result['Demand'].sum()
            df_res_parameter.loc[u, 'Avg_Region_Supply'] = df_result['Supply'].mean()
            df_res_parameter.loc[u, 'Avg_Region_Demand'] = df_result['Demand'].mean()
            
            df_res_parameter.loc[u, 'Total_Connected'] = df_result['Connected_Demand_Supply'].sum()
            df_res_parameter.loc[u, 'Total_Placed'] = df_result['Placed_Energy_System'].sum()
            df_res_parameter.loc[u, 'Avg_Region_Connected'] = df_result['Connected_Demand_Supply'].mean()
            df_res_parameter.loc[u, 'Avg_Region_Placed'] = df_result['Placed_Energy_System'].mean()
            
            # Network Value Metrics
            df_res_parameter.loc[u, 'Total_Value_Network'] = df_all_networks['value'].sum()
            df_res_parameter.loc[u, 'Avg_Value_Network'] = df_all_networks['value'].mean()
            df_res_parameter.loc[u, 'Median_Value_Network'] = df_all_networks['value'].median()
        
            # Network Distance Metrics
            df_res_parameter.loc[u, 'Total_Distance_Network'] = df_all_networks['distance'].sum()
            df_res_parameter.loc[u, 'Avg_Distance_Network'] = df_all_networks['distance'].mean()
            df_res_parameter.loc[u, 'Median_Distance_Network'] = df_all_networks['distance'].median()
            
            df_res_parameter.loc[u, 'Avg_Distance/Value_Network'] = df_all_networks['distance/value'].mean()
            df_res_parameter.loc[u, 'Median_Distance/Value_Network'] = df_all_networks['distance/value'].median()
            
            # Site Connections Distance
            df_res_parameter.loc[u, 'Total_Distance_Site_Connections'] = df_all_site_con['distance'].sum()
            df_res_parameter.loc[u, 'Avg_Distance_Site_Connections'] = df_all_site_con['distance'].mean()
            df_res_parameter.loc[u, 'Median_Distance_Site_Connections'] = df_all_site_con['distance'].median()
            
            # Placed Energy Systems Value
            df_res_parameter.loc[u, 'Total_Value_Placed_Energy_Systems'] = df_all_sites['value'].sum()
            df_res_parameter.loc[u, 'Avg_Value_Placed_Energy_Systems'] = df_all_sites['value'].mean()
            df_res_parameter.loc[u, 'Median_Value_Placed_Energy_Systems'] = df_all_sites['value'].median()
            
            # Placed Energy Systems Area
            df_res_parameter.loc[u, 'Total_Area_Placed_Energy_Systems'] = df_all_sites['area_needed'].sum()
            df_res_parameter.loc[u, 'Avg_Area_Placed_Energy_Systems'] = df_all_sites['area_needed'].mean()
            df_res_parameter.loc[u, 'Median_Area_Placed_Energy_Systems'] = df_all_sites['area_needed'].median()
            
            # Value Factor for Placed Energy Systems
            df_res_parameter.loc[u, 'Avg_ValueFactor_Placed_Energy_Systems'] = df_all_sites['value_factor'].mean()
            df_res_parameter.loc[u, 'Median_ValueFactor_Placed_Energy_Systems'] = df_all_sites['value_factor'].median()
        
        #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        print( '¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦')
        print( '                    All Iterations DONE!                               ')
        print( '¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦')
        print(f'----- Start creating Evaluation pdf for {name_parameter} -----\n')
        # scale the over all results according to the user input
        cols_energy=['Total_Supply','Total_Demand','Avg_Region_Supply','Avg_Region_Demand','Total_Connected','Total_Placed','Avg_Region_Connected','Avg_Region_Placed','Total_Value_Network','Avg_Value_Network','Median_Value_Network','Total_Value_Placed_Energy_Systems','Avg_Value_Placed_Energy_Systems','Median_Value_Placed_Energy_Systems']
        cols_dist_per_val=['Avg_Distance/Value_Network','Median_Distance/Value_Network']
        df_res_parameter.loc[:,cols_energy]=df_res_parameter.loc[:,cols_energy]*fac_SI_unit
        df_res_parameter.loc[:,cols_dist_per_val]=df_res_parameter.loc[:,cols_dist_per_val]/fac_SI_unit

        # plot_groups = [
        #     ['Total_Supply', 'Avg_Region_Supply', 'Total_Demand', 'Avg_Region_Demand',
        #      'Total_Connected', 'Avg_Region_Connected', 'Total_Placed', 'Avg_Region_Placed'],
        #     ['Total_Value_Network', 'Avg_Value_Network', 'Median_Value_Network'],
        #     ['Total_Distance_Network', 'Avg_Distance_Network', 'Median_Distance_Network'],
        #     ['Avg_Distance/Value_Network', 'Median_Distance/Value_Network'],
        #     ['Total_Distance_Site_Connections', 'Avg_Distance_Site_Connections', 'Median_Distance_Site_Connections'],
        #     ['Total_Value_Placed_Energy_Systems', 'Avg_Value_Placed_Energy_Systems', 'Median_Value_Placed_Energy_Systems'],
        #     ['Total_Area_Placed_Energy_Systems', 'Avg_Area_Placed_Energy_Systems', 'Median_Area_Placed_Energy_Systems'],
        #     ['Avg_ValueFactor_Placed_Energy_Systems', 'Median_ValueFactor_Placed_Energy_Systems']
        # ]
        # plot_groups = [
        #     ['Total_Demand', 'Avg_Region_Demand', 'Total_Placed', 'Avg_Region_Placed'],
        #     ['Total_Distance_Site_Connections', 'Avg_Distance_Site_Connections', 'Median_Distance_Site_Connections'],
        #     ['Total_Value_Placed_Energy_Systems', 'Avg_Value_Placed_Energy_Systems', 'Median_Value_Placed_Energy_Systems'],
        #     ['Total_Area_Placed_Energy_Systems', 'Avg_Area_Placed_Energy_Systems', 'Median_Area_Placed_Energy_Systems'],
        # ]
        
        # plot_groups = [
        #     ['Total_Demand', 'Avg_Region_Demand', 'Total_Placed', 'Avg_Region_Placed'],
        #     ['Avg_Distance_Site_Connections', 'Median_Distance_Site_Connections'],
        #     ['Avg_Value_Placed_Energy_Systems', 'Median_Value_Placed_Energy_Systems'],
        #     ['Avg_Area_Placed_Energy_Systems', 'Median_Area_Placed_Energy_Systems'],
        # ]
        
        plot_groups = [
            ['Total_Placed'],
            ['Avg_Distance_Site_Connections', 'Median_Distance_Site_Connections'],
            ['Avg_Value_Placed_Energy_Systems', 'Median_Value_Placed_Energy_Systems'],
            ['Avg_Area_Placed_Energy_Systems', 'Median_Area_Placed_Energy_Systems'],
        ]
        
        # y_axis_labels = [
        #     'Clustered Heat Demand [kWh/a]',           # for plot 1
        #     'Site Connection Distance [m]',            # for plot 2
        #     'Heat Capacity in Pits [kWh]',    # for plot 3
        #     'Area of Pits [m²]'       # for plot 4
        # ]    
        y_axis_labels = [
            '',           # for plot 1
            'Site Connection Distance [m]',            # for plot 2
            f'{res_unit_type} in Sites [{res_unit}]',    # for plot 3
            'Area of Sites [m²]'       # for plot 4
        ]
        
        secondary_y_labels = [
            f'Total Placed Sites {res_unit_type} [{res_unit}]',       # secondary y of plot 1
            '',                                        # no secondary y for others
            '',
            ''
        ]
        # secondary_y_cols = [
        #     'Total_Placed', 'Avg_Region_Placed'
        # ]  
        secondary_y_cols = ['Total_Placed']
        
        pdf_name = f'Parameter_result_plots_{name_parameter}.pdf'
        with PdfPages(map_path + pdf_name) as pdf:
            for plot_index, columns in enumerate(plot_groups, start=1):
                fig, ax = plt.subplots(figsize=(12, 8))
                ax2 = None  # secondary axis
        
                # Create base names for matching colors
                base_names = []
                for col in columns:
                    if col.startswith('Total_'):
                        base = col.replace('Total_', '')
                    elif col.startswith('Avg_Region_'):
                        base = col.replace('Avg_Region_', '')
                    elif col.startswith('Avg_'):
                        base = col.replace('Avg_', '')
                    elif col.startswith('Median_'):
                        base = col.replace('Median_', '')
                    else:
                        base = col
                    base_names.append(base)
        
                unique_base_names = list(dict.fromkeys(base_names))  # preserve order, remove duplicates
        
                # Assign colors
                cmap = matplotlib.cm.get_cmap('Dark2', len(unique_base_names))
                color_map = {base: cmap(i) for i, base in enumerate(unique_base_names)}
        
                # # Prepare secondary axis if needed (only for first plot group)
                if plot_index == 1:
                    ax2 = ax.twinx()           
                
                for col in columns:
                    # Determine base name, linestyle, etc.
                    if col.startswith('Avg_Region_'):
                        base = col.replace('Avg_Region_', '')
                        linestyle = '--'
                        marker = None
                    elif col.startswith('Avg_'):
                        base = col.replace('Avg_', '')
                        linestyle = '--'
                        marker = None
                    elif col.startswith('Median_'):
                        base = col.replace('Median_', '')
                        linestyle = ':'
                        marker = None
                    elif col.startswith('Total_'):
                        base = col.replace('Total_', '')
                        linestyle = '-'
                        marker = None
                    else:
                        base = col
                        linestyle = '-'
                        marker = None
        
                    # Choose axis: secondary or primary?
                    if ax2 and col in secondary_y_cols:
                        ax_plot = ax2
                    else:
                        ax_plot = ax
        
                    ax_plot.plot(
                        df_res_parameter.index,
                        df_res_parameter[col],
                        label=col,
                        linestyle=linestyle,
                        color=color_map.get(base, 'black'),
                        marker=marker
                    )
        
                if plot_index == 1 and ax2:
                    # Move ax2's y-axis to the left
                    ax2.yaxis.set_label_position("left")
                    ax2.yaxis.tick_left()
                    ax2.spines["left"].set_position(("outward", 0))
                    ax2.spines["right"].set_visible(False)
                
                    # Optional: hide the unused ax (primary y-axis)
                    ax.set_yticks([])
                    ax.set_ylabel('')
                    ax.tick_params(axis='y', left=False)
                    ax.spines["left"].set_visible(False)
            
                # Set titles and axis labels
                # ax.set_title(f'Plot {plot_index}: {" | ".join(columns)}')
                ax.set_xlabel('Scenario')
                ax.set_ylabel(y_axis_labels[plot_index - 1])
                if ax2 and secondary_y_labels[plot_index - 1]:
                    ax2.set_ylabel(secondary_y_labels[plot_index - 1])
    
        
                # # Combine legends for both axes
                if plot_index != 1:  # Only show legend for plots 2–4
                    if ax2:
                        handles1, labels1 = ax.get_legend_handles_labels()
                        handles2, labels2 = ax2.get_legend_handles_labels()
                        ax2.legend(handles1 + handles2, labels1 + labels2, loc='best')
                    else:
                        handles, labels = ax.get_legend_handles_labels()
                        ax.legend(handles, labels, loc='best')
        
                ax.set_xticks(df_res_parameter.index)
                ax.set_xticklabels(df_res_parameter.index)
    
                plt.tight_layout()
                pdf.savefig(fig)
                plt.close(fig)
        
        string_unit = res_unit.replace("/", "_")
        df_res_parameter.to_string(map_path+f'Overall_results_{name_parameter}_{string_unit}.txt')
        
        overall_time = round((time.time() - overall_time_start)/60,2)
        
        print("----- Saving the input variables -----")
        
        # pack variables into dictionary
        variable_dic = {
            # Configs PATHFNDR_main_framework
            "sqr_size": sqr_size,
            "sqr_size_exp": sqr_size_exp,
        
            # Result_path
            "result_folder": result_folder,
            "proof_file": proof_file,
        
            # Calculation configuration
            "explore_raw_data": explore_raw_data,
            "ReCalcData": ReCalcData,
            
            # User Defined Units
            'res_unit_type' : res_unit_type,
            'res_unit' : res_unit,
            'res_base_unit' : res_SI_unit,
            'fac_base_unit' : fac_SI_unit,
        
            # Energy Data source configuration
            "data_energy_path": data_energy_path,
            "dic_gpkg_data": dic_gpkg_data,
        
            # Placement Data source configuration
            "data_placement_path": data_placement_path,
            "dic_gpkg_geo": dic_gpkg_geo,
        
            # Iteration parameters
            "dic_par_iteration": dic_par_iteration,
        
            # BASE CASE (energy_system_models)
            "dic_energy": GeoPATH.get_dic_energy_user(),
            "dic_place": dic_place_orig,
            "dic_obj": GeoPATH.get_dic_obj_user,
            "dic_clust": dic_clust_orig,
            "dic_connect": dic_connect_orig,
        
            # Building site dictionary
            "dic_site": dic_site_orig,
        }
        
        variable_path = data_path + '../03_Results/' + result_folder
        create_inputs_as_txt(variable_dic, variable_path, overall_time)
        
        
        
        print( '¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦')
        print( '                   DONE - Ready for the next Ride                     ')
        print( '¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦')
    
    
    print( f'                This took {overall_time} min in total.           ')
    print( '¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦-¦')
    
