from .external import CelltypeVersionsBase

CELLTYPES_HUMAN_MALEGONAD_V0 = [
    ['Antigen presenting cell (RPS high)', "nan"],
    ['B cell', "nan"],
    ['CB CD34+', "nan"],
    ['Dendritic cell', "nan"],
    ['Differentiating Spermatogonia', "nan"],
    ['Early Primary Spermatocytes', "nan"],
    ['Elongated Spermatids', "nan"],
    ['Endothelial cells', "nan"],
    ['Erythroid cell', "nan"],
    ['Erythroid progenitor cell (RP high)', "nan"],
    ['Fasciculata cell', "nan"],
    ['Fetal acinar cell', "nan"],
    ['Fetal chondrocyte', "nan"],
    ['Fetal epithelial progenitor', "nan"],
    ['Fetal fibroblast', "nan"],
    ['Fetal mesenchymal progenitor', "nan"],
    ['Fetal neuron', "nan"],
    ['Fetal skeletal muscle cell', "nan"],
    ['Fetal stromal cell', "nan"],
    ['Late primary Spermatocytes', "nan"],
    ['Leydig cells', "nan"],
    ['Loop of Henle', "nan"],
    ['Macrophages', "nan"],
    ['Monocyte', "nan"],
    ['Myoid cells', "nan"],
    ['Neutrophil', "nan"],
    ['Neutrophil (RPS high)', "nan"],
    ['Primordial germ cell', "nan"],
    ['Proximal tubule progenitor', "nan"],
    ['Round Spermatids', "nan"],
    ['Sertoli cells', "nan"],
    ['Smooth muscle cell', "nan"],
    ['Sperm', "nan"],
    ['Spermatogonial Stem cell', "nan"],
    ['Stromal cell', "nan"],
    ['T cell', "nan"],
    ['Ureteric bud cell', "nan"]
]
ONTOLOGIES_HUMAN_MALEGONAD_V0 = {
    "names": {},
    "ontology_ids": {},
}


class CelltypeVersionsHumanMalegonad(CelltypeVersionsBase):

    def __init__(self, **kwargs):
        self.celltype_universe = {
            "0": CELLTYPES_HUMAN_MALEGONAD_V0
        }
        self.ontology = {
            "0": ONTOLOGIES_HUMAN_MALEGONAD_V0
        }
        super(CelltypeVersionsHumanMalegonad, self).__init__(**kwargs)