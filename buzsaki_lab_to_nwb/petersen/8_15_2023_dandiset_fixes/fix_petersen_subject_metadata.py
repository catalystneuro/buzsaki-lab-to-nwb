from pathlib import Path

import h5py

dandi_base = Path("E:/Buzsaki/PetersenP/000059")
all_dandi_nwbfiles = list(dandi_base.rglob("**/*.nwb"))


for dandi_file in all_dandi_nwbfiles:
    try:
        with h5py.File(name=dandi_file, mode="a") as file:
            pass
    except:
        continue

    with h5py.File(name=dandi_file, mode="a") as file:
        file["general"]["subject"]["age"][()] = b"P3M/P6M"  # All subjects same age range
        file["general"]["subject"]["sex"][()] = b"M"  # All subjects Male
        file["general"]["subject"]["species"][()] = b"Rattus norvegicus"
