'''Functions to manipulate the "Healthcare Associated Infections - Hospital.csv" file, and those like it.'''

import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from sklearn import linear_model
from sklearn.cross_validation import train_test_split
from sklearn.metrics import roc_curve, auc
# Local file, intro-ds-hai/src/ directly must be in the path.
import data_utils


def _convertOldHAIDataframe(old_df, year_str):
    '''Replaces the 'Measure' column with the 'Measure ID' column. year_str can be either '2012' or '2013' for now.'''
    # TODO both maps have other HAI_1 measures, like upper and lower bounds
    # TODO 2013_MEASURE_MAP can be extended to have entries for HAI 1 through HAI 4.
    # Rename the scores and compare rows to correspond to 2014 format
    MEASURE_MAP_2013 = {'Central-Line-Associated Blood Stream Infections (CLABSI)': 'HAI_1_SIR',
                        'CLABSI Compared to National': 'HAI_1_compare'}
    MEASURE_MAP_2012 = {'Central Line Associated Blood Stream Infections (CLABSI)': 'HAI_1_SIR',
                        'CLABSI Upper Confidence Limit': 'HAI_1_compare'} # TODO this looks wrong...did jackie work around this?

    def measure_map_func(measure_name):
        if year_str == '2013' and measure_name in MEASURE_MAP_2013:
            return MEASURE_MAP_2013[measure_name] 
        elif year_str == '2012' and measure_name in MEASURE_MAP_2012:
            return MEASURE_MAP_2012[measure_name]
        return None

    old_df['Measure ID'] = old_df['Measure'].map(measure_map_func)
    old_df = old_df.drop('Measure', 1)
    return old_df
    
def _categoricalToIndicator(df, compare):
    """Replaces the string values in a compare column to numerical benchmarks
        -1: Worse than national average
        0: No different than national average
        1: Better than national average
        Nan: Not available"""   
    benchmarks = pd.unique(df[compare])
    benchmarks.sort() # alphabetically sort the comparator labels
    benchmarks ={benchmarks[0]:1, benchmarks[1]:0, benchmarks[2]:np.nan, benchmarks[3]:-1}
    return df.replace({compare:benchmarks})

def _convertToNumeric(df, col_label, missing_marker):
    """Converts missing values denoted by string missing_marker to Nan 
    	and casts column data as float."""
    for marker in missing_marker:
    	df[col_label][df[col_label]==marker] = np.nan
    df[col_label] = df[col_label].astype(float)
    return df

# TODO DEPRECATED! doesn't set provider ID as the index.
def parseHAIFile(filename, year_str):
    '''year_str can be either '2012', '2013', or '2014' for now.'''
    COLUMNS_2014 = ['City', 'State', 'Measure ID', 'Score']
    COLUMNS_2013 = ['City', 'State', 'Measure', 'Score']
    COLUMNS_2012 = ['City', 'State', 'Measure', 'Score']
    useful_columns_map = {'2014': COLUMNS_2014, '2013': COLUMNS_2013, '2012': COLUMNS_2012}
    
    data = data_utils.parseFileWithIndex(filename, useful_columns_map[year_str])
    if year_str == '2012' or year_str == '2013':
        data = _convertOldHAIDataframe(data, year_str)
    assert 'Measure ID' in data.columns
    assert 'Measure' not in data.columns
    # Throws out all rows that don't have the measure ID 'HAI_1_SIR'.
    data = data[data['Measure ID'] == 'HAI_1_SIR']
    data = _convertToNumeric(data, 'Score', ['Not Available', '-'])
    data = data.drop('Measure ID', 1)
    # TODO Do we want to remove rows with missing target?
    return data

def parseHAIbyBinLabel(filename, year_str):
    '''year_str can be either '2012', '2013', or '2014' for now.
    Analog of parseHAIFile, but instead of using Score as target, gives numerical indicator for
    Compared to National. -1 means worse than average, 0 no different, 1 better than average.
    Actual SIR value, confidence intervals, etc. will not be included in returned df
    
   parseHAIbyBinLabel keeps the label, and drops the actual score
   parseHAIFile keeps only the score without the label
   If we want to keep both, we can call both functions and then merge the resulting datasets, 
   (see parseHAIboth) '''

    COLUMNS_2014 = ['City', 'State', 'Measure ID', 'Compared to National']
    COLUMNS_2013 = ['City', 'State', 'Measure', 'Score']
    COLUMNS_2012 = ['City', 'State', 'Measure', 'Score']
    useful_columns_map = {'2014': COLUMNS_2014, '2013': COLUMNS_2013, '2012': COLUMNS_2012}
    
    data = data_utils.parseFileWithIndex(filename, useful_columns_map[year_str])
    if year_str == '2013':
        data = _convertOldHAIDataframe(data, year_str)
        data['Compared to National'] = data['Score'] #rename the Score column
        data = data.drop('Score', 1)
    elif year_str == '2012':
        # 2012 doesn't come with its own labels. Instead, we use the CIs to construct the labels.
    	data = _binByCI(data, 'CLABSI Lower Confidence Limit', 'CLABSI Upper Confidence Limit', 'Score')
    	data = _convertOldHAIDataframe(data, year_str)
    	data = data.drop('Score', 1)
    elif year_str == '2014':
    	data = data.replace({'Measure ID': {'HAI_1_SIR':'HAI_1_compare'}})
    assert 'Measure ID' in data.columns
    assert 'Measure' not in data.columns
    assert 'Compared to National' in data.columns
    assert 'Score' not in data.columns
    # Throws out all rows that don't have the measure ID 'HAI_1_compare'.
    data = data[data['Measure ID'] == 'HAI_1_compare']
    if year_str !='2012':
    	data = _categoricalToIndicator(data, 'Compared to National')
    # Now that we've removed all the rows unrelated to HAI_1_SIR, drop the measure ID.
    data = data.drop('Measure ID', 1)
    # TODO Do we want to remove rows with missing target?
    return data

def parseHAIboth(filename, year_str):
	data1 = parseHAIFile(filename, year_str)
	data2 = parseHAIbyBinLabel(filename, year_str)
	data2['Score'] = data1['Score']
	assert 'Compared to National' in data2.columns
	assert 'Score' in data2.columns
	return data2
    
def _binByCI(data, lowerLabel, upperLabel, valueLabel):
	"""For a dataframe with no bin labels, takes the limits of confidence interval
	and converts them into a numerical indicator, -1, 1, or 0. If the interval
	contains 1, we will call this no different (i.e. 0)"""
	hospitals = np.unique(data.index)
	data = _convertToNumeric(data, valueLabel, ['Not Available', '-'])
	cp = 'Compared to National'
	data[cp] = np.nan
	for h in hospitals:
		hospital = data.loc[data.index == h]
		lower = hospital.loc[hospital['Measure'] == lowerLabel, valueLabel]
		upper = hospital.loc[hospital['Measure'] == upperLabel, valueLabel]
		lower = lower.get_values()[0]
		upper = upper.get_values()[0]
		if upper < 1:
			data.loc[hospital.index, cp] = 1
		elif lower > 1:
			data.loc[hospital.index, cp] = -1
		elif (lower < 1) & (upper > 1):
			data.loc[hospital.index, cp] = 0
	return data
	
def filterByMeasureID(data, measure_id):
    # TODO only used by notebook
    data = data.loc[data['Measure ID'] == measure_id]
    # Drop the measure id column, since it's the same for all rows now.
    data = data.drop('Measure ID', 1)
    return data

def removeRowsWithMissingTarget(data, target_column):
    # TODO only used by notebook
    MISSING_VALUE = 'Not Available'
    data = data[data[target_column] != MISSING_VALUE]
    return data
