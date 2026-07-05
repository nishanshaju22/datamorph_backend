import os
import re
import pandas as pd
from django.conf import settings
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

USE_SPARK = os.environ.get("USE_SPARK", "true").lower() == "true"


def run_replacement(
    file_path: str,
    mime_type: str,
    target_columns: list[str],
    regex_pattern: str,
    replacement: str,
    job_id: str,
    progress_callback,
) -> str:
    if USE_SPARK:
        return _run_with_spark(
            file_path, mime_type, target_columns,
            regex_pattern, replacement, job_id, progress_callback
        )
    else:
        return _run_with_pandas(
            file_path, mime_type, target_columns,
            regex_pattern, replacement, job_id, progress_callback
        )


def get_spark_session():
    """
    Create or retrieve a SparkSession.
    """

    return (
        SparkSession.builder
        .appName("csv-pattern-replace")
        .master("local[*]")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )


def _run_with_spark(
    file_path, mime_type, target_columns,
    regex_pattern, replacement, job_id, progress_callback
):

    spark = get_spark_session()
    progress_callback(10)

    df = _read_file(spark, file_path, mime_type)
    progress_callback(30)

    # Repartition for parallelism across all cores
    num_partitions = (os.cpu_count() or 4) * 2
    df = df.repartition(num_partitions)

    for col_name in target_columns:
        if col_name in df.columns:
            # Capture all three values explicitly in local scope
            _col = col_name
            _pattern = regex_pattern
            _replace = replacement

            df = df.withColumn(
                _col,
                F.regexp_replace(F.col(_col).cast("string"), _pattern, _replace)
            )

    progress_callback(70)

    output_path = _write_result(df, job_id)
    progress_callback(90)

    spark.catalog.clearCache()
    return output_path

# Pandas engine — fallback
def _run_with_pandas(
    file_path, mime_type, target_columns,
    regex_pattern, replacement, job_id, progress_callback
):
    progress_callback(10)

    if mime_type in (
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path, dtype=str)

    progress_callback(30)

    compiled = re.compile(regex_pattern)

    for col_name in target_columns:
        if col_name in df.columns:
            # Capture values by default arg to avoid closure scoping bug
            df[col_name] = df[col_name].astype(str).apply(
                lambda val, c=compiled, r=replacement: re.sub(c, r, val)
            )

    progress_callback(70)

    output_path = _write_parquet_pandas(df, job_id)
    progress_callback(90)
    return output_path


# File readers
def _read_file(spark, file_path: str, mime_type: str):
    """Read CSV or Excel into a Spark DataFrame."""
    if mime_type in (
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        pdf = pd.read_excel(file_path)
        return spark.createDataFrame(pdf)
    else:
        return (
            spark.read
            .option("header", "true")
            .option("inferSchema", "false")
            .option("multiLine", "true")
            .option("escape", '"')
            .csv(file_path)
        )


# Writers
def _write_result(df, job_id: str) -> str:
    """
    Write Spark DataFrame to Parquet.
    """
    os.makedirs(settings.RESULTS_DIR, exist_ok=True)
    output_path = os.path.join(settings.RESULTS_DIR, job_id)

    (
        df.coalesce(1)
        .write
        .mode("overwrite")
        .parquet(output_path)
    )

    return output_path

def _write_parquet_pandas(df, job_id: str) -> str:
    """Write pandas DataFrame to Parquet."""
    os.makedirs(settings.RESULTS_DIR, exist_ok=True)
    output_path = os.path.join(settings.RESULTS_DIR, job_id)
    os.makedirs(output_path, exist_ok=True)
    df.to_parquet(os.path.join(output_path, "result.parquet"), index=False)
    return output_path