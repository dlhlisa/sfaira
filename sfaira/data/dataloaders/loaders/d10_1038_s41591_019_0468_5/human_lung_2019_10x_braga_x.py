import anndata
import os
from typing import Union
import numpy as np

from sfaira.data import DatasetBaseGroupLoadingManyFiles

SAMPLE_FNS = [
    "vieira19_Alveoli_and_parenchyma_anonymised.processed.h5ad",
    "vieira19_Bronchi_anonymised.processed.h5ad",
]


class Dataset(DatasetBaseGroupLoadingManyFiles):

    def __init__(
            self,
            sample_fn: str,
            path: Union[str, None] = None,
            meta_path: Union[str, None] = None,
            cache_path: Union[str, None] = None,
            **kwargs
    ):
        super().__init__(sample_fn=sample_fn, path=path, meta_path=meta_path, cache_path=cache_path, **kwargs)
        self.id = f"human_lung_2019_10x_braga_{str(SAMPLE_FNS.index(self.sample_fn)).zfill(3)}_" \
                  f"10.1038/s41591-019-0468-5"

        self.download_url_data = f"https://covid19.cog.sanger.ac.uk/{self.sample_fn}"
        self.download_url_meta = None

        self.author = "Teichmann"
        self.doi = "10.1038/s41591-019-0468-5"
        self.healthy = True
        self.organ = "bronchus" if sample_fn == "vieira19_Bronchi_anonymised.processed.h5ad" else "lung parenchyma"
        self.organism = "human"
        self.protocol = "10X sequencing"
        self.state_exact = "healthy"
        self.year = 2019
        self.normalization = "norm"

        self.var_symbol_col = "index"

        self.obs_key_cellontology_original = "CellType"

        if self.sample_fn == "vieira19_Alveoli_and_parenchyma_anonymised.processed.h5ad":
            self.class_maps = {
                "0": {
                    "Ciliated 2": "Multiciliated lineage",
                    "Luminal_Macrophages": "Macrophages",
                    "Basal 1": "Basal",
                    "Dendritic cells": "Dendritic cells",
                    "Endothelial": "1_Endothelial",
                    "Lymphatic": "Lymphatic EC",
                    "Ciliated 1": "Multiciliated lineage",
                    "Smooth muscle": "2_Smooth Muscle",
                    "Type_1_alveolar": "AT1",
                    "Neutrophils": "Monocytes",
                    "Club": "Secretory",
                    "Basal 2": "Basal",
                    "B cells": "B cell lineage",
                    "T and NK": "2_Lymphoid",
                    "Mesothelium": "Mesothelium",
                    "Mast cells": "Mast cells",
                    "Fibroblasts": "2_Fibroblast lineage",
                    "Type 2 alveolar": "AT2",
                },
            }
        else:
            self.class_maps = {
                "0": {
                    "Ciliated 1": "Multiciliated lineage",
                    "Club": "Secretory",
                    "Ciliated 2": "Multiciliated lineage",
                    "Ionocytes": "Rare",
                    "Basal 2": "Basal",
                    "Goblet_1": "Secretory",
                    "Goblet 2": "Secretory",
                    "Basal 1": "Basal",
                    "Dendritic cells": "Dendritic cells",
                    "B cells": "B cell lineage",
                    "Luminal_Macrophages": "Macrophages",
                    "Neutrophils": "Monocytes",
                    "Endothelial": "1_Endothelial",
                    "Smooth muscle": "2_Smooth Muscle",
                    "T and NK": "2_Lymphoid",
                    "Fibroblasts": "2_Fibroblast lineage",
                    "Lymphatic": "Lymphatic EC",
                    "Mast cells": "Mast cells",
                },
            }

    def _load(self):
        fn = os.path.join(self.doi_path, self.sample_fn)
        self.adata = anndata.read(fn)
        self.adata.X = np.expm1(self.adata.X)

        self.set_unkown_class_id(ids=["1_Unicorns and artifacts"])