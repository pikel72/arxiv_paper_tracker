#!/usr/bin/env python3

import datetime
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import main


class DummyAuthor:
    def __init__(self, name):
        self.name = name


class DummyPaper:
    def __init__(self, title):
        self.title = title
        self.authors = [DummyAuthor("Tester")]
        self.summary = "abstract"
        self.categories = ["math.AP"]
        self.entry_id = f"https://arxiv.org/abs/{title}"
        self.published = datetime.datetime(2026, 5, 5)

    def get_short_id(self):
        return self.title.replace(" ", "_")


def test_batch_mode_checkpoints_completed_future_before_slow_future():
    papers = [DummyPaper("slow"), DummyPaper("fast")]
    checkpoint_sizes = []

    def fake_process(paper, index, total, thinking_mode=None):
        if paper.title == "slow":
            time.sleep(0.2)
        return 0, (paper, "reason", "**中文标题**: title")

    def fake_write(priority, secondary, irrelevant, filename=None, run_meta=None):
        if filename == "arxiv_analysis_checkpoint.md":
            checkpoint_sizes.append(len(irrelevant))
        return Path(tmpdir) / "daily.md"

    with TemporaryDirectory() as tmpdir:
        with patch.object(sys, "argv", ["main.py"]), patch.object(main, "configure_logging"), patch.object(
            main, "get_recent_papers", return_value=papers
        ), patch.object(main, "process_single_paper_task", side_effect=fake_process), patch.object(
            main, "write_to_conclusion", side_effect=fake_write
        ), patch.object(
            main, "format_email_content", return_value="email"
        ), patch.object(
            main, "send_email", return_value=True
        ), patch.object(
            main, "MAX_THREADS", 2
        ), patch.object(
            main, "DAILY_RUN_BUDGET_SECONDS", 0
        ):
            main.main()

    assert checkpoint_sizes
    assert checkpoint_sizes[0] == 1


if __name__ == "__main__":
    test_batch_mode_checkpoints_completed_future_before_slow_future()
    print("batch resilience tests passed")
