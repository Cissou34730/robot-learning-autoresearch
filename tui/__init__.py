"""Read-only campaign report for Windows Terminal.

The report is presentation only. It reads durable campaign state, results and
usage through `runner.paths`, never writes outside the reporting process and
holds no control channel of its own.
"""
