import os
import logging
import pandas as pd
from django.conf import settings
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

logger = logging.getLogger(__name__)


def get_spark_session():
    """Create or retrieve a SparkSession."""

    return (
        SparkSession.builder
        .appName("csv-pattern-replace")
        .master("local[*]")
        .config("spark.ui.enabled", "false")
        .config("spark.sql.shuffle.partitions", "8")
        .config("spark.driver.memory", "2g")
        .getOrCreate()
    )


def run_replacement(
    file_path: str,
    mime_type: str,
    target_columns: list[str],
    regex_pattern: str,
    replacement: str,
    job_id: str,
    progress_callback,
) -> str:
    """Spark transformation."""

    spark = get_spark_session()
    progress_callback(10)

    # Read 
    df = _read_file(spark, file_path, mime_type)
    progress_callback(30)

    # Repartition for parallelism
    num_partitions = (os.cpu_count() or 4) * 2
    df = df.repartition(num_partitions)

    # Transform
    # Apply regexp_replace to each target column
    for col in target_columns:
        if col in df.columns:
            df = df.withColumn(
                col,
                F.regexp_replace(F.col(col).cast("string"), regex_pattern, replacement)
            )
        else:
            logger.warning(f"Column '{col}' not found in DataFrame, skipping.")

    progress_callback(70)

    # Write
    output_path = _write_result(df, job_id)
    progress_callback(90)

    spark.catalog.clearCache()

    return output_path


def _read_file(spark, file_path: str, mime_type: str):
    """Read CSV or Excel into a Spark DataFrame."""
    if mime_type in (
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ):
        # convert via pandas 
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


def _write_result(df, job_id: str) -> str:
    """
    Write the result DataFrame to Parquet.
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