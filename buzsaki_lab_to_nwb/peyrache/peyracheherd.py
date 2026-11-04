"""External resource (HERD) annotations for the Peyrache conversion.

The terms are stored in the NWB file's ``external_resources`` group (NWB 2.11), read back with
``nwbfile.external_resources.to_dataframe()``. Every ID was checked on the EBI Ontology Lookup Service.
"""

from pynwb import NWBFile

from buzsaki_lab_to_nwb.utils.identifiers import add_identifier_refs


def obo(curie: str) -> tuple:
    """The CURIE and its OBO PURL."""
    return curie, "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


SPECIES = {"Mus musculus": obo("NCBITaxon:10090")}

# Electrode locations and the `region` of the units table: Allen Mouse Brain Atlas structure names
# (peyracheutils.REGION_LOCATIONS), annotated with their UBERON terms
LOCATIONS = {
    "Anterodorsal nucleus": obo("UBERON:0002679"),
    "Postsubiculum": obo("UBERON:0035971"),
    "Field CA1": obo("UBERON:0003881"),
    "Prelimbic area": obo("UBERON:8440032"),  # prelimbic area
    "Reticular nucleus of the thalamus": obo("UBERON:0001903"),
}
# The source gives cell types only as the 2019 buzcode putative classes (pE/pI), which are not annotated


def _add_column_terms(herd, column, terms: dict):
    for value in sorted(set(column.data[:])):
        if value in terms:
            entity_id, entity_uri = terms[value]
            herd.add_ref(container=column, key=value, entity_id=entity_id, entity_uri=entity_uri)


def add_external_resources(nwbfile: NWBFile):
    """Annotate the species, electrode locations and unit regions of an NWB file before it is written."""
    herd = nwbfile.get_external_resources()
    add_identifier_refs(nwbfile)
    subject = nwbfile.subject
    if subject is not None and subject.species in SPECIES:
        entity_id, entity_uri = SPECIES[subject.species]
        herd.add_ref(container=subject, attribute="species", entity_id=entity_id, entity_uri=entity_uri)
    for group in nwbfile.electrode_groups.values():
        if group.location in LOCATIONS:
            entity_id, entity_uri = LOCATIONS[group.location]
            herd.add_ref(container=group, attribute="location", entity_id=entity_id, entity_uri=entity_uri)
    if nwbfile.electrodes is not None:
        _add_column_terms(herd, nwbfile.electrodes["location"], LOCATIONS)
    if nwbfile.units is not None and "region" in nwbfile.units.colnames:
        _add_column_terms(herd, nwbfile.units["region"], LOCATIONS)
