# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.


import os

from airflow import models
from airflow.providers.microsoft.azure.operators.azure_batch import AzureBatchOperator
from airflow.utils.dates import days_ago

KUSTO_CLUSTER_URL = os.environ.get("KUSTO_CLUSTER_URL", "demo-cluster")
DATABASE_NAME = os.environ.get("DATABASE_NAME", "demo-database")

with models.DAG(
    "example_azure_batch_job",
    start_date=days_ago(1),
    schedule_interval=None,
    tags=['example'],
) as dag:

    batch_pool_id = ""
    batch_pool_vm_size = ""
    batch_job_id = ''
    batch_task_command_line = ''
    batch_task_id = ''

    # [START azure_batch_job_operator_howto_guide__]
    batch_job = AzureBatchOperator(
        batch_pool_id=batch_pool_id,
        batch_pool_vm_size=batch_pool_vm_size,
        batch_job_id=batch_job_id,
        batch_task_id=batch_task_id,
        batch_task_command_line=batch_task_command_line,
    )
    # [END azure_batch_job_operator_howto_guide__]
