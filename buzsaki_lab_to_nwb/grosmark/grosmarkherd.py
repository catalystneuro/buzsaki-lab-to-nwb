"""External resource (HERD) annotations for the Grosmark conversion.

The terms are stored in the NWB file's ``external_resources`` group (NWB 2.11), read back with
``nwbfile.external_resources.to_dataframe()``. Each term was checked on the EBI Ontology Lookup Service.
"""

from pynwb import NWBFile

from buzsaki_lab_to_nwb.utils.identifiers import add_identifier_refs


def obo(curie: str) -> tuple:
    """The CURIE and its OBO PURL."""
    return curie, "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


SPECIES = {"Rattus norvegicus": obo("NCBITaxon:10116")}
SEXES = {"M": obo("PATO:0000384")}  # male

# Electrode locations; the extra sites above CA1 have location "unknown" and no term
LOCATIONS = {"CA1 field of hippocampus": obo("UBERON:0003881")}

# `cell_type` of the units table
CELL_TYPES = {
    "pyramidal cell": obo("CL:0000598"),  # pyramidal neuron
    "interneuron": obo("CL:0000099"),
}


def _add_column_terms(herd, column, terms: dict):
    for value in sorted(set(column.data[:])):
        if value in terms:
            entity_id, entity_uri = terms[value]
            herd.add_ref(container=column, key=value, entity_id=entity_id, entity_uri=entity_uri)


def add_external_resources(nwbfile: NWBFile):
    """Annotate the species, sex, electrode locations and cell types of an NWB file before it is written."""
    herd = nwbfile.get_external_resources()
    add_identifier_refs(nwbfile)
    subject = nwbfile.subject
    if subject is not None:
        for attribute, terms in (("species", SPECIES), ("sex", SEXES)):
            value = getattr(subject, attribute)
            if value in terms:
                entity_id, entity_uri = terms[value]
                herd.add_ref(container=subject, attribute=attribute, entity_id=entity_id, entity_uri=entity_uri)
    for group in nwbfile.electrode_groups.values():
        if group.location in LOCATIONS:
            entity_id, entity_uri = LOCATIONS[group.location]
            herd.add_ref(container=group, attribute="location", entity_id=entity_id, entity_uri=entity_uri)
    if nwbfile.electrodes is not None:
        _add_column_terms(herd, nwbfile.electrodes["location"], LOCATIONS)
    if nwbfile.units is not None and "cell_type" in nwbfile.units.colnames:
        _add_column_terms(herd, nwbfile.units["cell_type"], CELL_TYPES)
