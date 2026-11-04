"""External resource (HERD) annotations for the Fujisawa conversion, stored in the file's `external_resources` group."""

from pynwb import NWBFile


def obo(curie: str) -> tuple:
    """The CURIE and its OBO PURL."""
    return curie, "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


SPECIES = {"Rattus norvegicus": obo("NCBITaxon:10116")}
SEX = {"M": obo("PATO:0000384")}
LOCATIONS = {
    "medial prefrontal cortex": obo("UBERON:4450000"),
    "CA1 field of hippocampus": obo("UBERON:0003881"),
}
REGIONS = {"mPFC": obo("UBERON:4450000"), "CA1": obo("UBERON:0003881")}
CELL_TYPES = {"pyramidal cell": obo("CL:0000598"), "interneuron": obo("CL:0000099")}


def _add_column_terms(herd, column, terms: dict):
    for value in sorted(set(column.data[:])):
        if value in terms:
            entity_id, entity_uri = terms[value]
            herd.add_ref(container=column, key=value, entity_id=entity_id, entity_uri=entity_uri)


def add_external_resources(nwbfile: NWBFile):
    """Annotate the species, sex, electrode locations, unit regions and cell types before the file is written."""
    herd = nwbfile.get_external_resources()
    subject = nwbfile.subject
    if subject is not None:
        for attribute, terms in (("species", SPECIES), ("sex", SEX)):
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
    if nwbfile.units is not None:
        for name, terms in (("region", REGIONS), ("cell_type", CELL_TYPES)):
            if name in nwbfile.units.colnames:
                _add_column_terms(herd, nwbfile.units[name], terms)
