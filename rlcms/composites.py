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
                    **kwargs):
    
    """Processes multi-band composite of your chosen dataset(s) within an AOI footprint polygon

        Uses `settings` .txt file at path provided or a dictionary provided to the function

    args:
        dataset (str|list[str]): one or multiple of: 'Landsat5','Landsat7','Landsat8','Sentinel1Asc','Sentinel1Desc','Sentinel2','Modis','Viirs')
        aoi (ee.Geometry): aoi geometry
        start_year (int): start year
        end_year (int): end year
    
    how to best display this in doc string...
    kwargs:
        'indices': list[str],
        'addTasselCap':bool,
        'addJRCWater': bool,
        'addTopography':bool,
        'percentileOptions': list[int],
        'addHarmonics':bool,
        'harmonicsOptions': 
                    {'red':
                    {'start':int[1:365],'end':int[1:365]}}
    
    returns:
        ee.Image: raster stack of S2 bands and covariates within AOI polygon
    """
    
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
    print('ds',ds)
    
    ds = ds.apply_func(returnCovariatesFromOptions,**kwargs)
    print('addedIndices bandnames',ds.collection.first().bandNames().getInfo())
    # print('addedIndices.n_images',addedIndices.n_images)
    
    # compute composite based on user-defined mode and method 
    if 'composite_mode' in kwargs.keys():
        if kwargs['composite_mode'] == 'annual':
            period_unit = 'year'
            period = 1 # if wanted to composite all of it..ds.dates then strip each element to the year, get distinct() and count unique years 
        elif kwargs['composite_mode'] == 'seasonal':
            if 'months' not in kwargs['months']:
                raise ValueError(f"'composite_mode': 'seasonal' cannot run, 'months' not defined.")
            else:
                period_unit = 'month'
                period = len(kwargs['months']) # figure out how to construct a seasonal composite from aggregate_time()
        
        else:
            raise ValueError(f"{kwargs['composite_mode']} is not a supported 'composite_mode'. Supported: 'annual', 'seasonal'")
        
        # is it even worth allowing the user to specify their percentiles?
        if 'percentileOptions' in kwargs.keys() and kwargs['composite_method'] != 'percentile':
            percentile_options = kwargs['percentileOptions'] # returns a list of percentile integers
            reducer = ee.Reducer.percentile(percentile_options)
            
    else:
        # default is yearly composite of whatever ds's time range is 
        # how to only have to call ds.aggregate_time() once outside of if-elses 
        composite = (ds.aggregate_time(reducer='mean',
                                      rename=True,
                                      period_unit='year',
                                      dates=[start_date])
                                      .collection.first())
    
    print('composite.collection.first().bandNames()',composite.bandNames().getInfo())
    
    # compute harmonics if desired (set in settings settings) 
    # TODO: consider using hf.timeseries module,
        #  but doesn't look like the methods are exact same as in rlcms.harmonics 
        # ht.timeseries functions don't return phase and amplitude..
    if 'addHarmonics' in kwargs:
        if kwargs['addHarmonics']:
            harmonics_features = doHarmonicsFromOptions(ds.collection,**kwargs) # returns an ee.Image, not a hf.Dataset
            composite = composite.addBands(harmonics_features)
    
    # add JRC variables if desired (set in settings settings) 
    if 'addJRCWater' in kwargs.keys():
        if kwargs['addJRCWater']:
            composite = idx.addJRC(composite).unmask(0)
    
    # add topography variables if desired (set in settings settings)     
    if 'addTopography' in kwargs.keys():
        if kwargs['addTopography']:
            composite = idx.addTopography(composite).unmask(0)
    
    print('final composite.bandNames()\n',composite.bandNames().getInfo())
    return ee.Image(composite)