"""External resource (HERD) annotations for the Senzai conversion.

The terms are written to a HERD file next to the NWB file (``<name>.herd.zip``), which pynwb reads with
``NWBHDF5IO(path, "r", herd_path=...)``.
"""

import tempfile
import zipfile
from pathlib import Path

from pynwb import NWBHDF5IO
from pynwb.resources import HERD


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


def to_zip(herd: HERD, path: Path):
    """Write the HERD tables as tsv files at the top of a zip file.

    HERD.to_zip in HDMF 6.2 stores the tables under their absolute paths, which HERD.from_zip cannot read.
    """
    with tempfile.TemporaryDirectory() as directory, zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for table in herd.children:
            tsv = Path(directory) / f"{table.name}.tsv"
            table.to_dataframe().to_csv(tsv, sep="\t", index=False)
            archive.write(tsv, arcname=tsv.name)


def herd_path_for(nwbfile_path) -> Path:
    nwbfile_path = Path(nwbfile_path)
    return nwbfile_path.with_name(nwbfile_path.stem + ".herd.zip")


def _add_column_terms(herd: HERD, column, terms: dict):
    for value in sorted(set(column[:])):
        if value in terms:
            entity_id, entity_uri = terms[value]
            herd.add_ref(container=column, key=value, entity_id=entity_id, entity_uri=entity_uri)


def write_herd(nwbfile_path) -> Path:
    """Annotate the species, electrode locations, unit regions and cell types of a written file."""
    herd_path = herd_path_for(nwbfile_path)
    with NWBHDF5IO(str(nwbfile_path), "r") as io:
        nwbfile = io.read()
        herd = HERD()
        subject = nwbfile.subject
        if subject is not None and subject.species in SPECIES:
            entity_id, entity_uri = SPECIES[subject.species]
            herd.add_ref(container=subject, attribute="species", entity_id=entity_id, entity_uri=entity_uri)
        for group in nwbfile.electrode_groups.values():
            if group.location in LOCATIONS:
                entity_id, entity_uri = LOCATIONS[group.location]
                herd.add_ref(container=group, attribute="location", entity_id=entity_id, entity_uri=entity_uri)
        _add_column_terms(herd, nwbfile.electrodes["location"], LOCATIONS)
        if nwbfile.units is not None:
            for name, terms in (("region", REGIONS), ("cell_type", CELL_TYPES)):
                if name in nwbfile.units.colnames:
                    _add_column_terms(herd, nwbfile.units[name], terms)
        to_zip(herd, herd_path)
    return herd_path
