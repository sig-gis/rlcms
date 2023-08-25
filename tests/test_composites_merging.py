#%%
from rlcms import composites
import ee
import hydrafloods as hf
ee.Initialize()

#%%
# tiny test rect in CA
## region = ee.Geometry.Polygon([[-120.70162384826843,36.658181801020476],
#                                [-120.65218537170593,36.658181801020476],
#                                [-120.65218537170593,36.68461734040718],
#                                [-120.70162384826843,36.68461734040718],
#                                [-120.70162384826843,36.658181801020476]])
aoi = ee.FeatureCollection("projects/wwf-sig/assets/kaza-lc/aoi/testSeshekeWater")#.geometry()
start_date = '2021-01-01'
end_date='2021-12-31'

# class TestComposites:
def test_composite_bands():
  
  # default behavior of composite() is annual mean composite
  composite = composites.composite(dataset=['Sentinel2','Sentinel1'],
                                aoi=aoi,
                                start_date=start_date,
                                end_date=end_date)
  print(composite.bandNames().getInfo())
  
# %%
test_composite_bands()
# %%
