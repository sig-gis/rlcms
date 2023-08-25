import ee
import hydrafloods as hf
from rlcms.harmonics import doHarmonicsFromOptions
from rlcms.covariates import indices
from rlcms.covariates import returnCovariatesFromOptions
from ee.ee_exception import EEException

ee.Initialize()

idx = indices()

def get_agg_timing(collection:hf.Dataset,**kwargs):
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

def composite(dataset:str,
                    region:ee.FeatureCollection,
                    start_date:str,
                    end_date:str,
                    **kwargs):
    
    """Processes multi-band composite of your chosen dataset(s) within an AOI footprint polygon

    args:
        dataset (str): one of: 'Landsat5','Landsat7','Landsat8','Sentinel1Asc','Sentinel1Desc','Sentinel2','Modis','Viirs')
        region (ee.FeatureCollection): area of interest
        start_date (str): start date
        end_date (str): end date
    
    kwargs:
        indices:list[str]
        composite_mode:str One of ['seasonal','annual'] Default = 'annual' 
        season:list[str|int]
        reducer:str|ee.Reducer
        addTasselCap:bool
        addTopography:bool
        addJRC:bool
        harmonicsOptions:dict in this format: {'nir':{'start':int[1:365],'end':[1:365]}}
    
    returns:
        ee.Image: multi-band image composite within region
    """
    # testing whether need to go b/w FC and Geometry for multi_poly
    if isinstance(region,ee.FeatureCollection):
         region = region.geometry()
         region_fc = region
    elif isinstance(region,ee.Geometry):
        region = region
    else:
        raise TypeError(f"{region} must be of type ee.FeatureCollection or ee.Geometry, got {type(region)}")
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
    
    # dataset can either be a named dataset string supported by a hf.Dataset sub-class 
    # or a GEE Asset path
    if isinstance(dataset,str):
        if dataset in ds_dict.keys(): 
            ds = ds_dict[dataset]
        else:
            if '/' in dataset: 
                try:
                    ds = hf.Dataset(asset_id=dataset,region=region,start_time=start_date,end_time=end_date)
                except:
                    raise EEException
            else: 
                raise ValueError(f"Could not construct a hf.Dataset from dataset name provided: {dataset}")
    else:
        raise TypeError(f"dataset must be str type, got: {type(dataset)}")
    
    # mask imgs to geometries in multi_poly mode
    if 'multi_poly' in kwargs:
        if kwargs['multi_poly'] == True:
            def update_mask(img):
                ref_poly_img = ee.Image(1).paint(region_fc).Not().selfMask() # aoi can be ee.Geometry or ee.FeatureCollection for this
                return ee.Image(img).updateMask(ref_poly_img)
            # do we want to warn user against using multi_poly unnecessarily if aoi is a single geometry?
            # would require another synchronous request of aoi's type/element size
            ds = ds.apply_func(update_mask)
    
    ds = ds.apply_func(returnCovariatesFromOptions,**kwargs)
    
    # set reducer passed to aggregate_time(), default mean
    if 'reducer' in kwargs:
        reducer=kwargs['reducer']
    else:
        reducer = 'mean'
    
    period,period_unit,dates = get_agg_timing(ds,**kwargs)
    
    # aggregate hf.Dataset
    agg_time_result = (ds.aggregate_time(reducer=reducer,
                                    rename=False,
                                    period_unit=period_unit,
                                    period=period,
                                    dates=dates)
                                    )
    
    composite = ee.ImageCollection(agg_time_result.collection).toBands()
    
    # rename bands depending on number of resulting images
    if agg_time_result.n_images > 1:
        bnames = composite.bandNames().map(lambda b: ee.String('t').cat(b))
    else:
        bnames = composite.bandNames().map(lambda b: ee.String(b).slice(2))
    
    composite = composite.rename(bnames)
        
    # compute harmonics if desired
    if 'harmonicsOptions' in kwargs:
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
    
    return ee.Image(composite).clip(region)