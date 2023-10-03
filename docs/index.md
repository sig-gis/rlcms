# Regional Land Cover Monitoring System
## Installation
Install with pip: 
```
pip install rlcms
```

Test that `earthengine-api` is setup and authenticated by checking the folder contents within one of your cloud projects. 
* In your shell, run:
```
earthengine set_project <project-name>
earthengine ls projects/project-name/assets
```
If you do not get an error and it returns a list of folders and assets similar to this then you are good to go! :tada:

## Features

* stratified sampling for use in Collect Earth Online
* Training and validation data extraction, from points or polygon references
* Land cover modeling using Primitive ensembles, complete with model metrics for iterative improvements

## Quick Start

```
from rlcms.composites import Composite
# Create an annual Sentinel-1 Composite
c = Composite(dataset='Sentinel1',
        region=aoi,
        start_date='2020-01-01',
        end_date='2021-12-31',
        composite_mode='annual',
        reducer='median')

# look at the Composite object
print(c.__dict__)

# retrieve band names
print(f"Composite bands:{c.bands}")

# retrieve ee.Image from Composite object 
image = c.image
```

## Contributing

We welcome contributions from the community. If there are issues are improvements, please submit an issue on Github: [https://github.com/sig-gis/rlcms](https://github.com/sig-gis/rlcms)

## License

This project is licensed under the GPL-3 License - see the LICENSE file for details.