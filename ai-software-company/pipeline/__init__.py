"""Delivery loop: Code → Review → Test → Deploy → Monitor → Linear tasks."""

__all__ = ["run_pipeline"]


def run_pipeline(*args, **kwargs):
    from pipeline.runner import run_pipeline as _run

    return _run(*args, **kwargs)
