"""
DAG that runs dbt models on a schedule.
In dev: every 5 minutes (simulates daily batch without waiting 24h).
In prod: daily at 6 AM UTC.
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "flowforge",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="dbt_cold_path",
    default_args=default_args,
    description="Run dbt models to produce enriched marts",
    schedule_interval="*/5 * * * *",  # Every 5 min in dev. Change to "0 6 * * *" in prod.
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["dbt", "cold-path"],
) as dag:

    dbt_seed = BashOperator(
        task_id="dbt_seed",
        bash_command="cd /opt/airflow/dbt && dbt seed --profiles-dir .",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt && dbt run --profiles-dir .",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt && dbt test --profiles-dir .",
    )

    dbt_seed >> dbt_run >> dbt_test
