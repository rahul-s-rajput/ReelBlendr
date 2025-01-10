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
from difflib import SequenceMatcher

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
            debug_print(f"Genre query: {genre_query}")
            try:
                genre_results = self.ytmusic.search(genre_query, filter="songs", limit=30)  # Reduced limit
                for track in genre_results:
                    if(track['duration_seconds'] >= duration_sec) and track['duration_seconds'] <= 3000:
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

            # Keep track of seen tracks to avoid duplicates
            seen_tracks = set()  # Track by name + duration combination

            def is_similar_title(title1: str, title2: str, threshold: float = 0.8) -> bool:
                """Check if two titles are similar using sequence matcher"""
                return SequenceMatcher(None, title1.lower(), title2.lower()).ratio() >= threshold

            def is_similar_duration(dur1: int, dur2: int, threshold_ms: int = 5000) -> bool:
                """Check if two durations are within threshold milliseconds"""
                return abs(dur1 - dur2) <= threshold_ms

            # Filter out similar tracks and create final list
            unique_tracks = []
            for track in final_tracks:
                # Check if we already have a similar track
                is_duplicate = False
                for existing_track in unique_tracks:
                    if (
                        # Same artist
                        track['artist'] == existing_track['artist'] 
                        and (
                            # Similar title
                            is_similar_title(track['name'], existing_track['name'])
                            or
                            # One title is substring of another
                            track['name'].lower() in existing_track['name'].lower()
                            or existing_track['name'].lower() in track['name'].lower()
                        )
                        and
                        # Similar duration
                        is_similar_duration(track['duration_ms'], existing_track['duration_ms'])
                    ):
                        # Keep the one with more views
                        if track['view_count'] > existing_track['view_count']:
                            unique_tracks.remove(existing_track)
                            unique_tracks.append(track)
                        is_duplicate = True
                        break
                
                if not is_duplicate:
                    unique_tracks.append(track)

            # Sort by view count and prioritize tracks with content_focus in title (only if views >= 1000)
            unique_tracks.sort(key=lambda x: (
                not (content_focus.lower() in x['name'].lower() and x['view_count'] >= 1000),
                -x['view_count']
            ))
            return unique_tracks[:num_recommendations]

        except Exception as e:
            print(f"Error getting music recommendations: {str(e)}", file=sys.stderr, flush=True)
            return []

    def find_best_section(self, y: np.ndarray, sr: int, style_min: int, target_duration_sec: float, mood: str) -> tuple:
        """Find the best section of audio based on mood and transitions"""
        try:
            # Set up debug printing
            def debug_print(*args, **kwargs):
                print(*args, file=sys.stderr, flush=True, **kwargs)

            hop_length = 256
            onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length, aggregate=np.median)
            onset_env = (onset_env - onset_env.min()) / (onset_env.max() - onset_env.min())  # Normalize
            
            # Calculate energy
            energy = self._calculate_energy(y, sr, hop_length)
            
            # Find transition points
            transition_points = self._find_transition_points(onset_env, sr, hop_length, min_distance_seconds=style_min)
            debug_print(f"Found {len(transition_points)} transition points")
            
            # Select best segment
            best_segment = self._select_smooth_segment(
                onset_env, energy, sr, hop_length, transition_points, 
                mood, target_duration_sec, min_transitions=4
            )
            debug_print(f"Best segment: {best_segment}")
            
            if best_segment is None:
                debug_print("No suitable segment found, falling back to default section")
                return transition_points,0, target_duration_sec, 0, int(target_duration_sec * sr)
            
            start_time, end_time = best_segment
            debug_print(f"Start time: {start_time}, End time: {end_time}")
            
            # Ensure we have valid numbers before converting
            if not (isinstance(start_time, (int, float)) and isinstance(end_time, (int, float))):
                debug_print(f"Invalid time values: start_time={type(start_time)}, end_time={type(end_time)}")
                return transition_points,0, int(target_duration_sec * sr), 0, int(target_duration_sec * sr)
            
            # Convert to integers for slicing
            start_sample = int(np.floor(start_time * sr))
            end_sample = int(np.floor(end_time * sr))
            
            debug_print(f"Best section found: {start_time:.2f}s to {end_time:.2f}s")
            debug_print(f"Samples: {start_sample} to {end_sample}")
            
            return transition_points,start_time, end_time,start_sample, end_sample
            
        except Exception as e:
            print(f"Error finding best section: {str(e)}", file=sys.stderr, flush=True)
            import traceback
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            return 0, int(target_duration_sec * sr)

    def _calculate_energy(self, y, sr, hop_length):
        """Calculate short-time energy of the audio signal"""
        frame_length = int(sr * 0.05)  # 50ms frames
        energy = np.array([
            np.sum(np.abs(y[i:i + frame_length])**2)
            for i in range(0, len(y), hop_length)
        ])
        return energy / energy.max()  # Normalize energy

    def _find_transition_points(self, onset_env, sr, hop_length, min_distance_seconds=4.0):
        """Find significant transition points in the audio"""
        max_retries = 4
        retry_count = 0
        transition_points = []
        
        def debug_print(*args, **kwargs):
            print(*args, file=sys.stderr, flush=True, **kwargs)
        
        while retry_count < max_retries and not transition_points:
            # Reduce threshold and prominence by 10% on each retry
            reduction_factor = 1.0 - (retry_count * 0.25)
            threshold = (0.2 + 0.1 * np.std(onset_env)) * reduction_factor
            prominence = (0.1 + 0.05 * np.mean(onset_env)) * reduction_factor
            debug_print(f"Attempt {retry_count + 1}: threshold={threshold:.4f}, prominence={prominence:.4f}")
            # Detect peaks
            peaks, _ = find_peaks(onset_env, height=threshold, prominence=prominence)
            peaks_in_seconds = peaks * hop_length / sr
            
            debug_print(f"Found {len(peaks)} initial peaks")
            
            if len(peaks) == 0:
                retry_count += 1
                continue
            
            # Rest of the existing logic remains the same
            filtered_peaks = []
            last_peak_time = 0
            
            while last_peak_time < peaks_in_seconds[-1]:
                search_start = last_peak_time + min_distance_seconds
                search_end = search_start + min_distance_seconds
                
                peaks_in_range = [
                    p for p in range(len(peaks)) 
                    if search_start <= peaks_in_seconds[p] < search_end
                ]
                
                if peaks_in_range:
                    peaks_with_significance = []
                    for p in peaks_in_range:
                        peak = peaks[p]
                        current_value = onset_env[peak]
                        previous_value = onset_env[peak - 1] if peak > 0 else 0
                        next_value = onset_env[peak + 1] if peak < len(onset_env) - 1 else 0
                        significance = max(abs(current_value - previous_value), abs(current_value - next_value))
                        peaks_with_significance.append((peak, significance))
                    
                    most_significant_peak = max(peaks_with_significance, key=lambda x: x[1])[0]
                    filtered_peaks.append(most_significant_peak)
                    last_peak_time = peaks_in_seconds[np.where(peaks == most_significant_peak)[0][0]]
                else:
                    last_peak_time += min_distance_seconds
            
            # Calculate final significances
            transition_points = []
            for peak in filtered_peaks:
                current_value = onset_env[peak]
                previous_value = onset_env[peak - 1] if peak > 0 else 0
                next_value = onset_env[peak + 1] if peak < len(onset_env) - 1 else 0
                significance = max(abs(current_value - previous_value), abs(current_value - next_value))
                time = peak * hop_length / sr
                transition_points.append((time, significance))
            
            if not transition_points:
                retry_count += 1
            
        return transition_points

    def _select_smooth_segment(self, onset_env, energy, sr, hop_length, transition_points, 
                             mood, duration, min_transitions=2):
        """Select a smooth segment based on mood and transitions"""
        segment_length_samples = duration * sr
        hop_per_second = sr // hop_length

        # Get mood-based energy thresholds
        start_threshold, end_threshold = self._get_energy_thresholds(mood)
        min_threshold = 0.05

        best_segment = None
        max_above_median = 0
        max_avg_significance = 0

        # Calculate median significance
        median_significance = self._calculate_median_significance(transition_points)

        while best_segment is None and start_threshold >= min_threshold and end_threshold >= min_threshold:
            for start_time, _ in transition_points:
                start_sample = int(start_time * sr)
                end_sample = start_sample + segment_length_samples

                if end_sample >= len(onset_env) * hop_length:
                    continue

                points_in_segment = [tp for tp in transition_points 
                                   if start_time <= tp[0] < start_time + duration]
                num_above_median = self._count_points_above_median(
                    transition_points, median_significance, start_time, duration
                )

                avg_significance = (
                    sum(tp[1] for tp in points_in_segment) / len(points_in_segment)
                    if points_in_segment else 0
                )

                start_frame = int(start_sample // hop_length)
                end_frame = int(end_sample // hop_length)

                print(f"Start frame: {start_frame}, End frame: {end_frame}", file=sys.stderr, flush=True)
                print(f"hop per second: {hop_per_second}", file=sys.stderr, flush=True)
                start_energy = np.mean(energy[start_frame:start_frame + hop_per_second])
                end_energy = np.mean(energy[end_frame - hop_per_second:end_frame])

                if (len(points_in_segment) >= min_transitions and 
                    start_energy > start_threshold and 
                    end_energy > end_threshold):
                    if (num_above_median > max_above_median or 
                        (num_above_median == max_above_median and 
                         avg_significance > max_avg_significance)):
                        max_above_median = num_above_median
                        max_avg_significance = avg_significance
                        best_segment = (start_sample / sr, end_sample / sr)

            start_threshold -= 0.05
            end_threshold -= 0.05

        return best_segment

    def _get_energy_thresholds(self, mood):
        """Get energy thresholds based on mood"""
        mood_settings = {
            "chill": (0.1, 0.1),
            "commute": (0.2, 0.2),
            "energy boosters": (0.4, 0.4),
            "feel good": (0.3, 0.3),
            "focus": (0.15, 0.15),
            "party": (0.4, 0.4),
            "romance": (0.15, 0.15),
            "sad": (0.1, 0.1),
            "workout": (0.4, 0.4),
        }
        return mood_settings.get(mood, (0.2, 0.2))

    def _calculate_median_significance(self, transition_points):
        """Calculate median significance of transition points"""
        significances = [significance for _, significance in transition_points]
        return np.median(significances)

    def _count_points_above_median(self, transition_points, median_significance, start_time, window_duration):
        """Count transition points above median significance within a window"""
        return sum(
            1 for time, significance in transition_points
            if start_time <= time < start_time + window_duration 
            and significance > median_significance
        )


    def get_audio_analysis(self, track_name: str, artist: str, style: str, target_duration: int, mood: str) -> Dict:
        """Get audio analysis using librosa"""
        def debug_print(*args, **kwargs):
            print(*args, file=sys.stderr, flush=True, **kwargs)
        try:
            # Search for the track
            if track_name.startswith(('https://www.youtube.com/', 'https://music.youtube.com/', 'https://youtu.be/')):
                # Extract video ID from URL
                if 'youtu.be/' in track_name:
                    video_id = track_name.split('youtu.be/')[-1].split('?')[0]
                else:
                    video_id = track_name.split('v=')[-1].split('&')[0]
                
                # Get track info directly from video ID
                try:
                    track_info = self.ytmusic.get_song(video_id)
                    track_name = track_info['title']
                    artist = track_info['artists'][0]['name'] if track_info.get('artists') else 'Unknown'
                except Exception as e:
                    print(f"Error getting track info, using URL as is: {e}")
                    # Continue with video ID we extracted
            else:
                # Search by track name and artist
                search_results = self.ytmusic.search(f"{track_name} {artist}", filter="songs", limit=1)
                if not search_results:
                    raise ValueError("Track not found on YouTube Music")
                video_id = search_results[0]['videoId']
                
            print(f"Processing video ID: {video_id} for track: {track_name} by {artist}")
            
            base_temp_file = f'temp_{video_id}'
            temp_file = os.path.abspath(f'{base_temp_file}.mp3.mp3')
            output_file = os.path.abspath(os.path.join('data', 'trimmed_audio.mp3'))
            
            # Download audio using yt-dlp
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'outtmpl': os.path.abspath(f'{base_temp_file}.mp3')
            }
            
            try:
                style_min = {
                    "Smooth/Cinematic": 4,
                    "Fast-paced": 2,
                    "Documentary": 7
                }
                # Download the audio
                with YoutubeDL(ydl_opts) as ydl:
                    print(f"Downloading audio from video ID: {video_id}")
                    ydl.download([f'https://www.youtube.com/watch?v={video_id}'])
                
                # Load and analyze the audio
                y, sr = librosa.load(temp_file, sr=None)
                target_duration_sec = target_duration / 1000
                print(f"Style min: {style_min[style]}")
                # Find the best section based on mood
                transition_points, start_time, end_time, start_sample, end_sample = self.find_best_section(y, sr, style_min[style], target_duration_sec, mood)
                
                # Extract and save the selected section
                y_section = y[start_sample:end_sample]
                
                # Apply fade in/out
                fade_duration = min(2.0, target_duration_sec / 4)  # 2 seconds or quarter of duration
                fade_length = int(fade_duration * sr)
                fade_in = np.linspace(0, 1, fade_length)
                fade_out = np.linspace(1, 0, fade_length)
                
                y_section[:fade_length] *= fade_in
                y_section[-fade_length:] *= fade_out
                
                import soundfile as sf
                sf.write(output_file, y_section, sr)
                print(f"Saved trimmed audio to: {output_file}")
                
                # Filter transition points for the segment, convert to relative times, and remove the first point if it is 0.0
                segment_transition_points = [
                    float(tp[0] - start_time) for tp in transition_points if start_time <= tp[0] < end_time
                ]
                
                analysis_result = {
                    'track_info': {
                        'name': track_name,
                        'artist': artist,
                        'duration': target_duration,
                        'video_id': video_id,
                        'trimmed_file': output_file,
                        'section_start': float(start_sample / sr),
                        'mood': mood
                    },
                    'analysis': {
                        'transition_points': [
                            {
                                'time': float(time)
                            } for time in segment_transition_points
                        ]
                    }
                }
                
                # Calculate segments using transition points
                segments = self.calculate_segments(segment_transition_points, target_duration)
                analysis_result['segments'] = segments
                debug_print(segments)
                debug_print(analysis_result)
                return analysis_result
                
            finally:
                # Clean up temporary files
                for ext in ['.mp3', '.mp3.mp3']:
                    cleanup_file = os.path.abspath(f'{base_temp_file}{ext}')
                    if os.path.exists(cleanup_file):
                        try:
                            os.remove(cleanup_file)
                            print(f"Cleaned up temporary file: {cleanup_file}")
                        except Exception as e:
                            print(f"Error removing temporary file {cleanup_file}: {e}")
                    
        except Exception as e:
            print(f"Error analyzing audio: {e}")
            return None
            

    def calculate_segments(self, segment_transitions, target_duration: float) -> List[Dict]:
        """Calculate video segments using transition points and energy analysis"""
        try:
            # Get basic parameters
            target_duration_sec = target_duration / 1000
            
            # Create segments based on transitions
            segments = []
            current_time = 0.0
            for transition in range(len(segment_transitions)-1):
                relative_time = segment_transitions[transition]
                next_time = segment_transitions[transition+1]
                duration = next_time - relative_time
                segments.append({
                    'start': float(current_time),
                    'duration': float(duration)
                })
                current_time = next_time
            
            # Add final segment if needed
            if current_time < target_duration_sec:
                segments.append({
                    'start': float(current_time),
                    'duration': float(target_duration_sec - current_time)
                })
            
            return segments

        except Exception as e:
            print(f"Error calculating segments: {e}")
            return []

    def _calculate_energy_at_time(self, y, sr, time):
        """Calculate energy at a specific time point"""
        frame_size = int(sr * 0.05)  # 50ms window
        start_sample = int(time * sr)
        end_sample = min(start_sample + frame_size, len(y))
        if start_sample >= len(y):
            return 0.0
        segment = y[start_sample:end_sample]
        return np.mean(np.abs(segment)**2)

if __name__ == "__main__":
    import sys
    import json
    import io
    
    # Set up UTF-8 encoding for output
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    try:
        # Get input from command line
        input_data = json.loads(sys.argv[1])
        print(input_data, file=sys.stderr, flush=True)
        # Initialize recommender
        recommender = MusicRecommender()
        
        # Get recommendations
        recommendations = recommender.find_recommendations(
            input_data['contentFocus'],
            input_data['genre'],
            input_data['mood'],
            input_data['duration']
        )
        
        # Ensure recommendations is a list
        if not isinstance(recommendations, list):
            recommendations = list(recommendations)
        
        # Ensure all values are JSON serializable
        clean_recommendations = []
        for rec in recommendations:
            clean_rec = {}
            for key, value in rec.items():
                if isinstance(value, (int, float)):
                    clean_rec[key] = float(value)
                else:
                    clean_rec[key] = str(value)  # Convert everything else to strings
            clean_recommendations.append(clean_rec)
        
        # Print single JSON output
        print(json.dumps(clean_recommendations, ensure_ascii=False))
        sys.stdout.flush()
        
    except Exception as e:
        print(f"Error in Python script: {str(e)}", file=sys.stderr)
        sys.exit(1)