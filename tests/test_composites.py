from rlcms import composites
import ee
ee.Initialize(project='sig-ee-cloud')
region = ee.FeatureCollection("projects/wwf-sig/assets/kaza-lc/aoi/testSeshekeWater").geometry()
settings_d = {'addTopography':True}
ds = composites.composite_aoi(dataset='Landsat8',
                              aoi=region,
                              start_date='2021-01-01',
                              end_date='2021-03-01',
                              settings = settings_d
                            #   settings=r'C:\Users\kyle\Downloads\model_settings_template.txt'
                              )





