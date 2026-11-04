"""External resource (HERD) annotations for the Petersen conversion.

The terms are stored in the NWB file's ``external_resources`` group (NWB 2.11), read back with
``nwbfile.external_resources.to_dataframe()``. Each term was checked on OLS (https://www.ebi.ac.uk/ols4).
"""

from pynwb import NWBFile


def obo(curie: str) -> tuple:
    """The CURIE and its OBO PURL."""
    return curie, "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


SPECIES = {"Rattus norvegicus": obo("NCBITaxon:10116")}
SEXES = {"M": obo("PATO:0000384")}  # male

# Electrode locations and the `region` of the units table: the lab's brain region labels
REGIONS = {"CA1": obo("UBERON:0003881")}  # CA1 field of hippocampus

# `cell_type` of the units table: the putativeCellType labels of CellExplorer
CELL_TYPES = {
    "Pyramidal Cell": obo("CL:0000598"),  # pyramidal neuron
    "Narrow Interneuron": obo("CL:0000099"),  # interneuron
    "Wide Interneuron": obo("CL:0000099"),
}


def _add_column_terms(herd, column, terms: dict):
    for value in sorted(set(column.data[:])):
        if value in terms:
            entity_id, entity_uri = terms[value]
            herd.add_ref(container=column, key=value, entity_id=entity_id, entity_uri=entity_uri)


def add_external_resources(nwbfile: NWBFile):
    """Annotate the species, sex, electrode locations, unit regions and cell types of an NWB file before it is written."""
    herd = nwbfile.get_external_resources()
    subject = nwbfile.subject
    if subject is not None:
        for attribute, terms in (("species", SPECIES), ("sex", SEXES)):
            value = getattr(subject, attribute)
            if value in terms:
                entity_id, entity_uri = terms[value]
                herd.add_ref(container=subject, attribute=attribute, entity_id=entity_id, entity_uri=entity_uri)
    for group in nwbfile.electrode_groups.values():
        if group.location in REGIONS:
            entity_id, entity_uri = REGIONS[group.location]
            herd.add_ref(container=group, attribute="location", entity_id=entity_id, entity_uri=entity_uri)
    if nwbfile.electrodes is not None:
        _add_column_terms(herd, nwbfile.electrodes["location"], REGIONS)
    if nwbfile.units is not None:
        for name, terms in (("region", REGIONS), ("cell_type", CELL_TYPES)):
            if name in nwbfile.units.colnames:
                _add_column_terms(herd, nwbfile.units[name], terms)
