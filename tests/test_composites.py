from rlcms import composites
import ee
ee.Initialize(project='sig-ee-cloud')
region = ee.FeatureCollection("projects/wwf-sig/assets/kaza-lc/aoi/testSeshekeWater").geometry()
ds = composites.composite_aoi(dataset='Landsat8',
                              aoi=region,
                              start_date='2021-01-01',
                              end_date='2021-03-01',
                              indices=['EVI'],
                              addTopography=True,
                              addJRC=True,
                              addHarmonics=True,
                              addTasselCap=True,
                              harmonicsOptions={'red':{'start':1,'end':365}}
                              )





