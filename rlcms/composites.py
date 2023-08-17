import ee
import hydrafloods as hf
from rlcms.harmonics import doHarmonicsFromOptions
from rlcms.covariates import indices
from rlcms.covariates import returnCovariatesFromOptions
ee.Initialize()

idx = indices()

def get_timing(collection:hf.Dataset,**kwargs):
    """utility function for hf.Dataset.aggregate_time(). Formats `period`, `period_unit`, and `dates` args
        to create certain types of composites (defined by `composite_mode`)
    args:
        collection (hf.Dataset): Hydrafloods Dataset
    kwargs:
        composite_mode (str): one of 'annual' or 'seasonal', Default = 'annual'
        season (list[str|int]): consecutive list of months (e.g. ['01','02','03']) comprising the season.
            A required arg if composite_mode == 'seasonal'
    Returns:
        tuple(period(int),period_unit(str),dates(list[str]))
            
    """
    if 'composite_mode' not in kwargs:
        composite_mode = 'annual'
    else:
        composite_mode = kwargs['composite_mode']
    
    # get unique yyyy strings
    years = list(set([d.split(' ')[0].split('-')[0] for d in collection.dates])) 
    years.sort()
    
    if composite_mode == 'seasonal':
        if 'season' not in kwargs:
            raise ValueError("season arg required if composite_mode == 'seasonal'")
        else:
            season = kwargs['season'] # must be consecutive 
            period = len(season)
            period_unit = 'month'
            dates = [f"{y}-{str(season[0])}-01" for y in years]
    elif composite_mode == 'annual':
        period = 1
        period_unit = 'year'
        dates = [y+'-01-01' for y in years]
    
    else:
        raise ValueError(f"{composite_mode} not a valid 'composite_mode'. Choose one of 'annual' or 'seasonal'")
    
    return period,period_unit,dates

def composite(dataset,
                    aoi:ee.FeatureCollection,
                    start_date,
                    end_date,
                    **kwargs):
    
    """Processes multi-band composite of your chosen dataset(s) within an AOI footprint polygon

    args:
        dataset (str|list[str]): one of: 'Landsat5','Landsat7','Landsat8','Sentinel1Asc','Sentinel1Desc','Sentinel2','Modis','Viirs')
        aoi (ee.FeatureCollection): area of interest
        start_date (str): start date
        end_date (str): end date
    
    kwargs:
        indices:list[str]
        composite_mode:str One of ['seasonal','annual'] Default = 'annual' 
        season:list[str|int]
        reducer:str|ee.Reducer
        addTopography:bool
        addJRC:bool
        addHarmonics:bool
        addTasselCap:bool
        harmonicsOptions:dict in this format: {'nir':{'start':int[1:365],'end':[1:365]}}
    
    returns:
        ee.Image: composited dataset within AOI polygon
    """
    
    if isinstance(aoi,ee.FeatureCollection):
        region = aoi.geometry()
    elif isinstance(aoi,ee.Geometry):
        region = aoi
    else:
        raise TypeError(f"{aoi} must be of type ee.FeatureCollection or ee.Geometry, got {type(aoi)}")
    
    # all hydrafloods.Dataset sub-classes
    ds_dict = {'Landsat5':hf.Landsat5(region,start_date,end_date),
               'Landsat7':hf.Landsat7(region,start_date,end_date),
               'Landsat8':hf.Landsat8(region,start_date,end_date),
               'Sentinel1':hf.Sentinel1(region,start_date,end_date),
               'Sentinel1Asc':hf.Sentinel1Asc(region,start_date,end_date),
               'Sentinel1Desc':hf.Sentinel1Desc(region,start_date,end_date),
               'Sentinel2':hf.Sentinel2(region,start_date,end_date),
               'MODIS':hf.Modis(region,start_date,end_date),
               'VIIRS':hf.Viirs(region,start_date,end_date)}
    
    if isinstance(dataset,list):
        # will need to iteratively construct each hf.Dataset and merge them together
        raise RuntimeError("multiple datasets not yet supported")  
    else:
        ds = ds_dict[dataset]
    # print('ds',ds)
    
    # mask imgs to geometries in multi_poly mode
    if 'multi_poly' in kwargs:
        if kwargs['multi_poly'] == True:
            def update_mask(img):
                ref_poly_img = ee.Image(1).paint(aoi).Not().selfMask() # aoi can be ee.Geometry or ee.FeatureCollection for this
                return ee.Image(img).updateMask(ref_poly_img)
            ds = ds.apply_func(update_mask)
    
    ds = ds.apply_func(returnCovariatesFromOptions,**kwargs)
    # print('addedIndices bandnames',ds.collection.first().bandNames().getInfo())
    # print('addedIndices.n_images',addedIndices.n_images)
    
    # set reducer passed to aggregate_time(), default mean
    if 'reducer' in kwargs:
        reducer=kwargs['reducer']
    else:
        reducer = 'mean'
    
    period,period_unit,dates = get_timing(ds,**kwargs)
    
    # print('reducer',reducer)
    # print('period',period)
    # print('period_unit',period_unit)
    # print('dates',dates)
    # print('ds.n_images before aggregate_time()',ds.n_images)
    
    agg_time_result = (ds.aggregate_time(reducer=reducer,
                                    rename=False,
                                    period_unit=period_unit,
                                    period = period,
                                    dates=dates)
                                    )
    # print('n_images of aggregate_time() result',agg_time_result.n_images)
    # print('dates of aggregate_time() result',agg_time_result.dates)
    # print('band names of agg_time_result.first()',agg_time_result.collection.first().bandNames().getInfo())
    
    composite = ee.ImageCollection(agg_time_result.collection).toBands()
    # rename bands depending on number of resulting images
    if agg_time_result.n_images > 1:
        bnames = composite.bandNames().map(lambda b: ee.String('t').cat(b))
    else:
        bnames = composite.bandNames().map(lambda b: ee.String(b).slice(2))
    
    composite = composite.rename(bnames)
        
    # compute harmonics if desired (set in settings settings) 
    # TODO: consider using hf.timeseries module,
        #  but doesn't look like the methods are exact same as in rlcms.harmonics 
        # ht.timeseries functions don't return phase and amplitude..
    if 'addHarmonics' in kwargs:
        if kwargs['addHarmonics']:
            harmonics_features = doHarmonicsFromOptions(ds.collection,**kwargs) # returns an ee.Image, not a hf.Dataset
            composite = composite.addBands(harmonics_features)
    
    # add JRC variables if desired
    if 'addJRCWater' in kwargs:
        if kwargs['addJRCWater']:
            composite = idx.addJRC(composite).unmask(0)
    
    # add topography variables if desired     
    if 'addTopography' in kwargs:
        if kwargs['addTopography']:
            composite = idx.addTopography(composite).unmask(0)
    
    return ee.Image(composite).clip(aoi)