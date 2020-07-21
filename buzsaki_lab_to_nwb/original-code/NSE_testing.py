import sys
sys.dont_write_bytecode=True

import spikeextractors as se

# resfile_path = 'D:\BuzsakiData\SenzaiY\YutaMouse41\YutaMouse41-150903\YutaMouse41-150903.res.1'
# clufile_path = 'D:\BuzsakiData\SenzaiY\YutaMouse41\YutaMouse41-150903\YutaMouse41-150903.clu.1'
#general_path = 'D:\BuzsakiData\SenzaiY\YutaMouse41\YutaMouse41-150903'
resfile_path = 'D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903/YutaMouse41-150903.res.1'
clufile_path = 'D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903/YutaMouse41-150903.clu.1'
general_path = 'D:/BuzsakiData/SenzaiY/YutaMouse41/YutaMouse41-150903'

NSE = se.NeuroscopeSortingExtractor(resfile_path=resfile_path,clufile_path=clufile_path)


# %%
NSE_single_test = se.NeuroscopeSortingExtractor(folder_path='D:/GitHub/tmp/tmpName')


# %%
NSE_all_shanks = se.NeuroscopeMultiSortingExtractor(folder_path=general_path)


# %%
test1 = NSE.get_unit_ids()
test2 = NSE.get_unit_spike_train(1)
test3 = NSE_single_test.get_unit_ids()
test4 = NSE_single_test.get_unit_spike_train(1)
test5 = NSE_all_shanks.get_unit_ids()
test6 = NSE_all_shanks.get_unit_spike_train(1)


# %%
test7 = se.MultiSortingExtractor(sortings=[NSE,NSE])


# %%
# celltype_names = ['temp1']
# descriptions = [
# {
#     'name': 'cell_type',
#     'description': 'name of cell type',
#     'data': celltype_names[0]},
# {
#     'name': 'global_id',
#     'description': 'global id for cell for entire experiment'},
# {
#     'name': 'shank_id',
#     'description': '0-indexed id of cluster of shank'},
# #             {
# #                'name': 'electrode_group',
# #                'description': 'the electrode group that each spike unit came from'},
# {
#    'name': 'max_electrode',
#    'description': 'electrode that has the maximum amplitude of the waveform'
# }
# ]

# temp = descriptions[0]
# NSE.set_unit_property(1, 'cell_type', temp)


# # %%
# temp2 = NSE.get_unit_property_names(1)
# temp3 = NSE.get_unit_property(1,temp2[0])


# # %% Assertion Testing - run line by line
# NSE_test = se.NeuroscopeSortingExtractor(resfile_path,clufile_path,general_path)
# NSE_test = se.NeuroscopeSortingExtractor(resfile_path=resfile_path,folder_path=general_path)
# NSE_test = se.NeuroscopeSortingExtractor(clufile_path=clufile_path,folder_path=general_path)

