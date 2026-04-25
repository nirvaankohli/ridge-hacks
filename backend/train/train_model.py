from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from train.data_pipeline import HistoricalDatasetBuilder
from train.modeling import train_risk_model

Debug = True

def print_if_debug(message: str, debug: bool) -> None:

    if debug:

        print(message)

async def run(start_date: str, end_date: str, output_dir: Path) -> None:

    print_if_debug("starting run function - now gonna build dataset", Debug)

    builder = HistoricalDatasetBuilder()

    print_if_debug("done initializing builder, now gonna fetch bundle", Debug)

    bundle = await builder.fetch_bundle(start_date, end_date)

    print_if_debug("got bundle, now gonna build dataset", Debug)

    dataset = builder.build_dataset(bundle, start_date, end_date)

    print_if_debug("built dataset, now gonna persist it", Debug)

    dataset_path = output_dir / "datasets" / "solar_storm_training_data.csv"

    print_if_debug(f"dataset path is {dataset_path}", Debug)

    builder.persist_dataset(dataset, dataset_path)

    print_if_debug("persisted dataset, now gonna train model", Debug)

    result = train_risk_model(dataset, output_dir / "artifacts")

    print_if_debug("trained model, now gonna print results", Debug)

    print(f"dataset_rows={len(dataset)}")
    print(f"expanded_training_rows={result.row_count}")
    print(f"artifact={result.artifact_path}")
    print(f"metrics={result.metrics_path}")
    print(f"labels={','.join(result.class_labels)}")


def main() -> None:

    today = datetime.now(UTC).date()
    default_start = (today - timedelta(days=365)).isoformat()

    print("got past date parsing") if Debug else None

    parser = argparse.ArgumentParser(description="Train the solar storm risk model.")
    parser.add_argument("--start-date", default=default_start)
    parser.add_argument("--end-date", default=today.isoformat())
    parser.add_argument("--output-dir", default="train")
    args = parser.parse_args()

    asyncio.run(run(args.start_date, args.end_date, Path(args.output_dir)))


if __name__ == "__main__":
    main()
