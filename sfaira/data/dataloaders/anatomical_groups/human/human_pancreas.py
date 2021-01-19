from typing import Union

from .external import DatasetGroup

from sfaira.data.dataloaders.loaders.d10_1016_j_cels_2016_08_011.human_pancreas_2016_indrop_baron_001 import Dataset as Dataset0001
from sfaira.data.dataloaders.loaders.d10_1016_j_cmet_2016_08_020.human_pancreas_2016_smartseq2_segerstolpe_001 import Dataset as Dataset0002
from sfaira.data.dataloaders.loaders.d10_1016_j_cell_2017_09_004.human_pancreas_2017_smartseq2_enge_001 import Dataset as Dataset0003
from sfaira.data.dataloaders.loaders.d10_1038_s41586_020_2157_4.human_pancreas_2020_microwell_han_001 import Dataset as Dataset0004
from sfaira.data.dataloaders.loaders.d10_1038_s41586_020_2157_4.human_pancreas_2020_microwell_han_002 import Dataset as Dataset0005
from sfaira.data.dataloaders.loaders.d10_1038_s41586_020_2157_4.human_pancreas_2020_microwell_han_003 import Dataset as Dataset0006
from sfaira.data.dataloaders.loaders.d10_1038_s41586_020_2157_4.human_pancreas_2020_microwell_han_004 import Dataset as Dataset0007


class DatasetGroupPancreas(DatasetGroup):

    def __init__(
        self,
        path: Union[str, None] = None,
        meta_path: Union[str, None] = None,
        cache_path: Union[str, None] = None
    ):
        datasets = [
            Dataset0001(path=path, meta_path=meta_path, cache_path=cache_path),
            Dataset0002(path=path, meta_path=meta_path, cache_path=cache_path),
            Dataset0003(path=path, meta_path=meta_path, cache_path=cache_path),
            Dataset0004(path=path, meta_path=meta_path, cache_path=cache_path),
            Dataset0005(path=path, meta_path=meta_path, cache_path=cache_path),
            Dataset0006(path=path, meta_path=meta_path, cache_path=cache_path),
            Dataset0007(path=path, meta_path=meta_path, cache_path=cache_path)
        ]
        keys = [x.id for x in datasets]
        super().__init__(datasets=dict(zip(keys, datasets)))
        # Load versions from extension if available:
        try:
            from sfaira_extension.data.human import DatasetGroupPancreas
            self.datasets.update(DatasetGroupPancreas(path=path, meta_path=meta_path, cache_path=cache_path).datasets)
        except ImportError:
            pass