"""Flow timeline store — persistent timeline model behind the scene grid.

Scenes ARE the timeline: the ordered scenes form the video track; ffmpeg
assembly concatenates them into one complete track, alongside audio
(narration/music) and caption (text) tracks. This package holds the data model,
frame math, and undo log that the agent tools operate on.
"""
