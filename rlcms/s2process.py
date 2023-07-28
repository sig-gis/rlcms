import ee
from rlcms import covariates
from rlcms import harmonics
from rlcms.model_inputs import model_inputs
idx = covariates.indices()

# Global S2 Processing Parameters
CLOUD_FILTER = 70
CLD_PRB_THRESH = 40
NIR_DRK_THRESH = 0.15
CLD_PRJ_DIST = 2
BUFFER = 100

def get_s2_sr_cld_col(aoi, start_date, end_date):
    """Create S2 SR + S2 Cloud Probability Image Collection"""
    # Import and filter S2 SR.
    s2_sr_col = (ee.ImageCollection('COPERNICUS/S2_SR')
        .filterBounds(aoi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', CLOUD_FILTER)))

    # Import and filter s2cloudless.
    s2_cloudless_col = (ee.ImageCollection('COPERNICUS/S2_CLOUD_PROBABILITY')
        .filterBounds(aoi)
        .filterDate(start_date, end_date))

    # Join the filtered s2cloudless collection to the SR collection by the 'system:index' property.
    return ee.ImageCollection(ee.Join.saveFirst('s2cloudless').apply(**{
        'primary': s2_sr_col,
        'secondary': s2_cloudless_col,
        'condition': ee.Filter.equals(**{
            'leftField': 'system:index',
            'rightField': 'system:index'
        })
    }))
    
def add_cloud_bands(img):
    """computes cloud probability and probability threshold binary cloud mask as bands to input image"""
    # Get s2cloudless image, subset the probability band.
    cld_prb = ee.Image(img.get('s2cloudless')).select('probability')

    # Condition s2cloudless by the probability threshold value.
    is_cloud = cld_prb.gt(CLD_PRB_THRESH).rename('clouds')

    # Add the cloud probability layer and cloud mask as image bands.
    return img.addBands(ee.Image([cld_prb, is_cloud]))
    
def add_shadow_bands(img):
    """adds dark pixels, cloud projection and shadows images as bands to input image"""
    # Identify water pixels from the SCL band.
    not_water = img.select('SCL').neq(6)

    # Identify dark NIR pixels that are not water (potential cloud shadow pixels).
    SR_BAND_SCALE = 1e4
    dark_pixels = img.select('B8').lt(NIR_DRK_THRESH*SR_BAND_SCALE).multiply(not_water).rename('dark_pixels')

    # Determine the direction to project cloud shadow from clouds (assumes UTM projection).
    shadow_azimuth = ee.Number(90).subtract(ee.Number(img.get('MEAN_SOLAR_AZIMUTH_ANGLE')));

    # Project shadows from clouds for the distance specified by the CLD_PRJ_DIST input.
    cld_proj = (img.select('clouds').directionalDistanceTransform(shadow_azimuth, CLD_PRJ_DIST*10)
        .reproject(**{'crs': img.select(0).projection(), 'scale': 100})
        .select('distance')
        .mask()
        .rename('cloud_transform'))

    # Identify the intersection of dark pixels with cloud shadow projection.
    shadows = cld_proj.multiply(dark_pixels).rename('shadows')

    # Add dark pixels, cloud projection, and identified shadows as image bands.
    return img.addBands(ee.Image([dark_pixels, cld_proj, shadows]))

def add_cld_shdw_mask(img):
    """Adds a cloud-shadow mask as a band to the input image"""
    # Add cloud component bands.
    img_cloud = add_cloud_bands(img)

    # Add cloud shadow component bands.
    img_cloud_shadow = add_shadow_bands(img_cloud)

    # Combine cloud and shadow mask, set cloud and shadow as value 1, else 0.
    is_cld_shdw = img_cloud_shadow.select('clouds').add(img_cloud_shadow.select('shadows')).gt(0)

    # Remove small cloud-shadow patches and dilate remaining pixels by BUFFER input.
    # 20 m scale is for speed, and assumes clouds don't require 10 m precision.
    is_cld_shdw = (is_cld_shdw.focal_min(2).focal_max(BUFFER*2/20)
        .reproject(**{'crs': img.select([0]).projection(), 'scale': 20})
        .rename('cloudmask'))

    # Add the final cloud-shadow mask to the image.
    return img.addBands(is_cld_shdw)
  
def apply_cld_shdw_mask(img):
    """apply cloud shadow mask to each image"""
    # Subset the cloudmask band and invert it so clouds/shadow are 0, else 1.
    not_cld_shdw = img.select('cloudmask').Not()

    # Subset reflectance bands and update their masks, return the result.
    return img.select('B.*').updateMask(not_cld_shdw)
    
def add_covariates(img):
    "Adds select indices to the S2 image, assumes band names have already been renamed (blue,green,red,etc)"
    covariates = ["blue","green","red","nir","swir1","swir2","EVI","SAVI","IBI",] # full list of unique spectral covariate bands
    img = ee.Image(img).addBands(idx.EVI(img)).addBands(idx.SAVI(img)).addBands(idx.IBI(img))
    img = img.select(covariates) # because .addBands() will create duplicates of pre-existing bands
    return img

def s2process(aoi:ee.FeatureCollection,start_year:int,end_year:int):
    """
    Processes an annual Sentinel-2 SR multi-band composite within an AOI footprint polygon

    Uses model_inputs settings dictionary stored at src/utils/model_inputs.py and imported at top of file 
        to compute specific indices and time series features

    args:
        aoi (ee.FeatureCollection): AOI footprint polygon FC
        start_year (int): start year
        end_year (int): end year
    
    returns:
        ee.Image raster stack of S2 bands and covariates within AOI polygon

    """
    start_date = ee.Date.fromYMD(start_year,1,1)
    end_date = ee.Date.fromYMD(end_year,12,31)
    
    s2_sr_cld_col = get_s2_sr_cld_col(aoi, start_date, end_date)

    imgColl =  ee.ImageCollection(s2_sr_cld_col.map(add_cld_shdw_mask)
                .map(apply_cld_shdw_mask)
                .select(["B2","B3","B4","B8","B11","B12"],['blue','green','red','nir','swir1','swir2'])
                )
    
    # compute spectral indices per image (set in model_inputs settings) 
    addedIndices = imgColl.map(covariates.returnCovariatesFromOptions)
    
    # compute desired percentile composites on bands/indices (set in model_inputs settings) 
    percentile_options = model_inputs['percentileOptions']
    percentiles = addedIndices.reduce(ee.Reducer.percentile(percentiles=percentile_options))
    
    # compute harmonics if desired (set in model_inputs settings) 
    if model_inputs['addHarmonics']:
        harmonics_features = harmonics.doHarmonicsFromOptions(addedIndices) 
    stack = ee.Image.cat([percentiles,harmonics_features])
    
    # add JRC variables if desired (set in model_inputs settings) 
    if model_inputs['addJRCWater']:
        stack = idx.addJRC(stack).unmask(0)
    
    # add topography variables if desired (set in model_inputs settings)     
    if model_inputs['addTopography']:
         stack = idx.addTopography(stack).unmask(0)

    return ee.Image(stack)

def s2process_refdata(ref_polys:ee.FeatureCollection,ref_label:str,ref_year:int):
    """
    Processes an annual Sentinel-2 SR multi-band composite within reference polygon footprints
    Uses model_inputs settings dictionary stored at src/utils/model_inputs.py and imported at top of file 
        to compute specific indices and time series features
    
    args: 
    ref_polys: reference polygon FeatureCollection
    ref_label: predictor property name the model needs (e.g. 'LANDCOVER')
    ref_year: year that the polygons were interpreted for, controls time period of s2 imagery used in the composite
    
    Returns: ee.Image raster stack of S2 bands and covariates within footprints of reference polygons
    """
    start_date = ee.Date.fromYMD(ref_year,1,1)
    end_date = ee.Date.fromYMD(ref_year,12,31)
    
    ref_poly_img = ee.Image(0).paint(ref_polys,ref_label).rename(ref_label).selfMask()

    s2_sr_cld_col = get_s2_sr_cld_col(ref_polys, start_date, end_date)

    imgColl =  ee.ImageCollection(s2_sr_cld_col.map(add_cld_shdw_mask)
                .map(lambda img: ee.Image(img).updateMask(ref_poly_img)) #mask imgs to ref poly areas before doing more heavy compute
                .map(apply_cld_shdw_mask)
                .select(["B2","B3","B4","B8","B11","B12"],['blue','green','red','nir','swir1','swir2'])
                )

    # compute spectral indices per image from model_inputs settings
    addedIndices = imgColl.map(covariates.returnCovariatesFromOptions)
    
    # compute desired percentile composites on bands/indices from model_inputs settings
    percentile_options = model_inputs['percentileOptions']
    percentiles = addedIndices.reduce(ee.Reducer.percentile(percentiles=percentile_options))
    
    # compute harmonics if desired (set in model_inputs settings)
    if model_inputs['addHarmonics']:
        harmonics_features = harmonics.doHarmonicsFromOptions(addedIndices) 
    stack = ee.Image.cat([percentiles,harmonics_features])
    
    # add JRC variables if desired (set in model_inputs settings)
    if model_inputs['addJRCWater']:
        stack = idx.addJRC(stack).unmask(0) # 0s are valid values for these variables
    
    # add topography variables if desired (set in model_inputs settings) 
    if model_inputs['addTopography']:
         stack = idx.addTopography(stack).unmask(0) # 0s are valid values for these variables
    
    return ee.Image(stack).updateMask(ref_poly_img)
    # have to update mask again because of the unmask(0)s for JRC and Topo.
    # ensures all pixels outside of reference polygons are masked