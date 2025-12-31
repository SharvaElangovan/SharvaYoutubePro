#!/bin/bash
# Combine two emoji quiz videos into one
# Usage: ./combine_videos.sh video1.mp4 video2.mp4 output.mp4

if [ $# -lt 3 ]; then
    echo "Usage: $0 video1.mp4 video2.mp4 output.mp4"
    exit 1
fi

# Create a file list for ffmpeg
echo "file '$1'" > /tmp/video_list.txt
echo "file '$2'" >> /tmp/video_list.txt

# Concatenate videos
ffmpeg -y -f concat -safe 0 -i /tmp/video_list.txt -c copy "$3"

echo "Combined video saved to: $3"
