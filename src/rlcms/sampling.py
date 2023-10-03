import ee
ee.Initialize()
 
def distanceFilter(pts,distance):
    """Filter Points within a FeatureCollection by a minimum distance threshold"""
    withinDistance = distance

    ## From the User Guide: https:#developers.google.com/earth-engine/joins_spatial
    ## add extra filter to eliminate self-matches
    distFilter = ee.Filter.And(ee.Filter.withinDistance(**{
      'distance': withinDistance,
      'leftField': '.geo',
      'rightField': '.geo', 
      'maxError': 1
    }), ee.Filter.notEquals(**{
      'leftField': 'system:index',
      'rightField': 'system:index',

    }))
    
    distSaveAll = ee.Join.saveAll(**{
                  'matchesKey': 'points',
                  'measureKey': 'distance'
    })
    # Apply the join.
    spatialJoined = distSaveAll.apply(pts, pts, distFilter)

    # Check the number of matches.
    # We're only interested if nmatches > 0.
    spatialJoined = spatialJoined.map(lambda f: f.set('nmatches', ee.List(f.get('points')).size()) )
    spatialJoined = spatialJoined.filterMetadata('nmatches', 'greater_than', 0)

    # The real matches are only half the total, because if p1.withinDistance(p2) then p2.withinDistance(p1)
    # Use some iterative logic to clean up
    def unpack(l): 
        return ee.List(l).map(lambda f: ee.Feature(f).id())

    def iterator_f(f,list):
        key = ee.Feature(f).id()
        list = ee.Algorithms.If(ee.List(list).contains(key), list, ee.List(list).cat(unpack(ee.List(f.get('points')))))
        return list
    
    ids = spatialJoined.iterate(iterator_f,ee.List([]))

    # Clean up 
    cleaned_pts = pts.filter(ee.Filter.inList('system:index', ids).Not())
    return cleaned_pts

# This func was developed with the idea that the user wants to extract 
# training or validation sample pts from an underlying ee.Image 
# using either a set of points or polygons as reference 
def strat_sample_from_reference(img:ee.Image,collection:ee.FeatureCollection,class_band:str,scale:int,crs:str,seed:int,
                              class_values:list,class_points:list):
    """
    Generates stratified random sample pts from reference polygons with all bands from input image extracted
    
    args:
      img (ee.Image): image whose bands will be extracted to the sample points
      collection (ee.FeatureCollection): reference polygons FeatureCollection
      class_band (str): property name of the reference (i.e. 'LANDCOVER')
      scale (int): resolution to sample the grid at
      seed (int): random seed
      class_values (list): unique reference labels (e.g. [1,2,3,4])
      class_points (list): number of points to sample per label (e.g. [100,200,100,200])
    returns:
      ee.FeatureCollection of sample points 
        They will contain the properties inherited from the reference polygons, 
          a 'random' property, and all bands from the image as properties.
    """
  
    # zip class_values and class_points together so they are easily accessible by map() index
    zip_value_n = ee.List(class_values).zip(ee.List(class_points))

    # done for each [class_value,class_points] pair
    def do_by_class(value_n):
        class_value = ee.List(value_n).get(0)
        n_points = ee.List(value_n).get(1)
        filtered_poly_by_class = collection.filter(ee.Filter.eq(class_band,class_value))
        
        def fromPolys(coll):
            geom = coll.geometry()
            # generate n random pts, n_points*multiplier
            multiplier = 2
            random_pts = (ee.FeatureCollection.randomPoints(geom,ee.Number(n_points).multiply(multiplier),seed,0.001)
                          .map(lambda f: f.set(class_band,class_value))) # class_band value from underlying poly geo must copy over into each point set
            # extract raster data to the points then limit to n_points requested
            rawSample_fromPts = ee.Image(img).sampleRegions(
                collection=random_pts, 
                scale=scale,
                projection=crs, 
                tileScale=16, 
                geometries=True).randomColumn().limit(n_points,'random')
            return rawSample_fromPts
        def fromPoints(coll):
            # extract band info to every pt in coll, then limit to n_points requested
            rawSample_fromPts = ee.Image(img).sampleRegions(
                collection=coll, 
                scale=scale,
                projection=crs, 
                tileScale=16, 
                geometries=True).randomColumn().limit(n_points,'random')
            return rawSample_fromPts
        
        # check if collection's geometry type is Polygon
        types = ee.List([ee.String('Polygon'),ee.String('MultiPolygon')])
        geom_type = collection.geometry().type()
        # conditional: 1 if geom_type=='Polygon' or 'MultiPolygon', else 0 - this is a little hacky not sure if there's a better way
        check_poly = types.map(lambda type: ee.String(type).match(geom_type)).flatten().size().gte(1)
        samples = ee.Algorithms.If(check_poly,fromPolys(filtered_poly_by_class),fromPoints(filtered_poly_by_class))
        # output_properties = ee.List(img.bandNames()).add(ee.String(class_band))
        
        return ee.FeatureCollection(samples)#.map(lambda f: f.select(output_properties))
    
    output_properties = ee.List(img.bandNames()).add(ee.String(class_band))
    pts_by_class = ee.FeatureCollection(ee.List(zip_value_n).map(do_by_class)).flatten().map(lambda f: f.select(output_properties))
    return pts_by_class

def strat_sample(img,class_band,region,scale,seed,n_points,class_values,class_points,ceo_format=True):
    """
    A wrapper for ee.Image.stratifiedSample() with CEO schema formatting if desired
    Note: This function has been found to be less efficient on EECUs and Memory than those defined above.
            Use the strat_sample_w_extraction for training data generation
            strat_sample_no_extraction can be used for testing data generation (predictor bands not required)
    """
    stratSample = ee.Image(img).stratifiedSample(
        numPoints=n_points,
        classBand=class_band,
        region=region,
        scale=scale, 
        seed=seed, 
        classValues=class_values,
        classPoints=class_points,
        dropNulls=True, 
        tileScale=16,
        geometries=True)
    
    if ceo_format:
        return stratSample.map(ceoClean)
    else:
        return stratSample

def split_train_test(pts,seed):
    """stratify 80/20 train and test points"""
    
    featColl = ee.FeatureCollection(pts)
    featColl = featColl.randomColumn(columnName='random', seed=seed)
    filt = ee.Filter.lt('random',0.8)
    train = featColl.filter(filt).map(lambda f: f.select(f.propertyNames().remove('random'))) # remove 'random' property
    test = featColl.filter(filt.Not()).map(lambda f: f.select(f.propertyNames().remove('random')))

    return train, test

def ceoClean(f):
        # LON,LAT,PLOTID,SAMPLEID.,
        fid = f.id()
        coords = f.geometry().coordinates()
        return f.set('LON',coords.get(0),
                    'LAT',coords.get(1),
                    'PLOTID',fid,
                    'SAMPLEID',fid)

def plot_id_global(n,feat):
    """takes an index number (n) and adds it to current PLOTID property of a feature 
            to ensure PLOTID values are globally unique (necessary for multiple sets of AOI sampling)"""
    aoi_id = ee.String(str(n))
    f = ee.Feature(feat)
    gid = aoi_id.cat('_').cat(ee.String(f.get('PLOTID')))
    f = f.set('PLOTID',gid, 'SAMPLEID', gid)
    return f

# these two funcs were developed with the idea that the user may want to 
# generate stratified random sample pts from reference polygons, their intent 
# would match one of these two:
# 1) extract band values from an underlying ee.Image (like a composite) to the sample pts (to make training data) [strat_sample_w_extraction]
# 2) don't extract band values from an underlying ee.Image (effectively a shortcut function to turn ref polys into validation points) [strat_sample_no_extraction]
# unclear as of yet if these func's add value or are a slight variant
# strat_sample_from_reference() above was developed as an extension of strat_sample_w_extraction to allow you to do this with points or polygons
# strat_sample_no_extraction() may have no utility other than potential performance improvments over strat_sample()
def strat_sample_no_extraction(collection:ee.FeatureCollection,class_band:str,scale:int,seed:int,
                               class_values:list=None,class_points:list=None):
    """
    Generates stratified random sample pts from reference polygons. Does not extract raster data to the points. 
    
    args:
      collection (ee.FeatureCollection): reference polygons FeatureCollection
      class_band (str): property name of the reference (i.e. 'LANDCOVER')
      scale (int): resolution to sample the grid at
      seed (int): random seed
      class_values (list): unique reference labels (e.g. [1,2,3,4])
      class_points (list): number of points to sample per label (e.g. [100,200,100,200])
    returns:
      ee.FeatureCollection of sample points 
        They will contain the properties inherited from the reference polygons and a 'random' property
    """
    # zip class_values and class_points together so they are easily accessible by map() index
    zip_value_n = ee.List(class_values).zip(ee.List(class_points))

    # done for each class and its desired n_points
    def do_by_class(value_n):
        class_value = ee.List(value_n).get(0)
        n_points = ee.List(value_n).get(1)
        # get polys by each class_band value at a time
        filtered_poly_by_class = collection.filter(ee.Filter.eq(class_band,class_value))
        geom = filtered_poly_by_class.geometry()
        # generate random pts, more than user specified
        random_pts = ee.FeatureCollection.randomPoints(geom,ee.Number(n_points).multiply(2),seed) 
        # filter out pts too close to each other at user specified scale
        random_pts = (ee.FeatureCollection(distanceFilter(random_pts,scale))
                      .randomColumn().limit(n_points,'random')) # shuffle, then try to return exact # pts user specified
        # set class_band as a property to the features
        random_pts = random_pts.map(lambda f: f.set(class_band,class_value))
        return ee.FeatureCollection(random_pts)

    pts_by_class = ee.FeatureCollection(ee.List(zip_value_n).map(do_by_class)).flatten()
    
    return pts_by_class
        

# working on optimized stratified sample function not using .stratifiedSample()
def strat_sample_w_extraction(img:ee.Image,collection:ee.FeatureCollection,scale:int,crs:str,class_band:str,seed:int,
                              class_values:list,class_points:list):
  """
    Generates stratified random sample pts from reference polygons with all bands from input image extracted
    
    args:
      img (ee.Image): image whose bands will be extracted to the sample points
      collection (ee.FeatureCollection): reference polygons FeatureCollection
      class_band (str): property name of the reference (i.e. 'LANDCOVER')
      scale (int): resolution to sample the grid at
      seed (int): random seed
      class_values (list): unique reference labels (e.g. [1,2,3,4])
      class_points (list): number of points to sample per label (e.g. [100,200,100,200])
    returns:
      ee.FeatureCollection of sample points 
        They will contain the properties inherited from the reference polygons, 
          a 'random' property, and all bands from the image as properties.
    """
  
  # zip class_values and class_points together so they are easily accessible by map() index
  zip_value_n = ee.List(class_values).zip(ee.List(class_points))
  
  # done for each [class_value,class_points] pair
  def do_by_class(value_n):
    class_value = ee.List(value_n).get(0)
    n_points = ee.List(value_n).get(1)
    filtered_poly_by_class = collection.filter(ee.Filter.eq(class_band,class_value))
    geom = filtered_poly_by_class.geometry()
    # generate random pts, more than user specified
    random_pts = ee.FeatureCollection.randomPoints(geom,ee.Number(n_points).multiply(2),seed) 
    # set class_band as property 
    random_pts = random_pts.map(lambda f: f.set(class_band,class_value))
    # extract raster data to the points and try to take specific n_points specified
    rawSample_fromPts = ee.Image(img).sampleRegions(
          collection=random_pts, 
          scale=scale,
          projection=crs, 
          tileScale=16, 
          geometries=True).randomColumn().limit(n_points,'random')
    
    return ee.FeatureCollection(rawSample_fromPts)
  
  
  pts_by_class = ee.FeatureCollection(ee.List(zip_value_n).map(do_by_class)).flatten()
  return pts_by_class