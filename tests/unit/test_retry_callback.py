"""Unit tests for record_retry_callback retry counting semantics.

Verifies that the before_sleep callback correctly counts every retry attempt
for RETRIES_MAX=2 (expect 1 counted) and RETRIES_MAX=8 (expect 7 counted).
Tests are isolated — they do not import the FastAPI app and do not require
Prometheus to be running.
"""
import pytest
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type,
    RetryCallState,
)


def make_counting_callback():
    """Return a (callback, counter_list) pair.  Each before_sleep invocation
    appends the attempt_number to counter_list if attempt_number >= 1."""
    counted: list[int] = []

    def callback(retry_state: RetryCallState) -> None:
        if retry_state.attempt_number >= 1:
            counted.append(retry_state.attempt_number)

    return callback, counted


def exhausting_func_factory(max_retries: int, callback) -> callable:
    """Return a function that always raises ValueError and retries max_retries times."""
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_fixed(0),              # no sleep in tests
        retry=retry_if_exception_type(ValueError),
        before_sleep=callback,
        reraise=True,
    )
    def _always_fails():
        raise ValueError("simulated downstream timeout")

    return _always_fails


class TestRetryCallbackCounting:
    """Verify retry counter semantics for the corrected >= 1 guard."""

    def test_retries_max_2_counts_exactly_1_retry(self):
        """With RETRIES_MAX=2: attempt 1 fails (callback fires, attempt_number=1),
        attempt 2 fails (stop triggered, before_sleep does NOT fire again).
        Expected: 1 retry counted."""
        cb, counted = make_counting_callback()
        fn = exhausting_func_factory(max_retries=2, callback=cb)
        with pytest.raises(ValueError):
            fn()
        assert len(counted) == 1, f"Expected 1 retry counted, got {len(counted)}: {counted}"
        assert counted[0] == 1

    def test_retries_max_8_counts_exactly_7_retries(self):
        """With RETRIES_MAX=8: attempts 1-7 each fail and trigger a sleep (callback fires),
        attempt 8 fails and stop_after_attempt triggers without sleeping.
        Expected: 7 retries counted (attempt_numbers 1 through 7)."""
        cb, counted = make_counting_callback()
        fn = exhausting_func_factory(max_retries=8, callback=cb)
        with pytest.raises(ValueError):
            fn()
        assert len(counted) == 7, f"Expected 7 retries counted, got {len(counted)}: {counted}"
        assert counted == list(range(1, 8))

    def test_retries_max_1_counts_zero_retries(self):
        """With RETRIES_MAX=1: only one attempt, no retry ever scheduled.
        before_sleep never fires.  Expected: 0 retries counted."""
        cb, counted = make_counting_callback()
        fn = exhausting_func_factory(max_retries=1, callback=cb)
        with pytest.raises(ValueError):
            fn()
        assert len(counted) == 0, f"Expected 0 retries counted, got {len(counted)}: {counted}"

    def test_retries_max_3_counts_exactly_2_retries(self):
        """With RETRIES_MAX=3: before_sleep fires for attempts 1 and 2.
        Expected: 2 retries counted."""
        cb, counted = make_counting_callback()
        fn = exhausting_func_factory(max_retries=3, callback=cb)
        with pytest.raises(ValueError):
            fn()
        assert len(counted) == 2, f"Expected 2 retries counted, got {len(counted)}: {counted}"
        assert counted == [1, 2]

    def test_old_guard_gt1_would_miss_first_retry_for_retries_max_2(self):
        """Regression guard: the OLD implementation used attempt_number > 1.
        Confirm that with RETRIES_MAX=2 the old guard counted 0 (the bug)."""
        old_counted: list[int] = []

        def old_callback(retry_state: RetryCallState) -> None:
            if retry_state.attempt_number > 1:        # old buggy guard
                old_counted.append(retry_state.attempt_number)

        fn = exhausting_func_factory(max_retries=2, callback=old_callback)
        with pytest.raises(ValueError):
            fn()
        # This documents the BUG: old guard counted 0 retries with RETRIES_MAX=2
        assert len(old_counted) == 0, (
            "Regression: old > 1 guard should have counted 0 for RETRIES_MAX=2"
        )

    def test_old_guard_gt1_undercounted_for_retries_max_8(self):
        """Regression guard: old guard with RETRIES_MAX=8 counted 6, not 7."""
        old_counted: list[int] = []

        def old_callback(retry_state: RetryCallState) -> None:
            if retry_state.attempt_number > 1:        # old buggy guard
                old_counted.append(retry_state.attempt_number)

        fn = exhausting_func_factory(max_retries=8, callback=old_callback)
        with pytest.raises(ValueError):
            fn()
        # Documents the undercount: 6 instead of 7
        assert len(old_counted) == 6, (
            f"Regression: old > 1 guard should have counted 6 for RETRIES_MAX=8, got {len(old_counted)}"
        )
