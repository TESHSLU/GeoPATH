# -*- coding: utf-8 -*-
"""
Created on Fri May  3 12:51:03 2024

@author: Simon In-Albon

classes that regulates all new raw data input
if a new class is defined, the following interfaces must be implemented:
    -
    -
    -
    -
    
"""
from tqdm import tqdm
from data_worker import df_multiHead
import numpy as np
import pandas as pd

#%%   BASELINE CLASS
"""
Copy the code below to create a new calculation class

# ============ User defined ============
CHANGE THE NAME OF THE CLASS TO THE KEY IN THE DICTIONARY IN << PATHFNDR_main_framework >>
# ======================================

class DHN():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = []
        # define all the columns that will be calculated to the square-map
        lst_columns = []
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)
                df_res.loc[w,(key[0], 'power_avg_MW' )] = round(df_data.Power.mean(),3)
                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res
"""
#%%
class DHN():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = ['EnergySource1', 'EnergySource2', 'HouseConnections', 'BeginningOfOperation', 'Power', 'Energy']
        # define all the columns that will be calculated to the square-map
        lst_columns = ['power_min_MW', 'power_tot_MW','power_max_MW', 'energy_MWh', 'tot_houses_con']
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)
                df_res.loc[w,(key[0], 'power_min_MW' )] = df_data.Power.min()
                df_res.loc[w,(key[0], 'power_max_MW' )] = df_data.Power.max()
                df_res.loc[w,(key[0], 'power_tot_MW' )] = df_data.Power.sum()
                df_res.loc[w,(key[0], 'energy_MWh' )] = df_data.Energy.sum()
                df_res.loc[w,(key[0], 'tot_houses_con' )] = int(df_data.HouseConnections.sum())

                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res

#%%

class IndHeat():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = []
        # define all the columns that will be calculated to the square-map
        lst_columns = ['energy_tot_MWh', 'energy_min_MWh', 'energy_max_MWh']
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)
                df_res.loc[w,(key[0], 'energy_tot_MWh' )] = df_data.NEEDINDUSTRY.sum()
                df_res.loc[w,(key[0], 'energy_min_MWh' )] = df_data.NEEDINDUSTRY.min()
                df_res.loc[w,(key[0], 'energy_max_MWh' )] = df_data.NEEDINDUSTRY.max()
                # Extraction of industry information (what industry is it := what temperature of waste heat?)
                # NEEDS TO BE DONE!

                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res

#%%   BASELINE CLASS

class Waste():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = []
        # define all the columns that will be calculated to the square-map
        lst_columns = []
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)
                
                # NO INFORMATION OTHER THAN LOCATION!
                
                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res


#%%   Elektrizitätsproduktionsanlagen --> ePlant

class ePlant():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = []
        # define all the columns that will be calculated to the square-map
        lst_columns = ['Operation_Start', 'Initial_Power_sum_kW', 'Power_Today_sum_kW', 'Expansion_kW', 'Main_Category', 'Sub_Category', 'Plant_Category']
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)
                df_res.loc[w,(key[0], 'Operation_Start' )] = pd.to_datetime(df_data.BeginningOfOperation, errors='coerce').dt.year.drop_duplicates().tolist()
                df_res.loc[w,(key[0], 'Initial_Power_sum_kW' )] = df_data.InitialPower.sum()
                df_res.loc[w,(key[0], 'Power_Today_sum_kW' )] = df_data.TotalPower.sum()
                df_res.loc[w,(key[0], 'Expansion_kW' )] = df_data.TotalPower.sum() - df_data.InitialPower.sum()
                df_res.loc[w,(key[0], 'Main_Category' )] = df_data.MainCategory.drop_duplicates().tolist()
                df_res.loc[w,(key[0], 'Sub_Category' )] = df_data.SubCategory.drop_duplicates().tolist()
                df_res.loc[w,(key[0], 'Plant_Category' )] = df_data.PlantCategory.drop_duplicates().tolist()
                
                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res

#%% Elektrische Anlagen über 36 kV, layer "leitung" --> eTransL

class eTransL():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = ['leitung_typ', 'spannung', 'betriebsstatus', 'frequenz']
        # define all the columns that will be calculated to the square-map
        lst_columns = []
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)

                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res


#%% Elektrische Anlagen über 36 kV, layer "station_punkt" --> eTransS

class eTransS():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = ['station_typ_de']
        # define all the columns that will be calculated to the square-map
        lst_columns = []

        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)

                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res
    
#%%
class gas():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = ['name', 'operator']
        # define all the columns that will be calculated to the square-map
        lst_columns = []
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)

                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res
        
        

#%%    
class bdgs_heat_e():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = ['BEDARF_HEIZUNG', 'heat_energy_demand_estimate_GWR3', 'heating_source_DE', 'fossil_heating_source', "mean_temp_winter", "mean_temp_summer", "temp_difference"]
        # define all the columns that will be calculated to the square-map
        lst_columns = ['BEDARF_HEIZUNG_sum', 'TotalPower_sum', 'fossil_heating_source_sum', "temp_difference_mean"]
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        # print ('\n=====================================================================')
        # print (f'----- Start calculation of {dic_key} -----')
        # print ('=====================================================================')
        
        # for w in tqdm(range(len(geo_data))):
        for w in range(len(geo_data)):
            # Build spatial index
            sindex = df_raw.sindex
            
            # Query geometries that have bounding box intersection first (fast)
            possible_matches_index = list(sindex.intersection(geo_data[w].bounds))
            possible_matches = df_raw.iloc[possible_matches_index]
            
            # Precise filtering with real geometry intersection
            df_data = possible_matches[possible_matches.intersects(geo_data[w])]
            # df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)
                # df_res.loc[w,(key[0], 'GBAUJ' )] = df_data.year.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'GWAERDATH1' )] = df_data.GWAERDATH1.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'BEDARF_HEIZUNG' )] = df_data.BEDARF_HEIZUNG.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'PV_Pot' )] = df_data.PV_Pot.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'PV_Pot_reco' )] = df_data.PV_Pot_reco.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'FPV_Pot' )] = df_data.FPV_Pot.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'FPV_Pot_reco' )] = df_data.FPV_Pot_reco.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'BeginningOfOperation' )] = df_data.BeginningOfOperation.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'InitialPower' )] = df_data.InitialPower.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'TotalPower' )] = df_data.TotalPower.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'PlantCategory' )] = df_data.PlantCategory.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'TotalEnergy' )] = df_data.TotalEnergy.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'altitude' )] = df_data.altitude.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'Temperature_mean' )] = df_data.Temperature_mean.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'renovation_base' )] = df_data.renovation_base.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'renovation_low' )] = df_data.renovation_low.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'renovation_high' )] = df_data.renovation_high.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'heat_energy_demand_estimate_kWh_combined' )] = df_data.heat_energy_demand_estimate_kWh_combined.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'heat_energy_demand_renov_estimate_kWh' )] = df_data.heat_energy_demand_renov_estimate_kWh.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'dhw_estimatin_kWh_combined' )] = df_data.dhw_estimatin_kWh_combined.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'ERA_netto' )] = df_data.ERA_netto.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'ERA_brutto' )] = df_data.ERA_brutto.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'heat_energy_demand_estimate_H4C' )] = df_data.heat_energy_demand_estimate_H4C.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'heat_energy_demand_estimate_GWR3' )] = df_data.heat_energy_demand_estimate_GWR3.drop_duplicates().tolist()
                # df_res.loc[w,(key[0], 'heating_source_DE' )] = df_data.heating_source_DE.drop_duplicates().tolist()
                df_res.loc[w,(key[0], 'BEDARF_HEIZUNG_sum' )] = df_data.BEDARF_HEIZUNG.sum()
                df_res.loc[w,(key[0], 'TotalPower_sum' )] = df_data.TotalPower.sum()
                df_res.loc[w,(key[0], 'fossil_heating_source_sum' )] = df_data.fossil_heating_source.sum()
                df_res.loc[w,(key[0], 'temp_difference_mean' )] = round(df_data.temp_difference.mean(),3)
                # ======================================
                
        # print ('\n=====================================================================')
        # print (f'----- Finished calculation of {dic_key} -----')
        # print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res
        
               
#%%
class ara():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = []
        # define all the columns that will be calculated to the square-map
        lst_columns = ['power_potential_avg_MWha', 'power_potential_min_MWha', 'power_potential_max_MWha']

        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)
                df_res.loc[w,(key[0], 'power_potential_avg_MWha' )] = round(df_data.HeatPotential_MWha.mean(),3)
                df_res.loc[w,(key[0], 'power_potential_min_MWha' )] = round(df_data.HeatPotential_MWha.min(),3)
                df_res.loc[w,(key[0], 'power_potential_max_MWha' )] = round(df_data.HeatPotential_MWha.max(),3)

                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res
 

#%%

class ARA_and_KVA():
    def __init__(self, geo_data, df_raw, dic_key):
        
        # ============ User defined ============
        # define list of all columns from the raw file that will stay!
        lst_raw_columns = ['heat_supply_MWha', 'source']
        # define all the columns that will be calculated to the square-map
        lst_columns = []
        
        # ======================================
        
        geo_index = geo_data.index
        geo_data.reset_index(drop=True, inplace=True)
        #create multicolumn dataframe
        key = [dic_key]
        df_res = df_multiHead(key, ['obj_ID']+lst_raw_columns+lst_columns, ['source', 'data'], geo_data.index, np.nan)
        #loop over each square polygon
        print ('\n=====================================================================')
        print (f'----- Start calculation of {dic_key} -----')
        print ('=====================================================================')
        
        for w in tqdm(range(len(geo_data))):
            df_data = df_raw[df_raw.geometry.intersects(geo_data[w])]
            if not df_data.empty: 
                df_res = df_res.astype(object)
                # save all raw data wanted (lst_raw_columns) in a list
                df_res.loc[w,(key[0], 'obj_ID' )] = df_data.index.tolist()
                for column in lst_raw_columns:
                    df_res.loc[w, (key[0], column)] = df_data[column].dropna().tolist()
                
                # ============ User defined ============
                # define how the columns are calculated
                # fill in the column, df_data is all the points that are inside the current square (use df_data to calculate)

                # ======================================
                
        print ('\n=====================================================================')
        print (f'----- Finished calculation of {dic_key} -----')
        print ('=====================================================================')
        df_res.set_index(geo_index, inplace=True)
        self.df_res = df_res
        
  




        