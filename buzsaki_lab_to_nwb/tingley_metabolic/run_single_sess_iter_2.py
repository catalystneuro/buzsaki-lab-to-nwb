import os

for _ in range(30):
    try:
        os.system("python fully_automated_single_session_2.py")
    except KeyboardInterrupt:
        break
