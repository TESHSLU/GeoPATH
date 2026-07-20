import PATHFNDR_main_framework
import sys
import copy
# =========================== User Inputs ===================================== 

#------------------------------------------------------------------------------
# 1 Configuration of GeoPATH
#------------------------------------------------------------------------------

# Unit of Results
res_unit_type = 'Yearly Energy' 
res_unit = 'GWh/a'
res_base_unit = 'Wh/a'
fac_base_unit = 10**(-9)
#....................... 

#Swiss Region Sqare Grid
sqr_size = 4000    #[m]
sqr_size_exp = 6000 #[m]
#....................

# Result Folder
result_folder = 'my_results'
#....................

# Calculation configuration
explore_raw_data = False
ReCalcData = False
#%% INFO Configuration GeoPATH
# -----------------------------------------------------------------------------
# |  INFO                                                                    |
# |                                                                          |
# |  Result Units:                                                           |
# |      res_unit_type  : descriptive label of the result quantity           |
# |      res_unit       : displayed output unit                              |
# |      res_base_unit  : baseline unit without >Mega< or >Kilo<             |
# |      fac_base_unit  : conversion factor from base to output unit         |
# |                       res_unit = res_base_unit * fac_base_unit           |
# |                                                                          |
# |  Spatial Grid Configuration (Swiss square grid):                         |
# |      sqr_size       : main grid resolution [m]                           |
# |      sqr_size_exp   : extended grid size for analysis buffer [m]         |
# |                                                                          |
# |  Result Storage:                                                         |
# |      result_folder  : name of output directory                           |
# |                                                                          |
# |  Calculation Settings:                                                   |
# |      explore_raw_data : True → only explore raw data (no full run)       |
# |      ReCalcData       : True → force recalculation of precomputed data   |
# |                                                                          |
# |  NOTE: The energy meta Excel file must be closed during model execution. |
# -----------------------------------------------------------------------------
#------------------------------------------------------------------------------
# 2 Configuration of BASE CASE 
#------------------------------------------------------------------------------
#%%----------------------------------------------------------------------------
# 2.1 Energy Reqirement (Binary Boundary Conditions, pre-calculations)
#------------------------------------------------------------------------------
dic_energy = {
    
    1:{'energy_object': 'bdgs_heat_e',
        'value': 'fossil_heating_source',
        'operator': 'eq',
        'requirement_value': 1
        },
    
    2:{'energy_object': 'Waste',
        'value': 'obj_ID',
        'operator': 'ge',
        'requirement_value': 1
        },

    }
#%% >>>> INFO Energy Requirement <<<<
#------------------------------------------------------------------------------
# |  INFO                                                                    |
# |                                                                          |
# |  Defines attribute-based filtering criteria for energy-related objects.  |
# |                                                                          |
# |  Structure:                                                              |
# |      ID : {                                                              |
# |          'energy_object'   : name of the spatial dataset,                |
# |          'value'           : attribute to be evaluated,                  |
# |          'operator'        : comparison operator,                        |
# |          'requirement_value': threshold value [IN Unit of Values!!!]     |
# |      }                                                                   |
# |                                                                          |
# |  --> ID is a user-defined unique identifier for each filter rule.        |
# |                                                                          |
# |  --> The condition is evaluated as:                                      |
# |      value (operator) requirement_value (ALWAYS IN Unit of Values        |
# |      from Excel!!)                                                       |
# |                                                                          |
# |  --> Multiple entries are combined sequentially to restrict the          |
# |      eligible energy objects.                                            |
# |                                                                          |
# |  --> To define a minimum number of objects within a region, use          |
# |      'obj_ID' as 'value' and set 'requirement_value' to the required     |
# |      number of objects (e.g. operator='ge', requirement_value=3).        |
# |                                                                          |
# |  Legend:                                                                 |
# |      'eq' : equal to                                                     |
# |      'ge' : greater than or equal to                                     |
# |      'le' : less than or equal to                                        |
# |      'lt' : less than                                                    |
# |      'gt' : greater than                                                 |
# -----------------------------------------------------------------------------
#%%----------------------------------------------------------------------------
# 2.2 Placement Reqirement (Binary Boundary Conditions)
#------------------------------------------------------------------------------
dic_place = {
    1 : {'placement_data' : 'DHM25', 
         'value' : 'tilt',
         'operator' : 'le',
         'requirement_value' : 5
        },

    }
#%% >>>> INFO Placement Reqirement <<<<
#------------------------------------------------------------------------------
# |                                                                          |
# |  Defines spatial placement constraints that must be fulfilled            |
# |  for an object to be considered suitable.                                |
# |                                                                          |
# |  Structure:                                                              |
# |      ID : {                                                              |
# |          'placement_data'   : spatial dataset used for evaluation,       |
# |          'value'            : attribute to be checked,                   |
# |          'operator'         : comparison operator,                       |
# |          'requirement_value': threshold value                            |
# |      }                                                                   |
# |                                                                          |
# |  Legend:                                                                 |
# |      'eq' : equal to                                                     |
# |      'ge' : greater than or equal to                                     |
# |      'le' : less than or equal to                                        |
# |      'lt' : less than                                                    |
# |      'gt' : greater than                                                 |
# -----------------------------------------------------------------------------
#%%----------------------------------------------------------------------------
# 2.3 Object Dictionary (Definition of Demand & Supply)
#------------------------------------------------------------------------------
dic_obj = {
    #---------------------------------------
    'Demand':{
        
        1:{'energy_object': 'bdgs_heat_e',
           'value': 'BEDARF_HEIZUNG',
           'factor': 1,
           'energy_type': 'heat'
            }
    #---------------------------------------
        },
    #---------------------------------------
    'Supply':{
        
        1:{'energy_object': 'Waste',
           'value': 'Heat_2021',
           'factor': 1,
           'energy_type': 'heat'
            },

    #---------------------------------------
        }
    }
#%% >>>> INFO Object Dictionary <<<<
#------------------------------------------------------------------------------
# |  INFO                                                                    |
# |                                                                          |
# |  Defines all energy-relevant objects that act as Supply or Demand        |
# |  within the system model.                                                |
# |                                                                          |
# |  Structure:                                                              |
# |      'Demand' or 'Supply' : {                                            |
# |          ID : {                                                          |
# |              'energy_object' : name of the spatial object,               |
# |              'value'         : attribute containing the quantity,        |
# |              'factor'        : scaling factor applied to raw values,     |
# |              'energy_type'   : transported energy type                   |
# |          }                                                               |
# |      }                                                                   |
# |                                                                          |
# |  --> ID is a user-defined unique identifier within 'Demand' or           |
# |      'Supply' and has no physical meaning.                               |
# |                                                                          |
# |  --> 'factor' scales the input data (e.g. for uncertainty or             |
# |      availability assumptions). Example: 1/3 reduces values to one       |
# |      third.                                                              |
# |                                                                          |
# |  --> 'energy_type' must be consistent with <dic_connect>.                |
# |                                                                          |
# |  --> Connector-only objects do not need to be defined here.              |
# |                                                                          |
# |  --> Network logic is defined separately in <dic_connect>.               |
# -----------------------------------------------------------------------------
#%%----------------------------------------------------------------------------
# 2.4 Cluster Dictionary
#------------------------------------------------------------------------------
dic_clust = {
    'bdgs_heat_e':{
                   'clustered_value' : 'BEDARF_HEIZUNG',
                   'max_distance' :  200,
                   'value_density' : 70,
                   'min_number_objects' : 50,
                   'interested_in_cluster' : True
                   },
    }
#%% >>>> INFO Cluster Dictionary <<<<
#------------------------------------------------------------------------------
# |  INFO                                                                    |
# |                                                                          |
# |  energy_object : {                                                       |
# |      'clustered_value'      : attribute used for aggregation,            |
# |      'max_distance'         : maximum distance within cluster [m],       |
# |      'value_density'        : minimum required density [value/m²],       |
# |      'min_number_objects'   : minimum objects required for a cluster,    |
# |      'interested_in_cluster': True → use clusters,                       |
# |                               False → use non-clustered objects          |
# |  }                                                                       |
# |                                                                          |
# |  --> Geometry of the energy_object MUST be of type Point.                |
# |                                                                          |
# |  --> Clustering is based on spatial proximity (max_distance) and         |
# |      aggregated density (value_density).                                 |
# |                                                                          |
# |  --> A cluster is created only if both density and minimum object        |
# |      criteria are fulfilled.                                             |
# |                                                                          |
# |  --> Non-clustered objects can optionally be considered individually.    |
# -----------------------------------------------------------------------------
#%%----------------------------------------------------------------------------
# 2.5 Network Dictionary
#------------------------------------------------------------------------------ 
dic_connect = {    
    
    1:{'demand': ('bdgs_heat_e', 'BEDARF_HEIZUNG', 1, False),   
          'supply': ('Waste', 'Heat_2021', 1, False),
          'connectors': [],
          'energy_type': 'heat',
          'max_distance': 0.5*(1/1000),
          'value_distance': True
          },
    
    }
#%% >>>> INFO Network Dictionary <<<<
#------------------------------------------------------------------------------
# |  INFO                                                                    |
# |                                                                          |
# |  Connection_Number : {                                                   |
# |      'demand'        : (Demand_object, Demand_column, transmission, hub) |
# |      'supply'        : (Supply_object, Supply_column, transmission, hub) |
# |      'connectors'    : [(Connector_object, Connector_column,             |
# |                          transmission, hub), ...],                       |
# |      'energy_type'   : <string>,                                         |
# |      'max_distance'  : [m/value or m],                                   |
# |      'value_distance': True/False                                        |
# |  }                                                                       |
# |                                                                          |
# |  --> transmission_value defines how much of the transferred value is     |
# |      required to create a connection. It allows scaling, conversion      |
# |      between quantities (e.g. heat ↔ electricity), or representation     |
# |      of transmission losses.                                             |
# |                                                                          |
# |  --> To remove capacity limits while keeping connectivity, set the       |
# |      corresponding <*_column> to 'None' (string). The object then        |
# |      acts purely as a connector.                                         |
# |                                                                          |
# |  --> If no connectors are required, use an empty list:                   |
# |      'connectors': []                                                    |
# |                                                                          |
# |  --> 'energy_type' must be consistent with <dic_obj>.                    |
# |                                                                          |
# |  --> hub=True allows branching (multiple connections).                   |
# |      hub=False defines a single start/end point.                         |
# -----------------------------------------------------------------------------
#%%----------------------------------------------------------------------------
# 2.6 Buidling Site Dictionary
#------------------------------------------------------------------------------ 
dic_site = {   
    'value': ('bdgs_heat_e', 'BEDARF_HEIZUNG'),
    'space': 800,
    'value_factor': 0.15,
    'min_value_factor': 1,
    'distance': 0.5*(1/1000),
    'value_distance': True,
    'max_distance': 3000,
}
#%% >>>> INFO Building Site Dictionary <<<<
#------------------------------------------------------------------------------
# |  INFO                                                                    |
# |                                                                          |
# |  dic_site : {                                                            |
# |      'value'            : (Reference_object, Reference_column),          |
# |      'space'            : capacity per unit area [value/m²],             |
# |      'value_factor'     : required share of reference value [-],         |
# |      'min_value_factor' : minimum allowed reduction factor [-],          |
# |      'distance'         : connection distance [m/value or m],            |
# |      'value_distance'   : True/False (scaled or fixed distance),         |
# |      'max_distance'     : absolute upper distance limit [m or None]      |
# |  }                                                                       |                                   |
# |                                                                          |
# |  --> If value_distance=True, the allowed distance scales with the        |
# |      reference value; otherwise a fixed limit is applied.                |
# -----------------------------------------------------------------------------
# |  ADDITIONAL INFO for dic_site['value']                                   |
# |                                                                          |
# |  'value' must be defined as: ('x', 'y')                                  |
# |                                                                          |
# |  The user can choose between two modes:                                  |
# |                                                                          |
# |  1) Site based on NETWORK results (x selects which network value):       |
# |     x can be one of the network result keys, e.g.:                       |
# |         'Network_total'     → total network value                        |
# |         'Connections_<n>'   → value of connection number <n> (dic_connect)|
# |         'Network_<type>'    → value of an energy-type network            |
# |                              (type from dic_connect['energy_type'])      |
# |                                                                          |
# |     y controls which geometry is used for the site:                      |
# |         y = 'None'        → connect to the closest network point         |
# |         y = <object_name> → connect to the geometry of the connected     |
# |                             objects of that type within the network      |
# |                             (must exist as df_now_<object_name>)         |
# |                                                                          |
# |  2) Site based on OBJECT data (x selects the energy object):             |
# |     x must be an energy_object declared in dic_obj (e.g. 'bdgs_heat_e'). |
# |     y must be a valid column name of that object (e.g. 'BEDARF_HEIZUNG').|
# |     If the object is clustered, the '<column>_sum' value is used.        |
# |     The site is then connected directly to that object geometry.         |
# -----------------------------------------------------------------------------
#------------------------------------------------------------------------------
# 3 Configuration of Sensitivity Analysis 
#------------------------------------------------------------------------------
#%%----------------------------------------------------------------------------
# 3.0 Sesitivity Analysis Dictionary
#------------------------------------------------------------------------------ 
dic_par_iteration = {
    "space_demand": {
                    "path": ("dic_site", "space"),
                    "values": [800, 900],
                                },
    
    "network_distance": {
                    "path": ("dic_connect", 1, "max_distance"),
                    "values": [0.10, 0.15],
                                },
}
#%% >>>> INFO Sensitivity Analysis <<<<
# -----------------------------------------------------------------------------
# |  INFO                                                                    |
# |                                                                          |
# |  dic_par_iteration : {                                                   |
# |      Parameter_Name : {                                                  |
# |          'path'   : (dictionary, nested_keys),                           |
# |          'values' : [v1, v2, v3, ...]                                    |
# |      }                                                                   |
# |  }                                                                       |
# |                                                                          |
# |  --> Defines which configuration parameters are varied in a              |
# |      sensitivity analysis.                                               |
# |                                                                          |
# |  --> Parameter_Name is a user-defined label for scenario                 |
# |      identification only (no functional influence).                      |
# |                                                                          |
# |  --> 'path' specifies the exact location of the parameter.               |
# |      The first element must be one of:                                   |
# |          'dic_site', 'dic_connect', 'dic_clust', 'dic_place'             |
# |      The following elements define the nested keys.                      |
# |                                                                          |
# |      Examples:                                                           |
# |          ('dic_site', 'space')                                           |
# |          ('dic_clust', 'bdgs_heat_e', 'max_distance')                    |
# |          ('dic_place', 1, 'requirement_value')                           |
# |                                                                          |
# |  --> 'values' contains the parameter values to be tested.                |
# |                                                                          |
# |  --> All paths must reference existing entries in the user-defined       |
# |      configuration dictionaries.                                         |
# -----------------------------------------------------------------------------
#%%
#  >>>>>>>>>>>> STOP HERE IF YOU DON'T KNOW WHAT YOU DO <<<<<<<<<<<<<<<<<<<<<<<

# ===============================================================================
# =========================== ADVANCED User Inputs ==============================
# ===============================================================================

#....................
# Energy Data source configuration
data_energy_path = 'energy_data'

dic_gpkg_data = {'DHN': 'DHN.gpkg',
                  'IndHeat': 'IndHeat.gpkg',
                   'Waste': 'waste.gpkg',
                  # 'ePlant': 'ch.bfe.elektrizitaetsproduktionsanlagen.gpkg',
                    # 'eTransL': 'eTrans_lines.gpkg',
                   # 'eTransS': 'eTrans_stations.gpkg',
                   # 'gas': 'erdgasnetz_schweiz.gpkg',
                   'bdgs_heat_e': 'schweiz_bdgs_heat_electricity.gpkg',
                   'ara': 'fernwaerme-angebot_HeatSupplier.gpkg',
                   # 'grWatHeat': 'grWater_energy.gpkg',
                    'ARA_and_KVA': 'ARA_and_KVA.gpkg',
                   
                  } # dictionary of all .gpkg data files

#....................
# Placement Data source configuration
data_placement_path = 'placement_data'

dic_gpkg_geo = {'DHM25': 'dhm25_swiss.parquet',
                # 'lDev': 'land_Development.parquet',
                # 'bdgs': 'bdgs.parquet',
                # 'grCov': 'forest.parquet',
                # 'protect': 'protect.parquet',
                # 'sSuit': 'sSuitability.parquet',
                # 'cRot': 'cRotation.parquet',
                # 'leisA': 'leisArea.parquet',
                # 'lUsage': 'lUsage.parquet',
                # 'traffA': 'traffArea.parquet',
                'placement_options': 'placement_options.parquet',
                'placement_options_wintes': 'placement_options_wintes.parquet'
                  } # dictionary of all .gpkg data files


#%% Check if the user inputs are valid

# 1) Check inconsistent object declarations
#------------------------------------------------------------------------------
# Collect declared Demand/Supply pairs from dic_obj
declared_pairs = set()
declared_objects = set()

for cat in ['Demand', 'Supply']:
    for spec in dic_obj.get(cat, {}).values():
        declared_pairs.add((spec['energy_object'], spec['value']))
        declared_objects.add(spec['energy_object'])

# Collect used pairs from dic_connect
used_pairs_connect = set()

for spec in dic_connect.values():
    d_obj, d_col, *_ = spec['demand']
    s_obj, s_col, *_ = spec['supply']

    if d_col != 'None':
        used_pairs_connect.add((d_obj, d_col))
    if s_col != 'None':
        used_pairs_connect.add((s_obj, s_col))

    for c in spec.get('connectors', []):
        c_obj, c_col, *_ = c
        if c_col is not None:
            used_pairs_connect.add((c_obj, c_col))

# dic_site check (object-mode only)
site_x, site_y = dic_site['value']
is_network_mode = (
    site_x == "Network_total" or
    site_x.startswith("Connections_") or
    site_x.startswith("Network_")
)

if not is_network_mode:
    if (site_x, site_y) not in declared_pairs:
        print(f"[ERROR] dic_site value {(site_x, site_y)} not declared in dic_obj.")
        sys.exit()

# Check: used in dic_connect but not declared in dic_obj
for pair in used_pairs_connect:
    if pair not in declared_pairs:
        print(f"[ERROR] {pair} used in dic_connect but not declared in dic_obj.")
        sys.exit()

# Check: declared in dic_obj but never used anywhere
for pair in declared_pairs:
    if pair not in used_pairs_connect:
        print(f"[WARNING] {pair} declared in dic_obj but not used in dic_connect, dic_clust or dic_site.")
        sys.exit()
# 2) dic_par_iteration must not reference dic_energy or dic_obj
#------------------------------------------------------------------------------
for name, spec in dic_par_iteration.items():
    path = spec['path']

    if path[0] in ['dic_energy', 'dic_obj']:
        print(f"[ERROR] dic_par_iteration '{name}' references forbidden dictionary '{path[0]}'.")
        sys.exit()

# 3) dic_par_iteration path must exist
#------------------------------------------------------------------------------
config_root = {
    'dic_site': dic_site,
    'dic_connect': dic_connect,
    'dic_clust': dic_clust,
    'dic_place': dic_place,
}

for name, spec in dic_par_iteration.items():
    path = spec['path']
    values = spec['values']

    # check path existence
    current = config_root.get(path[0])
    try:
        for key in path[1:]:
            current = current[key]
    except Exception:
        print(f"[ERROR] dic_par_iteration '{name}' has invalid path {path}.")
        sys.exit()

    # check baseline value included
    if current not in values:
        print(f"[WARNING] dic_par_iteration '{name}' does not include baseline value {current}.")
        sys.exit()

#%% transform new dictionaries to old structure 
def dic_energy_new_to_old(dic_energy_new):
    """
    Transforms NEW dic_energy format to OLD format.
    NEW: {ID: {'energy_object', 'value', 'operator', 'requirement_value'}}
    OLD: {(energy_object, value): [operator, requirement_value]}
    """
    dic_energy_old = {}

    for spec in dic_energy_new.values():
        key = (spec["energy_object"], spec["value"])
        dic_energy_old[key] = [spec["operator"], spec["requirement_value"]]

    return dic_energy_old

def dic_obj_new_to_old(dic_obj_new):
    """
    Transforms NEW dic_obj format to OLD format.
    NEW:
        {'Demand': {ID: {...}},
            'Supply': {ID: {...}}}
    OLD:
        {(energy_object, value): ['D' or 'S', factor, energy_type]}
    """
    dic_obj_old = {}

    for category, entries in dic_obj_new.items():

        # Map category to old identifier
        if category == "Demand":
            type_flag = "D"
        elif category == "Supply":
            type_flag = "S"
        else:
            continue  # ignore unexpected keys

        for spec in entries.values():
            key = (spec["energy_object"], spec["value"])
            dic_obj_old[key] = [
                type_flag,
                spec["factor"],
                spec["energy_type"]
            ]

    return dic_obj_old

dic_energy_user = copy.deepcopy(dic_energy)
dic_obj_user = copy.deepcopy(dic_obj)
dic_energy = dic_energy_new_to_old(dic_energy)
dic_obj = dic_obj_new_to_old(dic_obj)


#%% getters for user input

def get_res_unit_type():
    return res_unit_type

def get_res_unit():
    return res_unit


def get_res_SI_unit():
    return res_base_unit


def get_fac_SI_unit():
    return fac_base_unit


def get_sqr_size():
    return sqr_size

def get_sqr_size_exp():
    return sqr_size_exp

def get_result_folder():
    return result_folder

# Calculation configuration
def get_explore_raw_data():
    return explore_raw_data

def get_ReCalcData():
    return ReCalcData

# Energy Data source configuration
def get_data_energy_path():
    return data_energy_path

def get_dic_gpkg_data():
    return dic_gpkg_data

# Placement Data source configuration
def get_data_placement_path():
    return data_placement_path

def get_dic_gpkg_geo():
    return dic_gpkg_geo

def get_dic_par_iteration():
    return dic_par_iteration

# Configs BASE CASE (energy_system_models)
def get_dic_energy_user():
    return dic_energy_user

def get_dic_energy():
    return dic_energy

def get_dic_place():
    return dic_place

def get_dic_obj_user():
    return dic_obj_user

def get_dic_obj():
    return dic_obj

def get_dic_clust():
    return dic_clust

def get_dic_connect():
    return dic_connect


def get_dic_site():
    return dic_site


#%% Main Function Call

# ===============================================================================

def main():
    PATHFNDR_main_framework.PATHFNDR_main_framework()

if __name__ == "__main__":
    main()


