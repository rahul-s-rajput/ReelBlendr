from typing import List, Dict
import random
from ytmusicapi import YTMusic
import librosa
import numpy as np
from yt_dlp import YoutubeDL
import os
import io
import sys
from scipy.signal import find_peaks
import json

class MusicRecommender:
    def __init__(self):
        """Initialize YouTube Music client"""
        try:
            self.ytmusic = YTMusic()
            print("Successfully connected to YouTube Music API", file=sys.stderr, flush=True)
        except Exception as e:
            print(f"Error initializing YouTube Music client: {str(e)}", file=sys.stderr, flush=True)
            raise

    def find_recommendations(self, 
                        content_focus: str,
                        mood: str,
                        genre: str,
                        duration: int,
                        num_recommendations: int = 3) -> List[Dict]:
        """Find music recommendations using YouTube Music"""
        try:
            # Redirect all debug prints to stderr
            def debug_print(*args, **kwargs):
                print(*args, file=sys.stderr, flush=True, **kwargs)
            
            

            def get_track_info(video_id: str) -> dict:
                try:
                    song_info = self.ytmusic.get_song(video_id)
                    view_count = int(song_info['videoDetails']['viewCount'].replace(',', ''))
                    return {
                        'view_count': view_count
                    }
                except Exception as e:
                    return {'view_count': 0}

            final_tracks = []
            duration_sec = duration / 1000

            # First get genre tracks (since this is usually a smaller set)
            genre_query = f"{content_focus} {genre} {mood} music" 

            try:
                genre_results = self.ytmusic.search(genre_query, filter="songs", limit=20)  # Reduced limit
                for track in genre_results:
                    if(track['duration_seconds'] >= duration_sec) and track['duration_seconds'] <= 6000:
                        final_tracks.append({
                            'id': track['videoId'],
                            'name': track['title'],
                            'artist': track['artists'][0]['name'] if track.get('artists') else 'Unknown',
                            'duration_ms': int(track['duration_seconds'] * 1000),
                            'external_url': f"https://music.youtube.com/watch?v={track['videoId']}",
                            'view_count': get_track_info(track['videoId'])['view_count'],
                            'videoId': track['videoId']
                    })

              
            except Exception as e:
                debug_print(f"Error in genre search: {e}")

            # Sort by view count and prioritize tracks with content_focus in title
            final_tracks.sort(key=lambda x: (
                content_focus.lower() not in x['name'].lower(),  # False sorts before True
                -x['view_count']  # Negative so higher views sort first
            ))
            return final_tracks[:num_recommendations]

        except Exception as e:
            print(f"Error getting music recommendations: {str(e)}", file=sys.stderr, flush=True)
            return []
        
if __name__ == "__main__":
    mr = MusicRecommender()
    test = ['black lives matter', 'chill', 'christmas', 'commute', 'energy boosters', 'feel good', 'focus', 'halloween', 'party', 'pride', 'romance', 'sad', 'sleep', 'workout', 'african', 'arabic', 'blues', 'bollywood & indian', 'brazilian', 'christian & gospel', 'classical', 'country & americana', 'dance & electronic', 'decades', 'family', 'folk & acoustic', 'francophone', 'hip-hop', 'indie & alternative', 'j-pop', 'jazz', 'k-pop', 'latin', 'mandopop & cantopop', 'metal', 'pop', 'r&b & soul', 'reggae & caribbean', 'rock', 'soundtracks & musicals']
    try:
        
        print(mr.find_recommendations("Underwater", "calm","indie", 10000))
    except Exception as e:
        print(e)

