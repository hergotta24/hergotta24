"""Crowd-vs-Alex chess for the GitHub profile README.

Viewers click a move link on the README, which opens a pre-filled issue.
A GitHub Action hands that issue to this package, which validates the move,
updates the saved game, redraws the board, and rewrites the README section.

Inspired by Tim Burgan's community chess game: https://github.com/timburgan/timburgan
"""
