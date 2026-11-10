"""External resource (HERD) annotations for the Senzai conversion.

The terms are stored in the NWB file's ``external_resources`` group (NWB 2.11), read back with
``nwbfile.external_resources.to_dataframe()``.
"""

from pynwb import NWBFile

from buzsaki_lab_to_nwb.utils.identifiers import add_identifier_refs


def obo(curie: str) -> tuple:
    """The CURIE and its OBO PURL."""
    return curie, "http://purl.obolibrary.org/obo/" + curie.replace(":", "_")


SPECIES = {"Mus musculus": obo("NCBITaxon:10090")}

# Allen Mouse Brain Atlas (CCF) structure names used for electrode locations
LOCATIONS = {"Hippocampal region": obo("MBA:1080")}

# `region` of the units table: the lab's unit summary codes
REGIONS = {"DG": obo("UBERON:0001885"), "CA3": obo("UBERON:0003883")}

# `cell_type` of the units table; labels with no matching Cell Ontology term ("unclassified", the
# positive-waveform units, "excitatory cell", "not in unit summary") are left out
CELL_TYPES = {
    "granule cell": obo("CL:2000089"),  # dentate gyrus granule cell
    "mossy cell": obo("CL:0020069"),  # hilar mossy cell
    "CA3 pyramidal cell": obo("CL:0020068"),
    "optogenetically tagged SST interneuron": obo("CL:4023017"),  # sst GABAergic interneuron
    "narrow-waveform interneuron": obo("CL:0000099"),
    "wide-waveform interneuron (narrower)": obo("CL:0000099"),
    "wide-waveform interneuron (wider)": obo("CL:0000099"),
}


def _add_column_terms(herd, column, terms: dict):
    for value in sorted(set(column.data[:])):
        if value in terms:
            entity_id, entity_uri = terms[value]
            herd.add_ref(container=column, key=value, entity_id=entity_id, entity_uri=entity_uri)


def add_external_resources(nwbfile: NWBFile):
    """Annotate the species, electrode locations, unit regions and cell types of an NWB file before it is written."""
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
    if nwbfile.units is not None:
        for name, terms in (("region", REGIONS), ("cell_type", CELL_TYPES)):
            if name in nwbfile.units.colnames:
                _add_column_terms(herd, nwbfile.units[name], terms)
