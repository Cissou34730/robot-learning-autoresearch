"""Python campaign launcher: the trusted loop around PI sessions and Runner calls.

Modules take the campaign root explicitly; the launcher never relies on the
import-time ``runner.paths.ROOT`` of its own process.
"""
