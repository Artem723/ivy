'''
Utilities for managing vehicle count jobs.
'''

import os
import uuid
import time

job_ids = dict()

def get_job_id(input_file_name):
    '''
    Fetch job id or create new if one doesn't already exist.
    '''
    if os.getenv('JOB_ID') is None:
        # os.environ['JOB_ID'] = 'job_' + str(int(time.time())) + '_' + uuid.uuid4().hex
        os.environ['JOB_ID'] = 'job_' + input_file_name + time.strftime("%Y-%m-%d %H:%M:%S") + '_' + uuid.uuid4().hex
    if input_file_name not in job_ids:
        job_ids[input_file_name] = 'job_' + input_file_name + time.strftime("%Y-%m-%d %H:%M:%S") + '_' + uuid.uuid4().hex
    
    return job_ids[input_file_name]
