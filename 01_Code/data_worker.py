# -*- coding: utf-8 -*-
"""
Created on Mon Apr 19 19:17:01 2021

@author: Simon In-Albon
"""

# from datetime import datetime
import pandas as pd
import shapely
import geopandas as gpd
import numpy as np
from tqdm import tqdm
import os
from scipy.spatial import cKDTree
import sys
from operator import itemgetter
import time
from datetime import datetime
from collections import defaultdict
import networkx as nx
from itertools import chain

# import datetime as date
# import numpy as np

#%% Function that creates a .txt file with the inputs

def create_inputs_as_txt(variable_dic, path, overall_time, filename="input_variables.txt"):
    # os.makedirs(path, exist_ok=True)  # create folder if it doesn't exist
    file_path = os.path.join(path, filename)

    timestamp = datetime.now().strftime("%Y-%m-%d  %H:%M:%S")
    username = os.getlogin()

    header = (
        "\n\n============================================================\n\n"
        " INPUT VARIABLES\n\n"
        f" CREATED: {timestamp}\n"
        f" RUN BY: {username}\n"
        f" This took {overall_time} min in total.\n\n"
        "============================================================\n\n\n"
    )
    
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(header)
        for name, value in variable_dic.items():
            f.write(f"{name} = {repr(value)}\n\n")

    print("---- Variable inputs are saved. ----")
 

#%% Function which creats an empty DataFrame with two levels of Header an a specific Index

def df_multiHead(header1, header2, header_names, indexes, value):
    header1_new = list()
    for k in range(0, len(header1)):
        header1_new.extend([header1[k]]*len(header2))
    header2 = header2*len(header1)
    header1 = header1_new
    tuples = list(zip(*[header1 , header2]))
    header = pd.MultiIndex.from_tuples(tuples, names=header_names)
    df = pd.DataFrame(value, index=indexes, columns=header)
    return(df)
#%%
def flatten_columns(df):
    """
    Flatten multi-level columns of a DataFrame into a single level.
    
    Parameters:
    - df (pd.DataFrame): The DataFrame with multi-level columns.

    Returns:
    - pd.DataFrame: DataFrame with flattened single-level columns.
    """
    df.columns = ['*'.join(col).strip() for col in df.columns.values]
    return df
#%%
def unflatten_columns(df, separator='*'):
    """
    Convert single-level columns of a DataFrame back to multi-level columns.
    
    Parameters:
    - df (pd.DataFrame): The DataFrame with single-level columns.
    - separator (str): The separator used in single-level column names to denote different levels.

    Returns:
    - pd.DataFrame: DataFrame with multi-level columns.
    """
    # Split column names by separator and create a MultiIndex
    columns = [col.split(separator) for col in df.columns]
    df.columns = pd.MultiIndex.from_tuples(columns)
    return df

#%% convert string into a list if they have a <,>
def str_to_list(s):
    """
    Converts a comma-separated string to a list.
    
    Parameters:
    - s (str): The string to convert.

    Returns:
    - list: The converted list.
    """
    try:
        return s.split(',')  # Split the string by commas and return as list
    except AttributeError:
        return s  # Return the original value if it's not a string

#%%
def convert_column_types(gdf):
    """
    Converts columns in a GeoDataFrame to their appropriate data types.
    
    Parameters:
    - gdf (gpd.GeoDataFrame): The GeoDataFrame to process.

    Returns:
    - gpd.GeoDataFrame: The GeoDataFrame with columns converted to appropriate types.
    """
    for column in gdf.columns:
        if gdf[column].dtype == object:
            try:
                gdf[column] = pd.to_numeric(gdf[column])
            except ValueError:
                # If conversion fails, keep the original object type
                pass
    return gdf
#%% dictionary to convert string code like 'eq' to a string '='

def string_operator_converter(str_op):
    """
    str_op : string that has 'eq', 'ge' ect in it

    Returns: string like '=', '>='
    -------
    """
    dic_str_op = {
        'eq' : '=',
        'ge' : '>=',
        'le' : '<=',
        'gt' : '>',
        'lt' : '<'
        }
    return dic_str_op[str_op]

#%% function to expand a Series of Polygons to a certain dimension
def sqr_expansion(df_poly, size):
    """
    df_poly : geoDataFrame
        with polygon as geometry.
    size : int
        size of the expanded square in [m].

    Returns
    -------
    df_poly : geoDataFrame
        same geoDataFrame but with the expanded square polygon.

    """
    half_side = size/2 
    centroid = df_poly[('Basic','geometry')].centroid
    
    for ind in df_poly.index:
        df_poly.loc[ind, ('Basic','geometry')] = shapely.geometry.Polygon([
            (centroid[ind].x-half_side, centroid[ind].y-half_side), (centroid[ind].x+half_side, centroid[ind].y-half_side), 
            (centroid[ind].x+half_side, centroid[ind].y+half_side), (centroid[ind].x-half_side, centroid[ind].y+half_side)])

    return df_poly
    
#%% function to merge touching and overlaping polygons into one

def merge_touch_polygons_old(polys):
    """
    Parameters
    ----------
    polys : series of polygons that should be merged if they touch or overlap each other

    Returns
    -------
    df_polys : Multihead Dataframe with merged polygons and their calculated area. Polygons that stand alone are still included here.

    """
    # print('----- Merge Polygons -----')
    #check all polygons if they touch (using "intersects()")
    lst_sqr = polys.index.tolist()
    lst_sqr_merged = []
    merged_polys = pd.Series()
    # go throu all squares
    for value in lst_sqr:
        #only check the square if it isn't yet in the list of squares that are merged
        if value not in lst_sqr_merged:
            mask = polys.geometry.intersects(polys[value])
            if mask.sum() > 1:
                # this value must be part of a merged square
                lst_sqr_merged.append(value)
                merge_sqr = pd.Series(polys.index[mask])
                # check every area in that serie if it touches any other, such that it builds a cluster
                k = 1 
                while k < len(merge_sqr):
                    lst_sqr_merged.append(merge_sqr[k])
                    mask = polys.intersects(polys[merge_sqr[k]])
                    merge_sqr = pd.concat([merge_sqr, pd.Series(polys.index[mask])])
                    #drop all dublicates and reset the index
                    merge_sqr.drop_duplicates(inplace=True)
                    merge_sqr.reset_index(drop=True, inplace=True)
                    k+=1
                # merge the found cluster
                new_poly = shapely.ops.unary_union(polys[merge_sqr])
                merged_polys = pd.concat([merged_polys, pd.Series(new_poly)])
                merged_polys.reset_index(drop=True, inplace=True)
    
    #check if one of the merged polygons is a multipolygon
    #this happens if the areas only touch in one point
    #then we split them into two normal polygons
    merged_polys_new = merged_polys.copy()
    for k in merged_polys:
        if  type(k)== shapely.geometry.multipolygon.MultiPolygon:
            #drop the multipoly in the new merge series
            merged_polys_new = merged_polys_new[merged_polys_new != k]
            #iterate every polygon in this multipolygon and add it to the new merged poly series
            for j in k.geoms:
                merged_polys_new = pd.concat([merged_polys_new, pd.Series(j)])
    merged_polys_new.reset_index(drop=True, inplace=True)
    
    # form a new list of polygons
    old_polys = list(set(lst_sqr)-set(lst_sqr_merged))
    final_polys = polys[old_polys]
    final_polys = pd.concat([final_polys, merged_polys_new])
    final_polys.reset_index(drop=True, inplace=True)
    
    #creating the final geodataframe and calculate area of all polygons
    df = df_multiHead(['Basic'], ['area_km2'], ['source', 'data'], [], np.nan)
    df_polys = gpd.GeoDataFrame(df, geometry=final_polys, crs = 'EPSG:2056')
    #rename column of geometry
    df_polys = df_polys.rename(columns={'':'geometry'}, level=1)
    df_polys = df_polys.rename(columns={'geometry':'Basic'}, level=0)
    #reset geometry of df_calc
    df_polys = df_polys.set_geometry(('Basic', 'geometry'))
    df_polys[('Basic','area_km2')] =  df_polys.geometry.area*10**(-6)
    return df_polys

#%% function to merge touching and overlaping polygons into one

def merge_touch_polygons(polys):
    """
    Parameters
    ----------
    polys : series of polygons that should be merged if they touch or overlap each other

    Returns
    -------
    df_polys : Multihead Dataframe with merged polygons and their calculated area. Polygons that stand alone are still included here.

    """
    # print('----- Merge Polygons -----')
        
    # 1. Reset index for safety
    polys = polys.reset_index(drop=True)
    sindex = polys.sindex
    
    # 2. Build adjacency graph
    G = nx.Graph()
    for idx, geom in polys.geometry.items():
        possible_matches = list(sindex.query(geom, predicate="intersects"))
        for j in possible_matches:
            if idx < j:
                G.add_edge(idx, j)
    
    # 3. Find clusters (connected components)
    clusters = list(nx.connected_components(G))
    
    # 4. Merge each cluster
    merged_polys = []
    for cluster in clusters:
        to_merge = polys.geometry.loc[list(cluster)]
        merged = shapely.ops.unary_union(to_merge)
        merged_polys.append(merged)
    
    # 5. Add untouched polygons (not in any cluster)
    all_clustered = set().union(*clusters)
    untouched = [i for i in polys.index if i not in all_clustered]
    all_polys = [polys.geometry[i] for i in untouched] + merged_polys
    
    # 6. Filter/explode: only Polygon and MultiPolygon, flatten GeometryCollections
    clean_polys = []
    for g in all_polys:
        if g.geom_type == "Polygon":
            clean_polys.append(g)
        elif g.geom_type == "MultiPolygon":
            clean_polys.extend(g.geoms)
        elif g.geom_type == "GeometryCollection":
            for part in g.geoms:
                if part.geom_type == "Polygon":
                    clean_polys.append(part)
                elif part.geom_type == "MultiPolygon":
                    clean_polys.extend(part.geoms)
        # Ignore all others
    
    # 7. Final output as GeoSeries
    final_polys = gpd.GeoSeries(clean_polys, crs=polys.crs).reset_index(drop=True)
    #creating the final geodataframe and calculate area of all polygons
    df = df_multiHead(['Basic'], ['area_km2'], ['source', 'data'], [], np.nan)
    df_polys = gpd.GeoDataFrame(df, geometry=final_polys, crs = 'EPSG:2056')
    #rename column of geometry
    df_polys = df_polys.rename(columns={'':'geometry'}, level=1)
    df_polys = df_polys.rename(columns={'geometry':'Basic'}, level=0)
    #reset geometry of df_calc
    df_polys = df_polys.set_geometry(('Basic', 'geometry'))
    df_polys[('Basic','area_km2')] =  df_polys.geometry.area*10**(-6)
    # print('----- Finished Merge Polygons -----')
    return df_polys


#%% cluster algorithm         
def grid_cluster(df_grid, cluster_size):
    
    # sort dataframe such that y coordinates are first 
    df_grid.sort_values(by=['x', 'y'], ascending=[True, True], inplace=True)
    df_grid.reset_index(inplace=True)
    df_grid.drop(['index'], axis=1, inplace=True)
    
    # check the number of points in one cluster
    min_x = df_grid['x'].diff().dropna()
    min_x = min_x[min_x>0].min()
    min_y = df_grid['y'].diff().dropna()
    min_y = min_y[min_y>0].min()
    
    if (min_x >= cluster_size) | (min_y >= cluster_size):
        print ('\n=====================================================================')
        print( '---ERROR---\n wrong cluster size with this grid!')
        print ('\n=====================================================================')
        exit
    
    cluster_points = int(((cluster_size/min_x)+1)*((cluster_size/min_y)+1))
    
    # function that creats a list of all coordinates needed
    def cluster_fitter(df, coordinate, step):
        min_c = df[coordinate].min()
        max_c = df[coordinate].max()
        num = int((max_c-min_c)/step)
        rest_dist = ((max_c-min_c) % step)
        if rest_dist != 0:
            # if the step size does not fit the current grid
            lost_max = len(df[df[coordinate] > (max_c - rest_dist)])
            lost_min = len(df[df[coordinate] < (min_c + rest_dist)])
            # on which side do we loose less data?
            if lost_max >= lost_min:
                lst_coords = list(range(int(min_c),int(min_c+(num+1)*step),step))
            else:
                lst_coords = list(range(int(min_c+rest_dist),int(max_c+step),step))
        else:
            lst_coords = list(range(int(min_c),int(max_c+step),step))
        
        return lst_coords
    
    # define all x,y-coordinates
    lst_x_coords = cluster_fitter(df_grid[['x','y']], 'x', cluster_size)
    lst_y_coords = cluster_fitter(df_grid[['x','y']], 'y', cluster_size)
    
    print('----- pivot your dataframe -----')
    df_grid['total'] = df_grid[df_grid.columns.tolist()].apply(lambda row: np.array(row), axis=1)
    df_pivot = df_grid.pivot(index = 'y', columns='x', values= 'total')
    
    #initialize new DF for clustered data
    df_cluster = pd.DataFrame(columns=['x', 'y', 'cluster'], index= list(range(int(len(lst_y_coords)*len(lst_x_coords)))))
    
    print('----- start cluster your data -----')
    counter = 0
    for k in tqdm(range(len(lst_x_coords)-1)):
        for j in range(len(lst_y_coords)-1):
            if df_pivot.loc[lst_y_coords[j]:lst_y_coords[j+1], lst_x_coords[k]:lst_x_coords[k+1]].isna().any().any():
                pass
            else:
                df_cluster.loc[counter,'x'] = (lst_x_coords[k]+lst_x_coords[k+1])/2
                df_cluster.loc[counter,'y'] = (lst_y_coords[j]+lst_y_coords[j+1])/2
                df_cluster.loc[counter,'cluster'] = np.vstack(df_pivot.loc[lst_y_coords[j]:lst_y_coords[j+1], lst_x_coords[k]:lst_x_coords[k+1]].to_numpy().ravel())
            counter += 1
    
    df_cluster.dropna(inplace = True)
    df_cluster = df_cluster.reset_index()
    df_cluster.drop(['index'], axis=1, inplace=True)

    return df_cluster              

#%% Function that makes shapely points out of coordinates

def coor_to_points(df_coor):
    
    # x and y must be float
    df_coor.x = df_coor.x.astype(float)
    df_coor.y = df_coor.y.astype(float)
    
    # Define chunk size
    df_coor['geo'] = pd.Series([None] * len(df_coor), dtype='object')
    chunk_size = 10000
    # Process DataFrame in chunks
    for i in tqdm(range(0, len(df_coor), chunk_size)):
        if (i+chunk_size) <= len(df_coor):
            df_coor.loc[i:i+chunk_size, 'geo'] = df_coor[i:i+chunk_size].apply(lambda row: shapely.Point([row['x'], row['y']]), axis=1)
        else:
            df_coor.loc[i:, 'geo'] = df_coor[i:].apply(lambda row: shapely.Point([row['x'], row['y']]), axis=1)

    return df_coor['geo']
    
#%% function that creates from a df with xy-coordinates of a point, a squared polygon
def point_to_sqr(df_points, width = 50):
    """
    Convert x, y coordinates in a DataFrame to square polygons of a given width.
    
    Parameters:
        df (pd.DataFrame): The DataFrame containing x, y coordinates.
        width (float): The width of the square polygon in meters. Default is 50 meters.
    
    Returns:
        pd.Series: A series of shapely Polygon objects.
        """
    
    def sqr_polys (df_slice, side):

        half_width = side / 2
        
        # Calculate the bounds of the square polygons for all points
        x_min = df_slice['x'] - half_width
        x_max = df_slice['x'] + half_width
        y_min = df_slice['y'] - half_width
        y_max = df_slice['y'] + half_width
        # Create the square polygons by using vectorized operations
        polygons = [
            shapely.geometry.Polygon([(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)])
            for xmin, xmax, ymin, ymax in zip(x_min, x_max, y_min, y_max)
        ]
        
        return pd.Series(polygons)
    
    df_points['geo'] = pd.Series([None] * len(df_points), dtype='object')
    chunk_size = 100000
    # Process DataFrame
    print('----- assign all x,y coordinates to a square polygon -----')
     
    for i in tqdm(range(0, len(df_points), chunk_size)):
        if (i+chunk_size) <= len(df_points):
            poly_chunk = sqr_polys(df_points[i:i+chunk_size], width)
            df_points.loc[i:i+chunk_size-1, 'geo'] = poly_chunk.values
     
        else:
            poly_chunk = sqr_polys(df_points[i:i+chunk_size], width)
            df_points.loc[i:, 'geo'] = poly_chunk.values

    return df_points['geo']
    
#%% function to assign points to 1km2 grid

def grid_assignment(df_raw, df_1km2):
    """
    Parameters
    ----------
    df_raw : Dataframe with 'x' and 'y' columns of the coordinate
        needs to be sorted the same way as df_1km2 for high performance.
    
    df_1km2 : GeoDataFrame of 1km2 grid over all switzerland.
    
    Returns
    -------
    pd.Series: that assigns every point to a grid
    the points with no assignment will have 'grid_number'= NaN

    """
    
    # check that both are the same datatype
    if type(df_raw.x[0]) != np.float64:
        df_raw.x = df_raw.x.astype(np.float64)
        df_raw.y = df_raw.y.astype(np.float64)

    # filter and assign all data points to the square grid
    df_raw['grid_number'] = pd.Series(-1, index=range(len(df_raw)), dtype='int64')

    for k in tqdm(range(len(df_1km2))): 
        slice_idx = df_raw[(df_raw['x']>= df_1km2.geometry[k].bounds[0]) & (df_raw['y']>= df_1km2.geometry[k].bounds[1]) & (df_raw['y']< df_1km2.geometry[k].bounds[3]) & (df_raw['x']< df_1km2.geometry[k].bounds[2])].index
        df_raw.loc[slice_idx, 'grid_number'] = k
    
    df_raw['grid_number'] = df_raw['grid_number'].replace(-1, np.nan)
    return df_raw['grid_number']

#%% function to drop points outside switzerland square

def main_swiss_square(df_raw):
    #drop all points far out of switzerland
    start_x = 2485410
    end_x = 2833859
    start_y = 1075269
    end_y = 1295934
    df_raw = df_raw[(df_raw['x']<=end_x) & (df_raw['x']>=start_x) & (df_raw['y']<=end_y) & (df_raw['y']>=start_y)]
    df_raw.reset_index(inplace=True)
    df_raw.drop(['index'], axis=1, inplace=True)
    
    return df_raw

#%%
def find_data_path(path):
    username = os.getlogin()
    new_path = path.replace("username", username)
    return new_path

#%% input is a Serie of points, output is a concave hull that could even be a linestring in the extreme of only two points
def points_to_concavehull(serie_points, ratio = 0.05):
    multi_point = shapely.geometry.MultiPoint(serie_points.tolist())
    concave_hull = shapely.concave_hull(multi_point, ratio = ratio)
    
    return concave_hull

#%% used to impot gpkg files that have lists in it with numbers and strings
def convert_series_elements(series):
    """
    Convert strings in lists within a pandas Series to int or float if possible.
    If no float in the list has a non-zero decimal, convert all floats to integers.
    Handles None or non-list elements by temporarily removing them.
    
    Args:
        series (pd.Series): A pandas Series containing lists, None, or other types.

    Returns:
        pd.Series: A pandas Series with lists converted appropriately, and None reintegrated.
    """
    def is_float(value):
        if '.' in value or 'e' in value.lower():
            return value.replace('.', '', 1).replace('e', '', 1).replace('-', '', 1).isdigit()
        return False

    def is_int(value):
        return value.lstrip('-').isdigit()

    def has_nonzero_decimal(lst):
        """Check if any float in the list has a non-zero decimal part."""
        for item in lst:
            if isinstance(item, float) and not item.is_integer():
                return True
        return False

    def convert_list(lst):
        """Convert strings in a list to int or float where possible, and handle decimals."""
        if lst == [""]:
           return []
        # Step 1: Convert strings to numeric types
        converted_list = [
            int(item) if isinstance(item, str) and is_int(item) else
            float(item) if isinstance(item, str) and is_float(item) else
            item
            for item in lst
        ]

        # Step 2: Check for non-zero decimals
        if not has_nonzero_decimal(converted_list):
            # Convert all floats to integers if no non-zero decimal exists
            converted_list = [int(item) if isinstance(item, float) else item for item in converted_list]

        return converted_list

    def process_element(element):
        """Process individual elements in the Series."""
        if isinstance(element, list):
            return convert_list(element)
        return element  # Return non-list elements as is

    # Step 1: Remove None values and store their indices
    non_none_indices = series.notna()
    non_none_series = series[non_none_indices]

    # Step 2: Process the non-None values
    processed_series = non_none_series.apply(process_element)

    # Step 3: Reintegrate None values
    final_series = pd.Series(index=series.index, dtype=object)
    final_series.loc[non_none_indices] = processed_series
    final_series.loc[~non_none_indices] = None

    return final_series

#%% DBSCAN with User defined sum instead of min_sample

# import numpy as np
# import pandas as pd
from sklearn.neighbors import KDTree

def custom_dbscan(df, eps, min_value_sum, min_objects, value):
    """
    Perform DBSCAN-like clustering where clusters are formed if the sum of 'value' column meets a threshold.

    Parameters:
        df (pd.DataFrame): Input DataFrame with 'x', 'y', and 'value' columns.
        eps (float): Radius for neighborhood search.
        min_value_sum (float): Minimum sum of 'value' column to form a cluster.
        value (string): name of the column according to which the cluster is build.

    Returns:
        pd.Series: Cluster labels for each point (-1 for noise).
    """
    # Extract spatial positions and values
    positions = df[['x', 'y']].values  # Spatial positions
    values = df[value].values       # Values column


    # ---- GUARD: no points to cluster ----         inserted 28.10.25
    # 'positions' is expected to be a numpy array shaped (n, 2)
    # If n == 0, KDTree will raise: "Found array with 0 sample(s)..."
    if positions is None or getattr(positions, "size", 0) == 0:
        # Return a "noise" label series (all -1) of the right length, or empty if df is empty
        print("I run into the data_worker-guard. Strange things could happen.")
        n = len(df) if df is not None else 0
        return pd.Series([-1] * n, index=(df.index if n else None), name="cluster_no")


    # KDTree for efficient spatial neighbor search
    tree = KDTree(positions, leaf_size=40)
    labels = -np.ones(len(df), dtype=int)  # Initialize all points as noise
    cluster_id = 0
    visited = np.zeros(len(df), dtype=bool)

    def region_query(point_idx):
        """Find neighbors within eps and calculate the value sum."""
        neighbors_idx = tree.query_radius([positions[point_idx]], r=eps)[0]
        value_sum = values[neighbors_idx].sum()
        return neighbors_idx, value_sum

    def expand_cluster(point_idx, neighbors_idx):
        """Expand the cluster from the current point."""
        cluster_points = list(neighbors_idx)
        labels[point_idx] = cluster_id
        i = 0
        while i < len(cluster_points):
            current_idx = cluster_points[i]
            if not visited[current_idx]:
                visited[current_idx] = True
                new_neighbors, value_sum = region_query(current_idx)
                if value_sum >= min_value_sum:
                    for neighbor_idx in new_neighbors:
                        if labels[neighbor_idx] == -1:  # Add noise points
                            cluster_points.append(neighbor_idx)
                            labels[neighbor_idx] = cluster_id
            if labels[current_idx] == -1:
                labels[current_idx] = cluster_id
            i += 1

    # Main DBSCAN loop
    for point_idx in range(len(df)):
        if visited[point_idx]:
            continue
        visited[point_idx] = True
        neighbors_idx, value_sum = region_query(point_idx)
        if value_sum >= min_value_sum:
            expand_cluster(point_idx, neighbors_idx)
            cluster_id += 1
            
    # Enforce minimum object count for clusters
    cluster_sizes = pd.Series(labels).value_counts()
    invalid_clusters = cluster_sizes[cluster_sizes < min_objects].index
    
    # Relabel clusters with insufficient points as noise
    for invalid_cluster in invalid_clusters:
        labels[labels == invalid_cluster] = -1
    
    # Ensure cluster labels are continuous
    unique_labels = np.unique(labels)
    label_mapping = {old_label: new_label for new_label, old_label in enumerate(unique_labels) if old_label != -1}
    label_mapping[-1] = -1  # Keep noise as -1
    labels = np.array([label_mapping[label] for label in labels])

    return pd.Series(labels, index=df.index, name='cluster_no')

#%% 

def convert_multipoint_to_point(series):
    """
    Converts a Series of MultiPoint geometries to Point geometries if they contain only one point.
    Raises an error if any MultiPoint contains more than one point.

    Parameters:
        series (pd.Series): A Series containing MultiPoint geometries.

    Returns:
        pd.Series: A Series of Point geometries.
    """
    def process_multipoint(mp):
        if isinstance(mp, shapely.MultiPoint):
            points = list(mp.geoms)  # Extract individual points
            if len(points) == 1:
                return points[0]  # Return the single point
            else:
                raise ValueError(f"MultiPoint contains multiple points: {mp}")
        elif isinstance(mp, shapely.Point):
            return mp  # If it's already a Point, return as is
        else:
            raise TypeError(f"Invalid geometry type: {type(mp)}")

    return series.apply(process_multipoint)

#%% FUNCTION ONLY FOR CONNECTION_FINDER
#recursion depth first search with cKDTree filter, finds matches over multiple connection points 

def recursive_dfs(current_object, current_points, total_value, total_length, 
                  current_limit, current_level, path, arr_objects, df_objects, 
                  dic_objs, dic_points, kdtrees, valid_paths, initial_value, 
                  exist_paths, supply):
    """   
    Recursively searches for valid paths using DFS with dynamic distance limits.

    Parameters
    ----------
    current_object : shapely object
        The current shapely object that is searching for connection
    current_points : array
        Array wich holds points that are on the border of the current_object
    total_value : float
        Sum of all demand or supply of the current path
    total_length : float
        Sum of the total length the current path has
    current_limit : float
        The dynamically adjusted distance limit 
    current_level : index in objects list           
        The current object level
    path : list
        List storing the current path
    arr_objects : list
        List of numpy arrays [(x, y] containing coordinates of points
    df_objects : list
        List of dataframes containing all information of the objects
    dic_objs: list
        List with dictionnary that tells what points to what object belong
    dic_points: list
        List with dictionnary that tells what object to what points in the arr_object has
    kdtrees : list
        List of cKDTree objects for fast nearest neighbor search
    valid_paths : list
        List to store valid paths
    initial_value : float
        float that stores the initial value of the demand or supply (only used if supply matchmaking)
    exist_paths: list
        List of all existing paths, same format as valid paths
    supply : boolean
        true means the current matchmaking is comming from supply to demand
    Returns
    -------
    None.

    """
    # Filter for valide points with an increased max distance
    dist_factor = 1.5
    next_tree = kdtrees[current_level]  # KDTree for the next object
    
    #check if the current level has polygons or linestrings;  COULD be a problem if there are mixed geometry types
    if (type(df_objects[current_level].loc[df_objects[current_level].index[0],'geometry']) == shapely.geometry.polygon.Polygon) or (
            type(df_objects[current_level].loc[df_objects[current_level].index[0],'geometry']) == shapely.geometry.linestring.LineString):
        #check kdTree with additional distance factor bcs it's only points from the linestring or polygon
        kd_neighbors = next_tree.query_ball_point(current_points[:,:2], current_limit*dist_factor)
        kd_neighbors = np.unique(np.concatenate(kd_neighbors))
        if len(kd_neighbors) > 0:
            # collect all objects that are valid
            valid_coords = arr_objects[current_level][kd_neighbors,:2]
            coords_as_tuples = [tuple(row) for row in valid_coords]
            valid_obj = list(itemgetter(*coords_as_tuples)(dic_points[current_level]))
            #erase all dublicates
            valid_obj = list(dict.fromkeys(valid_obj))
        else:
            valid_obj = []

    #if they are points- take the faster version
    else:
        #check kdTree
        kd_neighbors = next_tree.query_ball_point(current_points[:,:2], current_limit)
        flat = np.fromiter(chain.from_iterable(kd_neighbors), dtype=np.int64)
        kd_neighbors = np.unique(flat)
        if len(kd_neighbors) > 0:
            valid_obj = df_objects[current_level].index[kd_neighbors].tolist()
        else:
            valid_obj = []
    # check all valid_obj if their distance is within the limits
    # calculate every distance (this takes a lot of comutational time)
    distances = [current_object.distance(obj) for obj in df_objects[current_level].loc[valid_obj, 'geometry']]
    # filter the valid_obj
    valid_neighbors = list(np.array(valid_obj)[distances <= current_limit])
    #filter distances
    distances = list(np.array(distances)[distances <= current_limit])

    #--------------------------------------------------------------------------
    # check if there are some paths allready used - prefere them
    if supply:
        existing_con = [item[0][len(item[0])-2-current_level] for item in exist_paths if item[0][len(item[0])-1-current_level] == path[-1]]
    else:
        existing_con = [item[0][current_level+1] for item in exist_paths if item[0][current_level] == path[-1]]
    # drop dublicates
    existing_con = list(dict.fromkeys(existing_con))    
    # check if any of those objects are in valid_neighbors and change their distance to zero
    distances = [0 if valid_neighbors[i] in existing_con else distances[i] for i in range(len(valid_neighbors))]    
    #if they are not jet in valid_neighbors - append them to valid neighbors and add a zero to the distance list
    existing_con = [item for item in existing_con if item not in valid_neighbors]
    # filter to only the objects that still have value (exist in df_objects)
    existing_con = list(set(existing_con) & set(df_objects[current_level].index.tolist()))
    if len(existing_con) > 0:
        # print(f'appending: {existing_con}')
        valid_neighbors.extend(existing_con)
        distances.extend([0]*len(existing_con))
    #--------------------------------------------------------------------------
    current_data_name, = set(df_objects[current_level].columns)-{'geometry', 'dist_max'}  
    #if the next level is the final one, check if the valid_neighbors fulfill the demand/supply
    if ((current_level+1) == len(arr_objects)) and (len(valid_neighbors) > 0):
        # if it's a supply matchmaking the match check is comparing the initial_value to all connected demand
        if supply:          
            distances = np.array(distances)[df_objects[current_level].loc[valid_neighbors,current_data_name]+total_value>=initial_value].tolist()
            valid_neighbors = list(df_objects[current_level].loc[valid_neighbors][df_objects[current_level].loc[valid_neighbors,current_data_name]+total_value>=initial_value].index)
            #store all valid neighbor paths at once
            valid_paths.extend([((path + [valid_neighbors[j]])[::-1], total_length+distances[j], initial_value) for j in range(len(valid_neighbors))])
        else:
            distances = np.array(distances)[df_objects[current_level].loc[valid_neighbors,current_data_name]>=total_value].tolist()
            valid_neighbors = list(df_objects[current_level].loc[valid_neighbors][df_objects[current_level].loc[valid_neighbors,current_data_name]>=total_value].index)
            #store all valid neighbor paths at once
            valid_paths.extend([((path + [valid_neighbors[j]]), total_length+distances[j], total_value) for j in range(len(valid_neighbors))])
        # back one level up
        return
    
    else:
        
        # if valid neighbors were found, go one lever further down, else return one level up
        if len(valid_neighbors) > 0:
            
            # Recursively explore valid paths
            for obj in valid_neighbors:
                next_object = df_objects[current_level].loc[obj, 'geometry']
                next_points = arr_objects[current_level][dic_objs[current_level][obj][0]:dic_objs[current_level][obj][1],:]
                next_total_value = total_value + df_objects[current_level].loc[obj, current_data_name]
                next_total_length = total_length + np.array(distances)[np.array(valid_neighbors) == obj][0]
                if supply: 
                    next_limit = current_limit - np.array(distances)[np.array(valid_neighbors) == obj][0]
                else:
                    next_limit = current_limit - np.array(distances)[np.array(valid_neighbors) == obj][0] + df_objects[current_level].loc[obj, 'dist_max']
                
                next_total_value = total_value + df_objects[current_level].loc[obj, current_data_name]
                # go one level deeper
                recursive_dfs(next_object, next_points, next_total_value, next_total_length, 
                              next_limit, current_level + 1, path + [obj], arr_objects, 
                              df_objects, dic_objs, dic_points, kdtrees, valid_paths, initial_value, exist_paths, supply)
        else:
            return
    
#%% FUNCTION ONLY FOR CONNECTION_FINDER
def max_dist_connection (df_basic, data_column, calc_type, limit):
    if calc_type == 'fix':
        df_basic['dist_max'] = limit
    elif calc_type == 'variable':
        #if the distance is variable but there is no limitation the max distance is 0 - otherwise the program runns wild
        if data_column == 'None':
            df_basic['dist_max'] = 0    
        else:
            df_basic['dist_max'] = df_basic[data_column]*limit
    
    return(df_basic)
#%% FUNCTION ONLY FOR CONNECTION_FINDER
# Converts a Series of LineStrings into a nested list of evenly spaced (x, y) tuples.
def lines_to_tuple_list(series, step):
    nested_points = []
    # Process each LineString
    for line in series.values:
        if line.is_empty or line.length == 0:
            nested_points.append([])  # Add an empty list for empty lines
            continue  # Skip processing for empty lines
    
        num_points = int(line.length // step) + 1  # Number of points along the line
        points = [(x, y) for x, y, _ in [tuple(line.interpolate(i * step).coords[0]) for i in range(num_points)]]            
        nested_points.append(points)  # Append the list of points for this line
    return nested_points  # Returns a list of lists of (x, y) tuples
#%% FUNCTION ONLY FOR CONNECTION_FINDER
#function that gets an dataframe and the level dic, brings back the array and maybe the dictionary for the created points
#check if a level is made out of points, linestrings or polygons --> create accordingly the points in an array
def df_to_array (df_sorted, data_name, df_name, dic_levels):
    # check what type of object is in this df
    if (dic_levels[df_name] == shapely.geometry.polygon.Polygon) or (dic_levels[df_name] == shapely.geometry.linestring.LineString):
        if dic_levels[df_name] == shapely.geometry.polygon.Polygon:
            # get all corner points of the polygon
            new_points = [list(poly.exterior.coords[:-1]) for poly in df_sorted.geometry]

        elif dic_levels[df_name] == shapely.geometry.linestring.LineString:
            # get all points on the linestring
            step_size = 1000  # Distance between points
            new_points = lines_to_tuple_list(df_sorted.geometry, step_size)            
        
        corner_array = np.array([point for poly in new_points for point in poly])
        #creating lookup table (input: point, output: object name)
        dic_points = {tup: df_sorted.index.tolist()[i] for i, lst in enumerate(new_points) for tup in lst}
        #creating lookup table (input: object name, output: set in corner_array)
        dic_obj = {}
        dummy = 0
        value_array = np.empty((0, 2))
        for k in range(len(new_points)):
            dic_obj[df_sorted.index.tolist()[k]] = (dummy, dummy+len(new_points[k]))
            dummy += len(new_points[k])
            #values
            col1_value = df_sorted.loc[df_sorted.index.tolist()[k],data_name]
            col2_value = df_sorted.loc[df_sorted.index.tolist()[k],'dist_max']
            # create columns
            col1 = np.full((len(new_points[k]), 1), col1_value)
            col2 = np.full((len(new_points[k]), 1), col2_value)
            arr = np.hstack((col1, col2))
            value_array = np.vstack([value_array, arr])
        del dummy
        # final_array =  np.hstack((corner_array, value_array))
        final_array = corner_array
    # if it's points, easy solved
    elif dic_levels[df_name] == shapely.geometry.point.Point:
        # final_array = np.array([[p.x, p.y, v1, v2] for p, v1, v2 in zip(df_sorted["geometry"], df_sorted[data_name], df_sorted['dist_max'])])
        final_array = np.array([[p.x, p.y] for p in df_sorted["geometry"]])            
        dic_points = {tuple(coord): idx for coord, idx in zip(final_array[:, :2], df_sorted.index)}
        dic_obj = {idx:(coord, coord+1) for idx, coord in zip(df_sorted.index, list(range(len(final_array))))}
    # if an multipoint, multilinestring or multipolygon is entered - stop the calculation! the raw data needs to be updated
    else:
        print(f'----- !!!TypeError!!!! -----\nThe objects <<{df_sorted.index.tolist()[0:3]}, ....>> are the type {type(df_sorted.geometry[0])}, only point, linestring & polygon are allowed!')
        sys.exit()
    return final_array, dic_points, dic_obj
# 
#%%                

def connection_finder(df_s, df_d, dist_type, dist_max, df_a = [], selection_mode = 'Effective'):
     
    #ONLY OBJECTS WITHOUT NAN OR 0 VALUES!
    # dictionary that leads trough all levels
    dic_levels = {'d': type(df_d.geometry[0])}
    #unpack df_a if it is not empty
    if not not df_a:
        c = 1
        for value in df_a:
            vars()[f'df_{c}'] = value.copy()
            vars()[f'data_{c}'] = vars()[f'df_{c}'].columns.difference([vars()[f'df_{c}'].geometry.name])[0]
            vars()[f'df_{c}'] = max_dist_connection(vars()[f'df_{c}'] , vars()[f'data_{c}'], dist_type, dist_max)
            vars()[f'df_{c}_orig'] = vars()[f'df_{c}'].copy()
            dic_levels[f'{c}'] = type(vars()[f'df_{c}'].loc[vars()[f'df_{c}'].index[0], 'geometry'])
            c += 1
        del c
    dic_levels['s'] = type(df_s.geometry[0])
    # Calculate max. allowed distances for all objects
    data_s = df_s.columns.difference([df_s.geometry.name])[0]
    data_d = df_d.columns.difference([df_d.geometry.name])[0]
    df_s = max_dist_connection(df_s, data_s, dist_type, dist_max)
    df_d = max_dist_connection(df_d, data_d, dist_type, dist_max)
    # save all originals
    df_s_orig = df_s.copy()
    df_d_orig = df_d.copy()
    
    # check what is the maximum demand that could be covered
    total_demand  = df_d[data_d].sum() 
    for j in range(1, len(dic_levels)-1):
        total_demand += vars()[f'df_{j}'][vars()[f'data_{j}']].sum()
    
    tot_d = min(total_demand, df_s[data_s].sum())
    del total_demand

    counter = 0
    # level0: highest-first and smallest-first are collected on this level
    for finder in [True, False]:

        if finder:
            str_dummy = 'smallest'
        else:
            str_dummy = 'highest'
        # print(f'Searching connections {str_dummy}-first:')
        #reset all df needed
        df_s = df_s_orig.copy()
        df_d = df_d_orig.copy()
        for j in range(1, len(dic_levels)-1):
            vars()[f'df_{j}'] = vars()[f'df_{j}_orig'].copy()
        
        #start algorithm
        df_d.sort_values(by=data_d, ascending=finder, inplace=True)
        df_s.sort_values(by=data_s, ascending=finder, inplace=True)
        # get each df transfered into array
        for key in dic_levels:
                vars()[f'arr_{key}'], vars()[f'dic_points_{key}'], vars()[f'dic_obj_{key}'] = df_to_array(vars()[f'df_{key}'], vars()[f'data_{key}'], key, dic_levels)
        # create connector array
        lst_connectors = list()
        lst_df_con = list()
        lst_dic_obj = list()
        lst_dic_point = list()
        for j in range(len(dic_levels)-2):
            lst_connectors.append(vars()[f'arr_{j+1}'])
            lst_df_con.append(vars()[f'df_{j+1}'])
            lst_dic_obj.append(vars()[f'dic_obj_{j+1}'])
            lst_dic_point.append(vars()[f'dic_points_{j+1}'])
         
        lst_con = []
        
        # check if anything has changed
        cov_demand_old = 0
        demand_old = 0
        finisher = 0
        lst_d_s = ['d', 's']
        while finisher <= 1 :
            
            len_df = len(vars()[f'df_{lst_d_s[0]}'])
            checker = 0
            checker_old = 0
            if lst_d_s[0] == 's':
                supply_bool = True
                str_dummy = 'supply'
            else:
                supply_bool = False
                str_dummy = 'demand'
            # print(f'Starting with {str_dummy} matchmaking')
            # total list of all objects
            geo_objects = lst_df_con + [vars()[f'df_{lst_d_s[1]}']]

            for idx in tqdm(vars()[f'df_{lst_d_s[0]}'].index):
                #only reasign if there were some changes
                if checker == checker_old:
                    # create current total list of arrays    
                    lst_dic_obj_tot = lst_dic_obj + [vars()[f'dic_obj_{lst_d_s[1]}']]
                    lst_dic_point_tot = lst_dic_point + [vars()[f'dic_points_{lst_d_s[1]}']]
                    objects = lst_connectors + [vars()[f'arr_{lst_d_s[1]}']]
                    # Build KD-Trees for objects 
                    kdtrees = [cKDTree(obj[:, :2]) for obj in objects[:]]
                checker_old = checker
                
                # preparing values for recursive_dfs
                initial_object = vars()[f'df_{lst_d_s[0]}'].loc[idx, 'geometry']
                initial_points = vars()[f'arr_{lst_d_s[0]}'][vars()[f'dic_obj_{lst_d_s[0]}'][idx][0]:vars()[f'dic_obj_{lst_d_s[0]}'][idx][1],:]
                initial_value = vars()[f'df_{lst_d_s[0]}'].loc[idx, vars()[f'data_{lst_d_s[0]}']]
                if supply_bool:
                    tot_value = 0 
                else:
                    tot_value = initial_value
                initial_limit = vars()[f'df_{lst_d_s[0]}'].loc[idx, 'dist_max']
                #list with tuples([path], connection_value, connection_length)
                valid_paths = []
                # sending all the information to DFS Algorithm
                recursive_dfs(initial_object, initial_points, tot_value, 0, initial_limit, 0, [idx], objects, geo_objects, lst_dic_obj_tot, lst_dic_point_tot, kdtrees, valid_paths, initial_value, lst_con, supply_bool)    

                # print(f'done with {idx}')
                # if (len(valid_paths) >0):
                #     print(valid_paths)
                # plot all valid paths (only done for Paper!) %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                # # collect all geodata
                # df_valid_con = pd.DataFrame(columns = ['geometry', 'value', 'length', 'network'])
                # total_valid_connections = []
                # lst_con_lines = []
                # b = 0
                # for val in valid_paths:
                    
                #     df_dummy = pd.DataFrame(columns = ['geometry', 'value', 'length', 'network'])
                #     lst_sub_con = []
                #     lst_sub_con.append(vars()[f'df_{lst_d_s[0]}'].loc[val[0][0], 'geometry'])
                #     lst_index_con = []
                    
                #     for n in range(len(geo_objects)):
                #         lst_sub_con.append(geo_objects[n].loc[val[0][n+1], 'geometry'])
                #         lst_index_con.append(f'CON_{b}_{n}')
                    
                #     df_dummy['geometry'] = pd.Series(connect_geometries_by_shortest_distance(lst_sub_con))
                #     df_dummy['value'] = val[1]
                #     df_dummy['length'] = val[2]
                #     df_dummy['network'] = b
                #     df_dummy.index = lst_index_con   
                    
                #     df_valid_con = pd.concat([df_valid_con, df_dummy])
                #     b += 1
                    
                # gdf_connection = gpd.GeoDataFrame(data = df_valid_con, geometry = df_valid_con.loc[:, 'geometry'], crs= "EPSG:2056")
                # 0%%%%%%%%%%%%%%%%%%%%%%%%%%(only done for Paper!) %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
                
                
                if len(valid_paths) > 0:
                    df_valid_paths = pd.DataFrame([(entry[0], entry[1], entry[2]) for entry in valid_paths], columns=['objects', 'distance', 'value'])
                    df_valid_paths['dist/val'] = df_valid_paths['distance']/df_valid_paths['value']
                    if selection_mode == 'Effective' :
                        # version1 - take the connection with the highest value per distance
                        best_path = df_valid_paths[df_valid_paths['dist/val'] == df_valid_paths['dist/val'].min()].iloc[0,:].tolist()
                    if selection_mode == 'Closest' :
                        # version2 - take the connection with the lowest distance
                        best_path = df_valid_paths[df_valid_paths['distance'] == df_valid_paths['distance'].min()].iloc[0,:].tolist()
                    if selection_mode == 'Furthest' :
                        # version3 - take the connection with the highest distance
                        best_path = df_valid_paths[df_valid_paths['distance'] == df_valid_paths['distance'].max()].iloc[0,:].tolist()
                    if selection_mode == 'Ineffective' :
                        # version4 - take the connection with the lowest value per distance
                        best_path = df_valid_paths[df_valid_paths['dist/val'] == df_valid_paths['dist/val'].max()].iloc[0,:].tolist()
                    
                    # print(best_path)
                    lst_con.append(best_path)
                    # erase the matched objects or the transfered value (difference supply vs demand)
                    # drop in dataframe
                    vars()[f'df_{lst_d_s[0]}'].drop(idx, inplace = True)
                    if supply_bool:
                        # print(best_path)
                        # subtract as much as possible from demand object
                        df_d.loc[best_path[0][0], data_d]  -= best_path[2]
                        # if we subtracted too much, clean up and subtract from connectors if there are some
                        if df_d.loc[best_path[0][0], data_d] < 0:
                            excess_value = abs(df_d.loc[best_path[0][0], data_d])
                            #drop in df_d
                            df_d.drop(best_path[0][0], inplace= True)
                            # drop in array
                            vars()[f'arr_{lst_d_s[1]}'] = np.delete(vars()[f'arr_{lst_d_s[1]}'], np.arange(vars()[f'dic_obj_{lst_d_s[1]}'][best_path[0][0]][0], vars()[f'dic_obj_{lst_d_s[1]}'][best_path[0][0]][1]), axis = 0)
                            
                            for j in range(1,len(dic_levels)-1):                                
                                vars()[f'df_{j}'].loc[best_path[0][j], vars()[f'data_{j}']]  -= excess_value
                                
                                if vars()[f'df_{j}'].loc[best_path[0][j], vars()[f'data_{j}']] < 0:
                                    vars()[f'df_{j}'].loc[best_path[0][j], vars()[f'data_{j}']] = 0
                                    vars()[f'df_{j}'].loc[best_path[0][j], 'dist_max'] = 0
                                    excess_value = abs(vars()[f'df_{j}'].loc[best_path[0][j], vars()[f'data_{j}']])
                                else:
                                    # recalculate max distances
                                    vars()[f'df_{j}'] = max_dist_connection(vars()[f'df_{j}'] , vars()[f'data_{j}'], dist_type, dist_max)
                                    break
                        else:
                            # recalculate max distances
                            df_d = max_dist_connection(df_d , data_d, dist_type, dist_max)
  
                    else:
                        for j in range(1,len(dic_levels)-1):
                            # the value of the connection point with value is used up
                            vars()[f'df_{j}'].loc[best_path[0][j], vars()[f'data_{j}']] = 0
                            vars()[f'df_{j}'].loc[best_path[0][j], 'dist_max'] = 0
                        # reduce supply
                        df_s.loc[best_path[0][-1], data_s] -= best_path[2]
                        # if the supply is now zero - drop it and delete it from array
                        if df_s.loc[best_path[0][-1], data_s] == 0:
                            df_s.drop(best_path[0][-1], inplace = True)
                            # drop in array
                            vars()[f'arr_{lst_d_s[1]}'] = np.delete(vars()[f'arr_{lst_d_s[1]}'], np.arange(vars()[f'dic_obj_{lst_d_s[1]}'][best_path[0][-1]][0], vars()[f'dic_obj_{lst_d_s[1]}'][best_path[0][-1]][1]), axis = 0)
                    
                    # recalculate array and dictionary that was changed
                    # if there are no more demand or supply - out of while loop
                    if len(vars()[f'df_{lst_d_s[1]}']) == 0:
                        break
                    else:
                        vars()[f'df_{lst_d_s[1]}'] = max_dist_connection(vars()[f'df_{lst_d_s[1]}'], vars()[f'data_{lst_d_s[1]}'], dist_type, dist_max)
                        vars()[f'arr_{lst_d_s[1]}'], vars()[f'dic_points_{lst_d_s[1]}'], vars()[f'dic_obj_{lst_d_s[1]}'] = df_to_array(vars()[f'df_{lst_d_s[1]}'], vars()[f'data_{lst_d_s[1]}'], lst_d_s[1], dic_levels)

                # if there was no match, the checker will be increased
                else:
                    checker += 1 
            #print how much of the demand is currently matched
            cov_demand = round(100*((sum(entry[2] for entry in lst_con.copy()))/tot_d),6)
            # demand_now = (sum(entry[2] for entry in lst_con.copy()))
            # demand_change = demand_now - demand_old
            # demand_old = demand_now
            # dec_detail = 100000
            # cov_demand_dif = cov_demand*dec_detail - cov_demand_old*dec_detail
            # cov_demand_old = cov_demand
            print(f'\n{cov_demand}% of total demand matched')
            # print(f'demand change: {demand_change}')
            # check if there was no match found at all
            # print(f'length df: {len_df}')
            # print(f'checker: {checker}')
            if (checker == len_df):
                #increase finisher, if this happens twice in row, no more connections can be found
                print('I found nothing, but maybe with a diffrent approach - hold on')
                finisher += 1
            else:
                # if (cov_demand_dif)<1:
                #     #increase finisher, if this happens twice in row, no more connections can be found
                #     print('I found too little, but maybe with a diffrent approach - hold on')
                #     finisher += 1
                # else:
                #     # if there where some matches found, finisher goes to zero and df is newly sorted
                finisher = 0
                # if there are no more demand or supply - out of while loop
                if len(vars()[f'df_{lst_d_s[0]}']) == 0:
                    print('\nThat is it, Im done here')
                    finisher = 2
                else:
                    #update array and dictionary of lst_d_s[0]
                    vars()[f'arr_{lst_d_s[0]}'], vars()[f'dic_points_{lst_d_s[0]}'], vars()[f'dic_obj_{lst_d_s[0]}'] = df_to_array(vars()[f'df_{lst_d_s[0]}'], vars()[f'data_{lst_d_s[0]}'], lst_d_s[0], dic_levels)
                    vars()[f'df_{lst_d_s[1]}'].sort_values(by=vars()[f'data_{lst_d_s[1]}'], ascending=finder, inplace=True)
                    vars()[f'arr_{lst_d_s[1]}'], vars()[f'dic_points_{lst_d_s[1]}'], vars()[f'dic_obj_{lst_d_s[1]}'] = df_to_array(vars()[f'df_{lst_d_s[1]}'], vars()[f'data_{lst_d_s[1]}'], lst_d_s[1], dic_levels)
            
            # change demand and supply
            lst_d_s.reverse()
            
        # Extracting the needed values
        vars()[f'lst_con_{counter}'] = lst_con.copy()
        vars()[f'total_sum_{counter}'] = sum(entry[2] for entry in vars()[f'lst_con_{counter}'])
        # if the max potential was found, no second run is needed
        if vars()['total_sum_0'] < tot_d:
            # print('That could be better, last try...')
            counter += 1
        else:
            # print('WOW- first try I found the max potential\nSaving that!')
            vars()['total_sum_1'] = 0
            break
        # # paper code ---------------------------------------------------------
        # vars()['total_sum_1'] = 0
        # #----------------------------------------------------------------------
    #check which version cover the bigger potential
    if vars()['total_sum_0'] >= vars()['total_sum_1']:
        final_counter = 0 
        # print('\nsmallest first has better matches')
    else:
        final_counter = 1 
        # print('\nhighest first has better matches')

    
    # saving the best version in geodataframe
    # print('---- Saving your brand new connection GeoDataFrame ----')
    column_df_final_con = ['objs', 'value', 'distance', 'distance/value', 'geometry']
    df_final_con = pd.DataFrame(columns = column_df_final_con)

    b = 0
    for val in tqdm(vars()[f'lst_con_{final_counter}']):
        
        df_dummy = pd.DataFrame(columns = column_df_final_con)
        lst_objs = val[0]
        #collect each original geometry object
        lst_sub_con = []
        for key in dic_levels:
            idx_match = vars()[f'df_{key}_orig'].index[vars()[f'df_{key}_orig'].index.isin(lst_objs)].tolist()
            lst_sub_con.append(vars()[f'df_{key}_orig'].loc[idx_match[0],'geometry'])
        
        df_dummy['objs'] = [val[0]]
        # get the connection line
        df_dummy['geometry'] = shapely.MultiLineString(connect_geometries_by_shortest_distance(lst_sub_con))
        df_dummy['distance'] = val[1]
        df_dummy['value'] = val[2]
        df_dummy['distance/value'] = val[3]
        df_dummy.index =  [f'CON_{b}']
        df_final_con = pd.concat([df_final_con, df_dummy])
        b += 1
        
    gdf_connection = gpd.GeoDataFrame(data = df_final_con, geometry = df_final_con.loc[:, 'geometry'], crs= "EPSG:2056")
    return gdf_connection

#%%
def connect_geometries_by_shortest_distance(geometries):
    """
    Connects a list of Shapely geometries (points, lines, polygons) by the shortest distance 
    in their given order and returns a new list with the original geometries and the connecting lines.
    
    Parameters:
        geometries (list): List of shapely.geometry objects (Point, LineString, Polygon).
    
    Returns:
        list: connection LineStrings.
    """
    if not geometries or len(geometries) < 2:
        return geometries  # No connections needed if there's only one or zero elements
    
    connection_lines = list()  # Start with the original geometries

    # Compute shortest connection lines
    for i in range(len(geometries) - 1):
        geom1 = geometries[i]
        geom2 = geometries[i + 1]
        # Get nearest points between the two geometries
        point1, point2 = shapely.ops.nearest_points(geom1, geom2)
        connection = shapely.LineString([point1.coords[0][:2], point2.coords[0][:2]])
        connection_lines.append(connection)

    return connection_lines
#%%
def group_by_middle_overlap(df, list_col):
    """
    Groups rows in a DataFrame based on overlapping elements in the middle
    of lists in the specified column. Other columns are aggregated into lists.

    Parameters:
    - df: input DataFrame
    - list_col: name of the column that contains lists of strings

    Returns:
    - aggregated DataFrame
    """

     # Step 1: Build map from center elements to row indices
    middle_map = defaultdict(set)
    for idx, lst in df[list_col].items():
        if len(lst) >= 3:
            for mid in lst[1:-1]:
                middle_map[mid].add(idx)

    # Step 2: Group connected rows
    visited = set()
    groups = []
    for indices in middle_map.values():
        new_group = set()
        for idx in indices:
            if idx not in visited:
                new_group |= indices
        if new_group:
            groups.append(list(new_group))
            visited |= new_group

    # Step 3: Include ungrouped rows
    all_grouped = set(idx for group in groups for idx in group)
    for idx in df.index:
        if idx not in all_grouped:
            groups.append([idx])

    # Step 4: Process each group
    results = []
    for group in groups:
        rows = df.loc[group]

        # Nest the list elements by position (with uniqueness)
        max_len = max(len(lst) for lst in rows[list_col])
        nested = [set() for _ in range(max_len)]

        for lst in rows[list_col]:
            for i, val in enumerate(lst):
                nested[i].add(val)

        # Convert sets to sorted lists (for consistent output)
        nested = [sorted(list(s)) for s in nested]

        # Aggregate all other columns into lists
        agg_data = {list_col: nested}
        for col in df.columns:
            if col != list_col:
                agg_data[col] = list(rows[col])

        results.append(agg_data)

    return pd.DataFrame(results)   

#%%
class UnionFind:
    def __init__(self):
        self.parent = dict()

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        self.parent[self.find(x)] = self.find(y)


def group_by_masked_overlap(df, list_col, group_mask):
    """
    Groups rows in a DataFrame based on overlapping elements defined by a mask,
    using union-find to merge connected components.
    """
    uf = UnionFind()
    element_to_indices = defaultdict(list)

    for idx, lst in df[list_col].items():
        for i, val in enumerate(lst):
            if i < len(group_mask) and group_mask[i]:
                element_to_indices[val].append(idx)

    for indices in element_to_indices.values():
        for i in range(1, len(indices)):
            uf.union(indices[0], indices[i])

    # Group rows by connected component root
    groups = defaultdict(list)
    for idx in df.index:
        root = uf.find(idx)
        groups[root].append(idx)

    # Build result
    results = []
    for group_indices in groups.values():
        rows = df.loc[group_indices]

        max_len = max(len(lst) for lst in rows[list_col])
        nested = [set() for _ in range(max_len)]
        for lst in rows[list_col]:
            for i, val in enumerate(lst):
                nested[i].add(val)
        nested = [sorted(list(s)) for s in nested]

        agg_data = {list_col: nested}
        for col in df.columns:
            if col != list_col:
                agg_data[col] = list(rows[col])

        results.append(agg_data)

    return pd.DataFrame(results)

#%%
def covering_circle(polygon):
    """
    Compute a covering circle centered at the polygon centroid.
    Works for Polygon and MultiPolygon.
    """
    center = polygon.centroid

    # Get all exterior coordinates
    if polygon.geom_type == 'Polygon':
        exterior_coords = np.array(polygon.exterior.coords)
    elif polygon.geom_type == 'MultiPolygon':
        exterior_coords = np.vstack([
            np.array(p.exterior.coords) for p in polygon.geoms
        ])
    else:
        raise TypeError("Input geometry must be Polygon or MultiPolygon.")

    # Compute distances from centroid to all exterior points
    distances = np.sqrt(
        (exterior_coords[:, 0] - center.x) ** 2 +
        (exterior_coords[:, 1] - center.y) ** 2
    )

    max_distance = distances.max()
    circle = center.buffer(max_distance)

    circle_area = circle.area
    polygon_area = polygon.area
    area_ratio = circle_area / polygon_area

    return {
        "circle": circle,
        "radius": max_distance,
        "circle_area": circle_area,
        "polygon_area": polygon_area,
        "area_ratio": area_ratio,
        "center": center
    }


#%%

def explode_geometrycollections(gdf):
    """
    Explodes GeometryCollections and keeps only specified geometry types.
    Parameters:
        gdf (GeoDataFrame): The input GeoDataFrame.
    Returns:
        GeoDataFrame: A new GeoDataFrame with exploded geometries filtered by type.
    """
    keep_types=('Polygon', 'MultiPolygon')
    exploded_rows = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        if geom.geom_type == 'GeometryCollection':
            for part in geom.geoms:
                if part.geom_type in keep_types:
                    new_row = row.copy()
                    new_row.geometry = part
                    exploded_rows.append(new_row)
        elif geom.geom_type in keep_types:
            exploded_rows.append(row)
        # ignore other geometry types like Point, LineString, etc.

    return gpd.GeoDataFrame(exploded_rows, crs=gdf.crs).reset_index(drop=True)






















