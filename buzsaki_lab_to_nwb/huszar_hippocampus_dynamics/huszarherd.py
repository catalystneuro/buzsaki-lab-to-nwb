"""External resource (HERD) annotations for the Huszar conversion (DANDI:000552).

The terms are stored in the NWB file's ``external_resources`` group (NWB 2.11), read back with
``nwbfile.external_resources.to_dataframe()``. Every ID was checked on OLS.
"""

from pynwb import NWBFile

from buzsaki_lab_to_nwb.utils.identifiers import add_identifier_refs


def obo(curie: str) -> tuple:
    """The CURIE and its OBO PURL."""
    return curie, "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


SPECIES = {"Mus musculus": obo("NCBITaxon:10090")}
SEX = {"M": obo("PATO:0000384"), "F": obo("PATO:0000383")}
LOCATIONS = {"CA1": obo("UBERON:0003881")}  # CA1 field of hippocampus

# `putative_cell_type` of the units table (CellExplorer labels)
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
    """Annotate the species, sex, electrode locations and unit cell types of an NWB file before it is written."""
    herd = nwbfile.get_external_resources()
    add_identifier_refs(nwbfile)
    subject = nwbfile.subject
    if subject is not None:
        if subject.species in SPECIES:
            entity_id, entity_uri = SPECIES[subject.species]
            herd.add_ref(container=subject, attribute="species", entity_id=entity_id, entity_uri=entity_uri)
        if subject.sex in SEX:
            entity_id, entity_uri = SEX[subject.sex]
            herd.add_ref(container=subject, attribute="sex", entity_id=entity_id, entity_uri=entity_uri)
    for group in nwbfile.electrode_groups.values():
        if group.location in LOCATIONS:
            entity_id, entity_uri = LOCATIONS[group.location]
            herd.add_ref(container=group, attribute="location", entity_id=entity_id, entity_uri=entity_uri)
    if nwbfile.electrodes is not None:
        _add_column_terms(herd, nwbfile.electrodes["location"], LOCATIONS)
    if nwbfile.units is not None and "putative_cell_type" in nwbfile.units.colnames:
        _add_column_terms(herd, nwbfile.units["putative_cell_type"], CELL_TYPES)
