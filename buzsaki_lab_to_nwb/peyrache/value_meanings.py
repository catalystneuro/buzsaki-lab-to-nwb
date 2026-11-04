"""MeaningsTables, with HED, for the categorical columns in value_meanings.yaml (from the nwb-convert skill)."""

from hdmf.common import DynamicTable, MeaningsTable, VectorIndex
from pynwb import NWBFile


def add_value_meanings(nwbfile: NWBFile, annotations: dict) -> None:
    """Write the meanings and HED in value_meanings.yaml into the file as MeaningsTables."""
    tables = [
        neurodata_object
        for neurodata_object in nwbfile.all_children()
        if isinstance(neurodata_object, DynamicTable) and not isinstance(neurodata_object, MeaningsTable)
    ]
    wrote_hed = False
    for table_name, columns in (annotations.get("tables") or {}).items():
        for table in (table for table in tables if table.name == table_name):
            for column_name, entries in (columns or {}).items():
                if column_name not in table.colnames or not entries:
                    continue
                column = table[column_name]
                if isinstance(column, VectorIndex):  # a ragged column: the meanings describe its values
                    column = column.target
                # A NeuroConv events interface may already have written meanings for this column
                meanings_table = table.get_meanings_for_column(column_name)
                is_new = meanings_table is None
                if is_new:
                    meanings_table = MeaningsTable(target=column)
                described = list(meanings_table["value"].data)
                if "HED" not in meanings_table.colnames and any(entry.get("hed") for entry in entries.values()):
                    from ndx_hed import HedTags

                    meanings_table.add_column(
                        name="HED",  # the name ndx-hed requires
                        description="HED annotation of each value.",
                        data=[(entries.get(value) or {}).get("hed", "") for value in described],
                        col_cls=HedTags,
                    )
                has_hed = "HED" in meanings_table.colnames
                wrote_hed = wrote_hed or has_hed
                for value, entry in entries.items():
                    if value in described:
                        continue
                    row = dict(value=value, meaning=entry["meaning"])
                    if has_hed:
                        row["HED"] = entry.get("hed", "")  # empty means no annotation
                    meanings_table.add_row(**row)
                if is_new:
                    table.add_meanings_table(meanings_table)

    if wrote_hed and "hed_schema" not in nwbfile.lab_meta_data:
        from ndx_hed import HedLabMetaData

        # The file records the schema version its annotations were validated against
        nwbfile.add_lab_meta_data(HedLabMetaData(hed_schema_version=annotations["hed_schema_version"]))
