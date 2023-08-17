from rlcms import composites
import ee
import hydrafloods as hf
ee.Initialize()

# tiny test rect in CA
region = ee.Geometry.Polygon([[-120.70162384826843,36.658181801020476],
                               [-120.65218537170593,36.658181801020476],
                               [-120.65218537170593,36.68461734040718],
                               [-120.70162384826843,36.68461734040718],
                               [-120.70162384826843,36.658181801020476]])
# aoi = ee.FeatureCollection("projects/wwf-sig/assets/kaza-lc/aoi/testSeshekeWater")#.geometry()
start_date = '2021-01-01'
end_date='2021-12-31'

# class TestComposites:
def test_composite_bands():
  
  # default behavior of composite() is annual mean composite
  composite = composites.composite(dataset='Sentinel2',
                                aoi=region,
                                start_date=start_date,
                                end_date=end_date)
  assert composite.bandNames().getInfo() == ['blue_mean','green_mean','red_mean',
                                            'nir_mean','swir1_mean','swir2_mean']
def test_composite_values():
  composite = composites.composite(dataset='Sentinel2',
                                aoi=region,
                                start_date=start_date,
                                end_date=end_date)
  # sample some points and compare their extracted pixel values from both methods' ee.Images
  points = ee.FeatureCollection.randomPoints(region,5)
  # stack = composite.addBands(sen2_composite)
  comparison_pts = composite.sampleRegions(collection=points,scale=10)
  
  assert comparison_pts.aggregate_array('blue_mean') == [363.6774193548387, 655.3863636363636, 964.709090909091, 1108.4954545454545, 1335.3148148148148]

test_composite_bands()
test_composite_values()





