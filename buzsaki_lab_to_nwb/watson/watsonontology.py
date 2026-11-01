"""HERD annotations linking the free-text values of a Watson file to ontology terms."""

from pynwb import NWBFile

OBO = "http://purl.obolibrary.org/obo/"

SUBJECT_TERMS = dict(
    species={"Rattus norvegicus": "NCBITaxon:10116"},
    # No strain term: the Rat Strain Ontology has Long Evans only as vendor lines (e.g. Crl:LE), and the paper does
    # not name the vendor
    sex={"M": "PATO:0000384"},
)
# Cortical regions as named in the CortexRegion field of the _BasicMetaData.mat files
REGION_TERMS = {
    "ACC": "UBERON:0009835",  # anterior cingulate cortex
    "mPFC": "UBERON:4450000",  # medial prefrontal cortex
    "OFC": "UBERON:0004167",  # orbitofrontal cortex
    # The lab's "MotorCtx" is the secondary motor cortex of Watson et al. 2016
    "MotorCtx": "UBERON:0016634",  # premotor cortex, synonym "nonprimary motor cortex"
    "CTX": "UBERON:0000956",  # cerebral cortex, the region of every unit in spikes.cellinfo.mat
}
CELL_TYPE_TERMS = {
    "excitatory": "CL:0000598",  # pyramidal neuron; the paper's pE cells are putative pyramidal cells
    "inhibitory": "CL:0000498",  # inhibitory interneuron
}


def term_uri(term: str) -> str:
    return OBO + term.replace(":", "_")


def add_ontology_annotations(nwbfile: NWBFile):
    herd = nwbfile.get_external_resources()

    def annotate_scalar(container, attribute, terms):
        value = getattr(container, attribute, None)
        if value in terms:
            herd.add_ref(
                container=container,
                attribute=attribute,
                key=value,
                entity_id=terms[value],
                entity_uri=term_uri(terms[value]),
            )

    def annotate_column(table, column_name, terms):
        if table is None or column_name not in table.colnames:
            return
        column = table[column_name]
        for value in sorted(set(column.data[:])):
            if value in terms:
                herd.add_ref(container=column, key=value, entity_id=terms[value], entity_uri=term_uri(terms[value]))

    for attribute, terms in SUBJECT_TERMS.items():
        annotate_scalar(nwbfile.subject, attribute, terms)
    for group in nwbfile.electrode_groups.values():
        annotate_scalar(group, "location", REGION_TERMS)
    annotate_column(nwbfile.electrodes, "location", REGION_TERMS)
    annotate_column(nwbfile.units, "region", REGION_TERMS)
    annotate_column(nwbfile.units, "cell_type", CELL_TYPE_TERMS)
