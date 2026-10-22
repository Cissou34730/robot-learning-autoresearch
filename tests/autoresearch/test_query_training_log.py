"""Schema-6 training-log lookup uses operation identity."""

from __future__ import annotations

import pytest

from runner import query_training_log


def test_training_log_cli_rejects_non_operation_identity():
    with pytest.raises(SystemExit):
        query_training_log.parse_arguments(
            ["--operation", "2", "--from-step", "0", "--to-step", "10"]
        )
