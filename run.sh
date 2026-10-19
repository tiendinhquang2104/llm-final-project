#!/usr/bin/env bash
set -e

# ==============================================================================
# LLM Grading Challenge Orchestration Entrypoint
# ==============================================================================

show_help() {
    echo "Usage: ./run.sh [OPTION]"
    echo "Options:"
    echo "  --prepare-data    Execute raw data preprocessing pipeline"
    echo "  --task1           Execute Task 1 inference / evaluation"
    echo "  --task1-finetune  Task 1 QLoRA system end-to-end on a CUDA GPU (args: see scripts/run_task1_finetune.py -h)"
    echo "  --task1-compare   Score table: Task 1 API runs vs QLoRA adapter (gold validation)"
    echo "  --task2           Execute Task 2 training / inference"
    echo "  --task3           Execute Task 3 training / inference"
    echo "  --test            Run test suite"
    echo "  --submission      Generate final submission package"
    echo "  --help            Display this help message"
}

if [ "$#" -eq 0 ]; then
    show_help
    exit 0
fi

case "$1" in
    --prepare-data)
        echo "Preparing datasets..."
        python scripts/prepare_data.py
        ;;
    --task1)
        echo "Running Task 1..."
        python scripts/run_task1.py
        ;;
    --task1-finetune)
        shift
        python scripts/run_task1_finetune.py "$@"
        ;;
    --task1-compare)
        shift
        python scripts/compare_task1_methods.py "$@"
        ;;
    --task2)
        echo "Running Task 2..."
        python scripts/run_task2.py
        ;;
    --task3)
        echo "Running Task 3..."
        python scripts/run_task3.py
        ;;
    --test)
        echo "Running tests..."
        pytest tests/ -v
        ;;
    --submission)
        echo "Packaging submission..."
        python scripts/build_submission.py
        ;;
    --help)
        show_help
        ;;
    *)
        echo "Unknown option: $1"
        show_help
        exit 1
        ;;
esac
