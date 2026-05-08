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
        ):
            main.main()

    assert checkpoint_sizes
    assert checkpoint_sizes[0] == 1


def test_batch_mode_ignores_empty_wait_poll_and_keeps_collecting():
    papers = [DummyPaper("slow one"), DummyPaper("slow two")]
    final_meta = []
    original_wait = main.wait
    wait_calls = {"count": 0}

    def fake_process(paper, index, total, thinking_mode=None):
        time.sleep(0.1)
        return 0, (paper, "reason", "**中文标题**: title")

    def fake_wait(fs, timeout=None, return_when=None):
        wait_calls["count"] += 1
        if wait_calls["count"] == 1:
            return set(), set(fs)
        return original_wait(fs, timeout=1, return_when=return_when)

    def fake_write(priority, secondary, irrelevant, filename=None, run_meta=None):
        if filename is None and run_meta:
            final_meta.append(run_meta.copy())
        return Path(tmpdir) / "daily.md"

    with TemporaryDirectory() as tmpdir:
        with patch.object(sys, "argv", ["main.py"]), patch.object(main, "configure_logging"), patch.object(
            main, "get_recent_papers", return_value=papers
        ), patch.object(main, "process_single_paper_task", side_effect=fake_process), patch.object(
            main, "wait", side_effect=fake_wait
        ), patch.object(
            main, "write_to_conclusion", side_effect=fake_write
        ), patch.object(
            main, "format_email_content", return_value="email"
        ), patch.object(
            main, "send_email", return_value=True
        ), patch.object(
            main, "MAX_THREADS", 2
        ):
            main.main()

    assert final_meta
    assert final_meta[-1]["completed_papers"] == 2
    assert final_meta[-1]["skipped_papers"] == 0
    assert final_meta[-1]["partial_run"] is False


if __name__ == "__main__":
    test_batch_mode_checkpoints_completed_future_before_slow_future()
    test_batch_mode_ignores_empty_wait_poll_and_keeps_collecting()
    print("batch resilience tests passed")
