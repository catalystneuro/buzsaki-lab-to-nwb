"""ORCID and ROR identifiers for the experimenters and institutions of the Buzsaki lab conversions.

The ORCIDs are those of the dandisets' contributor metadata on DANDI (checked against the ORCID registry); an
experimenter or institution that is not listed here gets no reference.
"""

from pynwb import NWBFile

ORCIDS = {
    "Senzai, Yuta": "0000-0002-2990-9889",
    "Watson, Brendon O.": "0000-0002-9940-4579",
    "Grosmark, Andres D.": "0000-0002-7185-3946",
    "Peyrache, Adrien": "0000-0001-9708-309X",
    "Lacroix, Marie M.": "0000-0001-9472-5106",
    "Petersen, Peter C.": "0000-0002-2092-4791",
    "Girardeau, Gabrielle": "0000-0002-5265-9697",
    "Fujisawa, Shigeyoshi": "0000-0003-3963-4281",
    "Tingley, David": "0000-0003-4263-0476",
    "Huszár, Roman": "0000-0002-8426-8308",
    "Zhang, Yunchang": "0000-0003-3294-7373",
    "Blockus, Heike": "0000-0001-5274-2805",
    "Buzsáki, György": "0000-0002-3100-4800",
    "Valero, Manuel": "0000-0001-7860-577X",
    "Zutshi, Ipshita": "0000-0001-8180-0816",
    "Yoon, Euisik": "0000-0002-2127-1200",
}

RORS = {
    "New York University": "0190ak572",
    "Rutgers, The State University of New Jersey": "05vt9qd57",
}


def add_identifier_refs(nwbfile: NWBFile):
    """Link the file's experimenters to their ORCID and its institution to its ROR, in the file's HERD."""
    herd = nwbfile.get_external_resources()
    for name in nwbfile.experimenter or ():
        if name in ORCIDS:
            orcid = ORCIDS[name]
            herd.add_ref(
                container=nwbfile,
                attribute="experimenter",
                key=name,
                entity_id=f"ORCID:{orcid}",
                entity_uri=f"https://orcid.org/{orcid}",
            )
    if nwbfile.institution in RORS:
        ror = RORS[nwbfile.institution]
        herd.add_ref(
            container=nwbfile, attribute="institution", entity_id=f"ROR:{ror}", entity_uri=f"https://ror.org/{ror}"
        )
