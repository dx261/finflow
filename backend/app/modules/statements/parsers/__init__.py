"""Bank statement parsers.

The parsing strategy is coordinate-free: text is normalized, anchors are
located dynamically, and the transaction table is found by scoring every
row's header coverage — never by hardcoding row numbers.
"""
