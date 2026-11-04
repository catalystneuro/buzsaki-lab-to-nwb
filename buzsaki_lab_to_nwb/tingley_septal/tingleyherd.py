"""External resource (HERD) annotations for the Tingley conversion.

The terms are stored in the NWB file's ``external_resources`` group (NWB 2.11), read back with
``nwbfile.external_resources.to_dataframe()``. Each term was checked on the EBI Ontology Lookup Service.
"""

from pynwb import NWBFile


def obo(curie: str) -> tuple:
    """The CURIE and its OBO PURL."""
    return curie, "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


SPECIES = {"Rattus norvegicus": obo("NCBITaxon:10116")}
SEXES = {"M": obo("PATO:0000384"), "F": obo("PATO:0000383")}  # the source gives no sex per rat, so none is written

# Electrode locations (REGION_NAMES of tingleyutils); "unknown" has no term
LOCATIONS = {
    "lateral septal nucleus": obo("UBERON:0002667"),
    "hippocampal formation": obo("UBERON:0002421"),
    "CA1 field of hippocampus": obo("UBERON:0003881"),
    "CA3 field of hippocampus": obo("UBERON:0003883"),
    "posterior parietal cortex": obo("UBERON:0034889"),
    "anterior cingulate cortex": obo("UBERON:0009835"),
    "corpus callosum": obo("UBERON:0002336"),
    "medial septal nucleus": obo("UBERON:0001877"),
    "septofimbrial nucleus": obo("UBERON:0001878"),
}

# `region` of the electrodes and units tables: the lab's labels
REGIONS = {
    "ls": LOCATIONS["lateral septal nucleus"],
    "hpc": LOCATIONS["hippocampal formation"],
    "ca1": LOCATIONS["CA1 field of hippocampus"],
    "ca3": LOCATIONS["CA3 field of hippocampus"],
    "ppc": LOCATIONS["posterior parietal cortex"],
    "acg": LOCATIONS["anterior cingulate cortex"],
    "cc": LOCATIONS["corpus callosum"],
    "ms": LOCATIONS["medial septal nucleus"],
    "sFi": LOCATIONS["septofimbrial nucleus"],
}


def _add_column_terms(herd, column, terms: dict):
    for value in sorted(set(column.data[:])):
        if value in terms:
            entity_id, entity_uri = terms[value]
            herd.add_ref(container=column, key=value, entity_id=entity_id, entity_uri=entity_uri)


def add_external_resources(nwbfile: NWBFile):
    """Annotate the species, sex, electrode locations and regions of an NWB file before it is written."""
    herd = nwbfile.get_external_resources()
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
        _add_column_terms(herd, nwbfile.electrodes["region"], REGIONS)
    if nwbfile.units is not None and "region" in nwbfile.units.colnames:
        _add_column_terms(herd, nwbfile.units["region"], REGIONS)
