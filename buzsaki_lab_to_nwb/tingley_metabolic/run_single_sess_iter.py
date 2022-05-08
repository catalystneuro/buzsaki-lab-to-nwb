from nwb_conversion_tools.tools.data_transfers import deploy_process

for _ in range(2):
    res = deploy_process(command="python fully_automated_single_session.py", catch_output=True)
