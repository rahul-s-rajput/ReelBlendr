from typing import List, Dict, Any
from pathlib import Path
import json
import google.generativeai as genai

def simplify_analysis_results(analysis_results_file: Path) -> dict:
    """Convert full analysis results into simplified format with only labels per segment"""
    try:
        with open(analysis_results_file, 'r') as f:
           full_results = json.load(f)
        simplified_results = {}
        for video_name, video_data in full_results.items():
           simplified_results[video_name] = {
               "segments": {}
           }
           
           for segment_id, segment_data in video_data.get("segments", {}).items():
               # Get unique labels across all frames in this segment
               unique_labels = set()
               for frame_data in segment_data.get("frames", {}).values():
                   for label_info in frame_data:
                       label = label_info.get("label")
                       confidence = label_info.get("confidence_score", 0.0)
                       if confidence >= 0.7:  # Only include labels with confidence > 70%
                           unique_labels.add(label)
                # Add segment to simplified results
               simplified_results[video_name]["segments"][segment_id] = {
                   "start_time": segment_data.get("start_time"),
                   "end_time": segment_data.get("end_time"),
                   "labels": sorted(list(unique_labels))  # Convert set to sorted list
               }
        # Save simplified results
        output_file = analysis_results_file.parent / 'simplified_analysis_results.json'
        with open(output_file, 'w') as f:
           json.dump(simplified_results, f, indent=2)
           
        print(f"Saved simplified results to {output_file}")
        return simplified_results
    except Exception as e:
        print(f"Error simplifying analysis results: {e}")
        import traceback
        traceback.print_exc()
        return {}
   
def create_edit_sequence(analysis_results_file: Path, prompt_parameters: dict, audio_segments: List[dict]) -> List[dict]:
    """Use Gemini Pro to create edit sequence from analysis results and cut according to audio segments"""
    try:
        with open(analysis_results_file, 'r') as f:
            analysis_results = json.load(f)

        print("Loaded analysis results successfully")

        # Define mood-based minimum durations
        mood_min_durations = {
            "Energetic": 2.0,
            "Calm": 5.0,
            "Serious": 4.0,
            "Playful": 2.5,
            "Dramatic": 3.5,
            "Neutral": 3.0,
            "Chill": 4.0
        }
        
        # Get minimum duration based on mood
        mood = prompt_parameters.get('mood_tone', 'Neutral')
        MIN_DURATION = mood_min_durations.get(mood, 3.0)  # Default to 3.0 if mood not found
        
        print(f"Using mood-based minimum duration: {MIN_DURATION}s for mood: {mood}")

        # Create a simplified list of available segments
        available_segments = []
        temp_segments = []

        for file_name, video_data in analysis_results.items():
            print(f"\nProcessing file: {file_name}")
            
            # Get video duration
            duration = video_data.get("duration", 0)
            segments = video_data.get("segments", {})
            
            for segment_id, segment_data in segments.items():
                start_time = float(segment_data.get("start_time", 0))
                end_time = float(segment_data.get("end_time", 0))
                duration = end_time - start_time
                
                # Get frame labels for this segment
                labels = segment_data.get("labels", [])
                all_labels = [{"label": label} for label in labels]
                
                segment_info = {
                    "file_name": file_name,
                    "start_time": start_time,
                    "end_time": end_time,
                    "duration": duration,
                    "labels": all_labels
                }
                
                if duration < MIN_DURATION:
                    temp_segments.append(segment_info)
                else:
                    if temp_segments:
                        # Merge skipped segments
                        merged_start = temp_segments[0]["start_time"]
                        merged_end = temp_segments[-1]["end_time"]
                        merged_duration = merged_end - merged_start
                        
                        # Find the segment with the longest duration among skipped segments
                        longest_segment = max(temp_segments, key=lambda x: x["duration"])
                        
                        merged_segment = {
                            "file_name": file_name,
                            "start_time": merged_start,
                            "end_time": merged_end,
                            "duration": merged_duration,
                            "labels": longest_segment["labels"]
                        }
                        
                        available_segments.append(merged_segment)
                        print(f"  Added merged segment: {merged_start:.2f}s - {merged_end:.2f}s ({merged_duration:.2f}s)")
                        print(f"  Labels: {[l['label'] for l in merged_segment['labels']]}")
                        
                        temp_segments = []
                    
                    available_segments.append(segment_info)
                    print(f"  Added segment: {start_time:.2f}s - {end_time:.2f}s ({duration:.2f}s)")
                    print(f"  Labels: {[l['label'] for l in all_labels]}")
            if temp_segments:
                # Merge skipped segments
                merged_start = temp_segments[0]["start_time"]
                merged_end = temp_segments[-1]["end_time"]
                merged_duration = merged_end - merged_start
                
                # Find the segment with the longest duration among skipped segments
                longest_segment = max(temp_segments, key=lambda x: x["duration"])
                
                merged_segment = {
                    "file_name": file_name,
                    "start_time": merged_start,
                    "end_time": merged_end,
                    "duration": merged_duration,
                    "labels": longest_segment["labels"]
                }
                
                available_segments.append(merged_segment)
                print(f"  Added merged segment: {merged_start:.2f}s - {merged_end:.2f}s ({merged_duration:.2f}s)")
                print(f"  Labels: {[l['label'] for l in merged_segment['labels']]}")
                
                temp_segments = []
            


        if not available_segments:
            print("No valid segments found")
            return []

        # Create prompt for Gemini
        system_prompt = f"""
        Analyze these video segments and identify the labels for each segment that are similar to these keywords:
        - Content focus: {prompt_parameters.get('content_focus', '')}
        - Key Labels: {', '.join(prompt_parameters.get('key_labels', []))}

        Available segments:
        {json.dumps([{
            'file_name': s['file_name'],
            'start_time': s['start_time'],
            'end_time': s['end_time'],
            'duration': s['duration'],
            'labels': [
                {
                    'label': label['label']
                }
                for label in s['labels']
            ]
        } for s in available_segments], indent=2)}

        Return a JSON array of all segments. Each object should contain:
        - file_name (string)
        - start_time (number)
        - end_time (number)
        - matching_labels (count of labels that are similar to either the content focus or any key label)

        Do not include any explanation or markdown formatting. The response should be a valid JSON array only.
        """

        print("\nSending request to Gemini...")
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(system_prompt)
        
        if not response or not response.text:
            print("No response from Gemini")
            return []

        # Extract JSON from response
        json_str = response.text
        print('\nGemini Response:')
        print('----------------------------------------')
        print(response.text)
        print('----------------------------------------')
        
        # Clean up the response text to extract just the JSON
        if "```json" in json_str.lower():
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
            
        # Remove any markdown formatting or extra whitespace
        json_str = json_str.strip()
        
        # Ensure we have valid JSON content
        if not json_str:
            print("Error: Empty JSON response")
            return []
            
        try:
            selected_segments = json.loads(json_str)
            print(f"\nProcessed {len(selected_segments)} selected segments")
            
            if not isinstance(selected_segments, list):
                print("Error: Response is not a list of segments")
                return []
                
            # Validate each segment has required fields
            valid_segments = []
            for seg in selected_segments:
                if all(key in seg for key in ['file_name', 'start_time', 'end_time', 'matching_labels']):
                    valid_segments.append(seg)
                else:
                    print(f"Skipping invalid segment: {seg}")
            
            if not valid_segments:
                print("No valid segments found in response")
                return []
                
            selected_segments = valid_segments
            
            # Sort segments by matching_labels in descending order
            selected_segments.sort(key=lambda x: x['matching_labels'], reverse=True)

            final_segments = []
            used_segments = set()

            print("\nMatching video segments to audio segments:")

            # Create a temporary sorted list of audio segments by duration (descending)
            temp_audio_segments = sorted(audio_segments, key=lambda x: x['duration'], reverse=True)

            # Create video_segments and remaining_segments lists
            video_segments = selected_segments[:len(audio_segments)]
            remaining_segments = selected_segments[len(audio_segments):]
            
            # Sort video segments by duration in descending order
            video_segments.sort(key=lambda x: x['end_time'] - x['start_time'], reverse=True)

            # Temporary storage for matched segments
            temp_final_segments = []

            for audio_seg in temp_audio_segments:
                audio_duration = audio_seg['duration']
                
                # Check if the corresponding video segment is long enough
                if video_segments and (video_segments[0]['end_time'] - video_segments[0]['start_time']) >= audio_duration:
                    video_seg = video_segments.pop(0)
                    final_segment = {
                        'file_name': video_seg['file_name'],
                        'start_time': video_seg['start_time'],
                        'end_time': video_seg['start_time'] + audio_duration + 0.2,
                        'matching_labels': video_seg['matching_labels'],
                        'audio_start': audio_seg['start'],
                        'audio_duration': audio_duration
                    }
                    used_segments.add(video_seg['file_name'])
                else:
                    # If the video segment is too short, move it to remaining_segments
                    if video_segments:
                        remaining_segments.insert(0, video_segments.pop(0))
                    
                    # Try to find a single segment that covers the audio duration
                    suitable_segment = next((seg for seg in remaining_segments if (seg['end_time'] - seg['start_time']) >= audio_duration), None)
                    
                    if suitable_segment:
                        final_segment = {
                            'file_name': suitable_segment['file_name'],
                            'start_time': suitable_segment['start_time'],
                            'end_time': suitable_segment['start_time'] + audio_duration + 0.2,
                            'matching_labels': suitable_segment['matching_labels'],
                            'audio_start': audio_seg['start'],
                            'audio_duration': audio_duration
                        }
                        remaining_segments.remove(suitable_segment)
                        used_segments.add(suitable_segment['file_name'])
                    else:
                        # Combine multiple segments to cover the audio duration
                        combined_segment = {
                            'file_name': [],
                            'start_time': [],
                            'end_time': [],
                            'matching_labels': 0,
                            'audio_start': audio_seg['start'],
                            'audio_duration': audio_duration
                        }
                        remaining_duration = audio_duration
                        
                        while remaining_duration > 0 and remaining_segments:
                            seg = remaining_segments.pop(0)
                            seg_duration = min(seg['end_time'] - seg['start_time'], remaining_duration)
                            combined_segment['file_name'].append(seg['file_name'])
                            combined_segment['start_time'].append(seg['start_time'])
                            combined_segment['end_time'].append(seg['start_time'] + seg_duration + 0.2)
                            combined_segment['matching_labels'] += seg['matching_labels']
                            remaining_duration -= seg_duration
                            used_segments.add(seg['file_name'])
                        
                        final_segment = combined_segment
                
                print(f"\nSegment {len(final_segments) + 1}:")
                print(f"Video: {final_segment['file_name']} ({final_segment['start_time']:.2f}s - {final_segment['end_time']:.2f}s)")
                print(f"Audio: {audio_seg['start']:.2f}s - {audio_seg['start'] + audio_duration:.2f}s")
                print(f"Duration: {audio_duration:.2f}s")
                print(f"Matching labels: {final_segment['matching_labels']}")
                
                temp_final_segments.append(final_segment)

            # Reorder final_segments to match the original order of audio_segments
            final_segments = sorted(temp_final_segments, key=lambda x: audio_segments.index(
                next(audio for audio in audio_segments if audio['start'] == x['audio_start'])
            ))

            total_duration = sum(seg['audio_duration'] for seg in final_segments)
            print(f"\nFinal sequence total duration: {total_duration:.2f}s")

            return final_segments

            
        except json.JSONDecodeError as e:
            print(f"Error parsing Gemini response: {e}")
            return []
            
    except Exception as e:
        print(f"Error in create_edit_sequence: {e}")
        import traceback
        traceback.print_exc()
        return [] 