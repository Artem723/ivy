'''
Utilities for managing vehicle count jobs.
'''

import os
import uuid
import time

job_ids = dict()

def get_job_id(input_file_path):
    '''
    Fetch job id or create new if one doesn't already exist.
    '''
    file_name = os.path.basename(input_file_path)
    if os.getenv('JOB_ID') is None:
        # os.environ['JOB_ID'] = 'job_' + str(int(time.time())) + '_' + uuid.uuid4().hex
        os.environ['JOB_ID'] = 'job'
    if file_name not in job_ids:
        job_ids[file_name] = 'job_' + file_name + time.strftime("%Y-%m-%d %H:%M:%S") + '_' + uuid.uuid4().hex
    
    return job_ids[file_name]
