from .external import CelltypeVersionsBase

CELLTYPES_HUMAN_SPINALCORD_V0 = [
    ['Antigen presenting cell (RPS high)', "nan"],
    ['Astrocyte', "nan"],
    ['B cell', "nan"],
    ['B cell (Plasmocyte)', "nan"],
    ['CB CD34+', "nan"],
    ['Dendritic cell', "nan"],
    ['Endothelial cell', "nan"],
    ['Epithelial cell', "nan"],
    ['Erythroid cell', "nan"],
    ['Erythroid progenitor cell (RP high)', "nan"],
    ['Fetal Neuron', "nan"],
    ['Fetal chondrocyte', "nan"],
    ['Fetal endocrine cell', "nan"],
    ['Fetal enterocyte ', "nan"],
    ['Fetal epithelial progenitor', "nan"],
    ['Fetal mesenchymal progenitor', "nan"],
    ['Fetal neuron', "nan"],
    ['Fetal skeletal muscle cell', "nan"],
    ['Fetal stromal cell', "nan"],
    ['Fibroblast', "nan"],
    ['Kidney intercalated cell', "nan"],
    ['Loop of Henle', "nan"],
    ['M2 Macrophage', "nan"],
    ['Macrophage', "nan"],
    ['Monocyte', "nan"],
    ['Neutrophil', "nan"],
    ['Neutrophil (RPS high)', "nan"],
    ['Primordial germ cell', "nan"],
    ['Proliferating T cell', "nan"],
    ['Sinusoidal endothelial cell', "nan"],
    ['Smooth muscle cell', "nan"],
    ['Stratified epithelial cell', "nan"],
    ['Stromal cell', "nan"],
    ['T cell', "nan"],
    ['hESC', "nan"]
]
ONTOLOGIES_HUMAN_SPINALCORD_V0 = {
    "names": {},
    "ontology_ids": {},
}


class CelltypeVersionsHumanSpinalcord(CelltypeVersionsBase):

    def __init__(self, **kwargs):
        self.celltype_universe = {
            "0": CELLTYPES_HUMAN_SPINALCORD_V0
        }
        self.ontology = {
            "0": ONTOLOGIES_HUMAN_SPINALCORD_V0
        }
        super(CelltypeVersionsHumanSpinalcord, self).__init__(**kwargs)