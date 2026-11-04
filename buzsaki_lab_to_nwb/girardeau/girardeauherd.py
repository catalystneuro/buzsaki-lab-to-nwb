"""External resource (HERD) annotations for the Girardeau conversion.

The terms are stored in the NWB file's ``external_resources`` group (NWB 2.11), read back with
``nwbfile.external_resources.to_dataframe()``. Every ID was checked on the EBI Ontology Lookup Service
(https://www.ebi.ac.uk/ols4).
"""

from pynwb import NWBFile

from buzsaki_lab_to_nwb.utils.identifiers import add_identifier_refs


def obo(curie: str) -> tuple:
    """The CURIE and its OBO PURL."""
    return curie, "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


SPECIES = {"Rattus norvegicus": obo("NCBITaxon:10116")}
SEX = {"M": obo("PATO:0000384"), "F": obo("PATO:0000383")}

# The lab's region codes (girardeauutils.REGION_CODES), keyed by the location written for them, where one UBERON term
# matches the code. Left out: den, ven, blv, bmp and plc01, which have no UBERON term of their own (only a broader one).
LOCATIONS = {
    "hippocampus": obo("UBERON:0002421"),  # hippocampal formation, exact synonym "hippocampus"
    "basolateral amygdaloid nucleus": obo(
        "UBERON:0002887"
    ),  # basal amygdaloid nucleus, synonym "basolateral amygdaloid nucleus"
    "lateral amygdaloid nucleus, dorsolateral part": obo("UBERON:0023415"),
    "central amygdaloid nucleus": obo("UBERON:0002883"),
    "piriform cortex": obo("UBERON:0004725"),
    "caudate putamen": obo("UBERON:0005383"),  # caudate-putamen
}
REGIONS = {
    "hpc": LOCATIONS["hippocampus"],
    "bla": LOCATIONS["basolateral amygdaloid nucleus"],
    "ladl": LOCATIONS["lateral amygdaloid nucleus, dorsolateral part"],
    "cen": LOCATIONS["central amygdaloid nucleus"],
    "pir": LOCATIONS["piriform cortex"],
    "cpu": LOCATIONS["caudate putamen"],
}


def _add_column_terms(herd, column, terms: dict):
    for value in sorted(set(column.data[:])):
        if value in terms:
            entity_id, entity_uri = terms[value]
            herd.add_ref(container=column, key=value, entity_id=entity_id, entity_uri=entity_uri)


def add_external_resources(nwbfile: NWBFile):
    """Annotate the species, sex, electrode locations and regions of an NWB file before it is written."""
    herd = nwbfile.get_external_resources()
    add_identifier_refs(nwbfile)
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
        _add_column_terms(herd, nwbfile.electrodes["region"], REGIONS)
    if nwbfile.units is not None and "region" in nwbfile.units.colnames:
        _add_column_terms(herd, nwbfile.units["region"], REGIONS)
