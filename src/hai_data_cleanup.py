'''Functions to manipulate the "Healthcare Associated Infections - Hospital.csv" file, and those like it.'''

import os

import matplotlib.pyplot as plt
import pandas as pd
from sklearn import linear_model
from sklearn.cross_validation import train_test_split
from sklearn.metrics import roc_curve, auc

# Local file, intro-ds-hai/src/ directly must be in the path.
import data_utils


def convertOldHAIDataframe(old_df, year_str):
    '''Replaces the 'Measure' column with the 'Measure ID' column. year_str can be either '2012' or '2013' for now.'''
    # TODO both maps have other HAI_1 measures, like upper and lower bounds
    # TODO 2013_MEASURE_MAP can be extended to have entries for HAI 1 through HAI 4.
    MEASURE_MAP_2013 = {'Central-Line-Associated Blood Stream Infections (CLABSI)': 'HAI_1_SIR'}
    MEASURE_MAP_2012 = {'Central Line Associated Blood Stream Infections (CLABSI)': 'HAI_1_SIR'}

    def measure_map_func(measure_name):
        if year_str == '2013' and measure_name in MEASURE_MAP_2013:
            return MEASURE_MAP_2013[measure_name] 
        elif year_str == '2012' and measure_name in MEASURE_MAP_2012:
            return MEASURE_MAP_2012[measure_name]
        return None

    old_df['Measure ID'] = old_df['Measure'].map(measure_map_func)
    old_df = old_df.drop('Measure', 1)
    return old_df

def parseHAIFile(filename, year_str):
    '''year_str can be either '2012', '2013', or '2014' for now.'''
    COLUMNS_2014 = ['Provider ID', 'City', 'State', 'ZIP Code', 'County Name', 'Measure ID', 'Score']
    COLUMNS_2013 = ['Provider ID', 'City', 'State', 'ZIP Code', 'County Name', 'Measure', 'Score']
    COLUMNS_2012 = ['Provider ID', 'City', 'State', 'ZIP Code', 'County Name', 'Measure', 'Score']
    useful_columns_map = {'2014': COLUMNS_2014, '2013': COLUMNS_2013, '2012': COLUMNS_2012}

    data = data_utils.parseFile(filename, useful_columns_map[year_str])
    if year_str == '2012' or year_str == '2013':
        data = convertOldHAIDataframe(data, year_str)
    assert 'Measure ID' in data.columns
    assert 'Measure' not in data.columns
    # Make Provider ID an integer so we can use it as a merge key. 
    # Other tables have padding zeros, so converting to int standardizes them.
    data['Provider ID'] = data['Provider ID'].astype(int)
    return data

def filterByMeasureID(data, measure_id):
    data = data.loc[data['Measure ID'] == measure_id]
    # Drop the measure id column, since it's the same for all rows now.
    data = data.drop('Measure ID', 1)
    return data

def factorizeFeatures(train_data):
    '''Makes all string columns into ints, using category numbers if the column isn't convertable into an int directly.'''
    X = pd.DataFrame()
    for column in list(train_data.columns):
        try:
            X[column] = train_data[column].astype(int)
        except ValueError:
            print 'cant interize column, assuming categorical', column
            X[column] = pd.Categorical.from_array(train_data[column]).codes
    return X

def removeRowsWithMissingTarget(data, target_column):
    MISSING_VALUE = 'Not Available'
    data = data[data[target_column] != MISSING_VALUE]
    return data
