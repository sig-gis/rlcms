import ee
import json
import hydrafloods as hf
from rlcms.harmonics import doHarmonicsFromOptions
from rlcms.covariates import indices
from rlcms.covariates import returnCovariatesFromOptions
from rlcms.utils import parse_settings
ee.Initialize()

idx = indices()

def composite_aoi(dataset,
                    aoi:ee.FeatureCollection,
                    start_date,
                    end_date,
                    settings):
    
    """Processes multi-band composite of your chosen dataset(s) within an AOI footprint polygon

        Uses `settings` .txt file at path provided or a dictionary provided to the function

    args:
        dataset (str|list[str]): one or multiple of: 'Landsat5','Landsat7','Landsat8','Sentinel1Asc','Sentinel1Desc','Sentinel2','Modis','Viirs')
        aoi (ee.Geometry): aoi geometry
        start_year (int): start year
        end_year (int): end year
        model_inputs (dict|str):
            
            {'indices': list[str],
            'addTasselCap':bool,
            'addJRCWater': bool,
            'addTopography':bool,
            'percentileOptions': list[int],
            'addHarmonics':bool,
            'harmonicsOptions': 
                     {'band(str)':
                       {'start':1,  in Julian Days (Day of Year)
                        'end':365}, 
                      
                       'blue':
                       {'start':1,  in Julian Days (Day of Year)
                       'end':365}, 
                     }}
            }
    returns:
        ee.Image: raster stack of S2 bands and covariates within AOI polygon
    """
    
    # parse settings dict from JSON-like file path or python dict
    settings_dict = parse_settings(settings)
    # print(settings_dict)
    
    # all hydrafloods.Dataset sub-classes
    ds_dict = {'Landsat5':hf.Landsat5(aoi,start_date,end_date),
               'Landsat7':hf.Landsat7(aoi,start_date,end_date),
               'Landsat8':hf.Landsat8(aoi,start_date,end_date),
               'Sentinel1':hf.Sentinel1(aoi,start_date,end_date),
               'Sentinel1Asc':hf.Sentinel1Asc(aoi,start_date,end_date),
               'Sentinel1Desc':hf.Sentinel1Desc(aoi,start_date,end_date),
               'Sentinel2':hf.Sentinel2(aoi,start_date,end_date),
               'MODIS':hf.Modis(aoi,start_date,end_date),
               'VIIRS':hf.Viirs(aoi,start_date,end_date)}
    
    if isinstance(dataset,list):
        # will need to iteratively construct each hf.Dataset and merge them together
        raise RuntimeError("multiple datasets not yet supported")  
    else:
        ds = ds_dict[dataset]
    # print('ds',ds)
    
    ds = ds.apply_func(returnCovariatesFromOptions,**settings_dict)
    # print('addedIndices bandnames',addedIndices.collection.first().bandNames().getInfo())
    # print('addedIndices.n_images',addedIndices.n_images)
    
    # compute composite based on user-defined mode and method 
    if 'composite_mode' in settings_dict.keys():
        if settings_dict['composite_mode'] == 'annual':
            period_unit = 'year'
            period = 1 # if wanted to composite all of it..ds.dates then strip each element to the year, get distinct() and count unique years 
        elif settings_dict['composite_mode'] == 'seasonal':
            if 'months' not in settings_dict['months']:
                raise ValueError(f"'composite_mode': 'seasonal' cannot run, 'months' not defined.")
            else:
                period_unit = 'month'
                period = len(settings_dict['months']) # figure out how to construct a seasonal composite from aggregate_time()
        
        else:
            raise ValueError(f"{settings_dict['composite_mode']} is not a supported 'composite_mode'. Supported: 'annual', 'seasonal'")
        
        # is it even worth allowing the user to specify their percentiles?
        if 'percentileOptions' in settings_dict.keys() and settings_dict['composite_method'] != 'percentile':
            percentile_options = settings_dict['percentileOptions'] # returns a list of percentile integers
            reducer = ee.Reducer.percentile(percentile_options)
            
    else:
        # default is yearly composite of whatever ds's time range is 
        composite = (ds.aggregate_time(reducer=ee.Reducer.mean,
                                      rename=True,
                                      period_unit='year',
                                      dates=[start_date])
                                      .collection.first())
    composite = (ds.aggregate_time(reducer=ee.Reducer.percentile(percentile_options),
                                rename=False,
                                period_unit='year', # annual composite, period default =1 
                                dates=[start_date])
                                .collection.first()) # extract hf.Dataset to ee.Image or ee.ImageCollection    
        
    # print('composite.n_images',percentiles.n_images)
    # print('composite.collection.first().bandNames()',composite.collection.first().bandNames().getInfo())
    
    # compute harmonics if desired (set in settings settings) 
    # TODO: consider using hf.timeseries module,
        #  but doesn't look like the methods are exact same as in rlcms.harmonics 
    if 'addHarmonics' in settings_dict:
        if settings_dict['addHarmonics']:
            harmonics_features = doHarmonicsFromOptions(ds.collection,settings_dict) # returns an ee.Image, not a hf.Dataset
            ds = composite.addBands(harmonics_features)
            # print('harmonics_features.collection.first().bandNames()',harmonics_features.bandNames().getInfo())

    # how to add hf.Datasets together that are images 
    # stack = ee.Image.cat([ee.Image(ds.collection.first()),
    #                       harmonics_features])
    # print('stack.bandNames()',stack.bandNames().getInfo())
    
    # add JRC variables if desired (set in settings settings) 
    if 'addJRCWater' in settings_dict.keys():
        if settings_dict['addJRCWater']:
            ds = idx.addJRC(ds).unmask(0)
    
    # add topography variables if desired (set in settings settings)     
    if 'addTopography' in settings_dict.keys():
        if settings_dict['addTopography']:
            ds = idx.addTopography(ds).unmask(0)
    
    print('final ds.bandNames()\n',ds.bandNames().getInfo())
    return ee.Image(ds)