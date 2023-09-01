import rlcms.composites_class_based as composites
import ee
import geemap

ee.Initialize()

# some args we'll use in both composites
start_date = '2018-01-01'
end_date = '2018-12-31'
reducer = 'mean' # min, max, ee.Reducer objects
composite_mode = 'annual' # 'annual'

sesheke = ee.FeatureCollection("projects/wwf-sig/assets/kaza-lc/aoi/testSeshekeWater")
# binga_polys = ee.FeatureCollection("projects/wwf-sig/assets/kaza-lc/reference_data/BingaDummyReferencePolys")
ca_poly = ee.Geometry.Polygon([[-120.70162384826843,36.658181801020476],
                               [-120.65218537170593,36.658181801020476],
                               [-120.65218537170593,36.68461734040718],
                               [-120.70162384826843,36.68461734040718],
                               [-120.70162384826843,36.658181801020476]])

s1composite = composites.composite(dataset='Sentinel1',
                                  region=sesheke,
                                  start_date=start_date,
                                  end_date=end_date,
                                 composite_mode=composite_mode,
                                 reducer=reducer)
s2composite = composites.composite(dataset='Sentinel2',
                                 region=sesheke,
                                 start_date=start_date,
                                 end_date=end_date,
                                 indices=['IBI','SAVI'],
                                 composite_mode=composite_mode,
                                 reducer=reducer)

print(s2composite.bands)
print(s2composite.composite.propertyNames().getInfo())
# print(s2composite.bandNames().getInfo())
# all_composite = s2composite.addBands(s1composite)
# print(all_composite.bandNames().getInfo())