from typing import List, Dict, Any
from pathlib import Path
import json
import google.generativeai as genai
import time

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
        style_min_durations = {
            "Smooth/Cinematic": 4.0,
            "Fast-paced": 2.0,
            "Documentary": 7.0
        }
        
        # Get minimum duration based on mood
        style = prompt_parameters.get('style', 'Smooth/Cinematic')
        MIN_DURATION = style_min_durations.get(style, 4.0)  # Default to 4.0 if mood not found
        
        print(f"Using style-based minimum duration: {MIN_DURATION}s for style: {style}")

        # Create a simplified list of available segments
        available_segments = []
        temp_segments = []

        # Store the original file order
        original_file_order = list(analysis_results.keys())
        print(f"Original file order: {original_file_order}")

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
        
        # Add retry mechanism
        max_retries = 3
        retry_count = 0
        selected_segments = None
        
        while retry_count < max_retries:
            try:
                response = model.generate_content(system_prompt)
                if not response or not response.text:
                    raise ValueError("Empty response from Gemini")

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
                
                # Additional cleaning steps
                json_str = json_str.strip()
                json_str = ''.join(char for char in json_str if ord(char) >= 32)  # Remove control characters
                json_str = json_str.replace('\n', '').replace('\r', '')  # Remove newlines
                json_str = json_str.replace('\t', '')  # Remove tabs
                
                # Try to fix truncated JSON
                if json_str.endswith('"video9'):
                    json_str = json_str.rsplit(',', 1)[0] + ']'
                elif not (json_str.endswith('}]') or json_str.endswith(']}')): 
                    json_str = json_str.rsplit(',', 1)[0] + ']'
                
                if not json_str:
                    raise ValueError("Empty JSON response")
                
                # Debug print to see the cleaned JSON string
                print("\nCleaned JSON string:")
                print(json_str[:100] + "..." if len(json_str) > 100 else json_str)
                
                selected_segments = json.loads(json_str)
                
                if not isinstance(selected_segments, list):
                    raise ValueError("Response is not a list of segments")
                
                # Validate each segment has required fields
                valid_segments = []
                for seg in selected_segments:
                    if all(key in seg for key in ['file_name', 'start_time', 'end_time', 'matching_labels']):
                        valid_segments.append(seg)
                    else:
                        print(f"Skipping invalid segment: {seg}")
                
                if not valid_segments:
                    raise ValueError("No valid segments found in response")
                
                selected_segments = valid_segments
                print(f"\nProcessed {len(selected_segments)} selected segments")
                break

            except Exception as e:
                print(f"Error processing Gemini response (attempt {retry_count + 1}/{max_retries}): {e}")
                retry_count += 1
                if retry_count < max_retries:
                    print("Retrying in 2 seconds...")
                    time.sleep(2)
        
        if selected_segments is None:
            print("Failed to get valid response from Gemini after all retries")
            return []

        # Add ordering logic based on prompt parameters
        final_segments = []
        used_segments = set()
        ordering = prompt_parameters.get('order', 'AI-determined')  # Default to relevance-based
        print(f"Ordering: {ordering}")
        if ordering == 'Chronological':
            # Create a mapping of file names to their original position
            file_order_map = {fname: idx for idx, fname in enumerate(original_file_order)}
            # Sort by original file order and then by start_time within each file
            selected_segments.sort(key=lambda x: (file_order_map[x['file_name']], x['start_time']))
            
            # Create a mapping of possible video segments for each audio segment
            possible_segments_map = []
            
            # First pass: Find all possible segments for each audio segment
            for audio_idx, audio_seg in enumerate(audio_segments):
                audio_duration = audio_seg['duration']
                suitable_segments = []
                
                # Check individual segments
                suitable_segments.extend([
                    (idx, seg) for idx, seg in enumerate(selected_segments)
                    if (seg['end_time'] - seg['start_time']) >= audio_duration
                ])
                
                # Check for consecutive segments from same file that can be combined
                for i in range(len(selected_segments)):
                    if i in [idx for idx, _ in suitable_segments]:
                        continue  # Skip if this segment is already suitable on its own
                        
                    combined_duration = 0
                    j = i
                    while j < len(selected_segments):
                        if (j > i and selected_segments[j]['file_name'] != selected_segments[i]['file_name']):
                            break
                        
                        combined_duration = selected_segments[j]['end_time'] - selected_segments[i]['start_time']
                        if combined_duration >= audio_duration:
                            # Create a combined segment
                            combined_seg = {
                                'file_name': selected_segments[i]['file_name'],
                                'start_time': selected_segments[i]['start_time'],
                                'end_time': selected_segments[j]['end_time'],
                                'matching_labels': max(s['matching_labels'] for s in selected_segments[i:j+1])
                            }
                            suitable_segments.append((i, combined_seg))
                            break
                        j += 1
                
                possible_segments_map.append(suitable_segments)
            
            # Second pass: Find constraints based on single-option segments
            forced_min_indices = [0] * len(audio_segments)  # Minimum allowed index for each position
            forced_max_indices = [len(selected_segments)] * len(audio_segments)  # Maximum allowed index
            
            for audio_idx, possibilities in enumerate(possible_segments_map):
                print(f"Audio index: {audio_idx}, possibilities: {possibilities}")
                if len(possibilities) == 1:
                    # This audio segment has only one possible video segment
                    forced_idx = possibilities[0][0]  # Get the index of the only possible segment
                    
                    # Update constraints for earlier segments
                    for i in range(audio_idx):
                        forced_max_indices[i] = min(forced_max_indices[i], forced_idx)
                    
                    # Update constraints for later segments
                    for i in range(audio_idx + 1, len(audio_segments)):
                        forced_min_indices[i] = max(forced_min_indices[i], forced_idx + 1)
            
            # Apply constraints to possible_segments_map
            for audio_idx in range(len(audio_segments)):
                possible_segments_map[audio_idx] = [
                    (idx, seg) for idx, seg in possible_segments_map[audio_idx]
                    if forced_min_indices[audio_idx] <= idx < forced_max_indices[audio_idx]
                ]
            
            def can_complete_sequence(used_idx: int, current_audio_idx: int) -> bool:
                """Check if remaining audio segments can be satisfied after using this video index"""
                # Keep track of available indices
                available_indices = set(range(used_idx + 1, len(selected_segments)))
                used_indices = set()
                
                # Add any previously used indices
                for segment in temp_final_segments:
                    used_indices.add(selected_segments.index(next(
                        s for s in selected_segments 
                        if s['file_name'] == segment['file_name'] 
                        and s['start_time'] == segment['start_time']
                    )))
                
                # Calculate how many segments we need for remaining audio segments
                remaining_audio_count = len(audio_segments) - current_audio_idx - 1
                
                # If we don't have enough remaining indices, fail early
                if len(available_indices) < remaining_audio_count:
                    return False
                
                # Try to find valid segments for each remaining audio segment
                remaining_indices = available_indices.copy()
                
                for audio_idx in range(current_audio_idx + 1, len(audio_segments)):
                    found_valid = False
                    
                    # Get valid segments for this audio
                    valid_options = [
                        (idx, seg) for idx, seg in possible_segments_map[audio_idx]
                        if idx in remaining_indices and idx not in used_indices
                    ]
                    
                    if not valid_options:
                        return False
                        
                    # Calculate how many segments we still need after this one
                    segments_needed_after = len(audio_segments) - audio_idx - 1
                    
                    # Find the earliest valid option that leaves enough segments for the future
                    for idx, seg in sorted(valid_options, key=lambda x: x[0]):  # Sort by index to maintain chronological order
                        # Check if we have enough segments left after this one
                        segments_available_after = len([i for i in remaining_indices if i > idx])
                        if segments_available_after < segments_needed_after:
                            continue
                            
                        # Temporarily mark this index as used
                        temp_remaining = remaining_indices - {idx}
                        temp_used_indices = used_indices | {idx}
                        
                        # Look ahead to verify future segments
                        can_use = True
                        future_remaining = temp_remaining.copy()
                        future_used = temp_used_indices.copy()
                        
                        for future_idx in range(audio_idx + 1, len(audio_segments)):
                            future_options = [
                                (i, s) for i, s in possible_segments_map[future_idx]
                                if i in future_remaining and i not in future_used
                            ]
                            if not future_options:
                                can_use = False
                                break
                            # Simulate using the earliest valid option
                            min_future_idx = min(i for i, _ in future_options)
                            future_remaining.remove(min_future_idx)
                            future_used.add(min_future_idx)
                        
                        if can_use:
                            found_valid = True
                            remaining_indices = temp_remaining
                            used_indices = temp_used_indices
                            break
                    
                    if not found_valid:
                        return False
                
                return True

            # Find best combination that satisfies all constraints
            temp_final_segments = []
            last_used_idx = -1
            
            for audio_idx, audio_seg in enumerate(audio_segments):
                audio_duration = audio_seg['duration']
                
                # Get valid segments (after the last used one)
                valid_segments = [
                    (idx, seg) for idx, seg in possible_segments_map[audio_idx]
                    if idx > last_used_idx
                ]
                
                # Filter segments based on look-ahead check
                valid_segments = [
                    (idx, seg) for idx, seg in valid_segments
                    if can_complete_sequence(idx, audio_idx)
                ]
                
                if not valid_segments:
                    print(f"No valid segments found for audio segment {audio_idx + 1} that allow completion")
                    return []
                
                # Score each valid segment
                best_segment = None
                best_score = float('-inf')
                
                for idx, seg in valid_segments:
                    # Check if this segment overlaps with any previously selected segments
                    overlaps = any(
                        prev_seg['file_name'] == seg['file_name'] and (
                            (prev_seg['start_time'] <= seg['start_time'] <= prev_seg['end_time']) or
                            (prev_seg['start_time'] <= seg['end_time'] <= prev_seg['end_time']) or
                            (seg['start_time'] <= prev_seg['start_time'] and seg['end_time'] >= prev_seg['end_time'])
                        )
                        for prev_seg in temp_final_segments
                    )
                    
                    if overlaps:
                        continue  # Skip overlapping segments
                    
                    # Base score is the number of matching labels
                    score = seg['matching_labels']
                    
                    # Penalty for adjacent segments from same video
                    if temp_final_segments:
                        last_segment = temp_final_segments[-1]
                        if seg['file_name'] == last_segment['file_name']:
                            score -= 10
                    
                    # Penalty for using early segments with high matching_labels too soon
                    remaining_segments = len(audio_segments) - audio_idx - 1
                    if remaining_segments > 0:
                        # Calculate how many high-quality segments we're leaving
                        better_segments = len([
                            (i, s) for i, s in possible_segments_map[audio_idx]
                            if i > idx and s['matching_labels'] >= seg['matching_labels']
                        ])
                        
                        # If this is one of our best segments and we're early in the sequence,
                        # apply a penalty to save some good segments for later
                        if seg['matching_labels'] > 20 and audio_idx < len(audio_segments) // 2:
                            score -= (remaining_segments * 2)  # Bigger penalty early in sequence
                            
                        # Penalty for reducing future options too much
                        future_options_count = len([
                            (i, s) for i, s in possible_segments_map[audio_idx + 1]
                            if i > idx
                        ]) if audio_idx + 1 < len(audio_segments) else 0
                        
                        if future_options_count < remaining_segments * 2:  # We want at least 2 options per future segment
                            score -= (remaining_segments * 3 - future_options_count)
                    
                    if score > best_score:
                        best_score = score
                        best_segment = (idx, seg)
                
                if best_segment:
                    idx, seg = best_segment
                    final_segment = {
                        'file_name': seg['file_name'],
                        'start_time': seg['start_time'],
                        'end_time': seg['start_time'] + audio_duration + (0.2 if audio_idx < len(audio_segments) - 1 else 0),
                        'matching_labels': seg['matching_labels'],
                        'audio_start': audio_seg['start'],
                        'audio_duration': audio_duration
                    }
                    
                    temp_final_segments.append(final_segment)
                    last_used_idx = idx
                    
                    print(f"\nSegment {len(temp_final_segments)}:")
                    print(f"Video: {final_segment['file_name']} "
                          f"({final_segment['start_time']:.2f}s - {final_segment['end_time']:.2f}s)")
                    print(f"Audio: {audio_seg['start']:.2f}s - {audio_seg['start'] + audio_duration:.2f}s")
                    print(f"Duration: {audio_duration:.2f}s")
                    print(f"Matching labels: {final_segment['matching_labels']}")

            final_segments = temp_final_segments
                

        else:
            # Original relevance-based sorting
            selected_segments.sort(key=lambda x: x['matching_labels'], reverse=True)

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
                        'end_time': video_seg['start_time'] + audio_duration + (0.2 if len(temp_final_segments) < len(audio_segments) - 1 else 0),
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
                            'end_time': suitable_segment['start_time'] + audio_duration + (0.2 if len(temp_final_segments) < len(audio_segments) - 1 else 0),
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
                            combined_segment['end_time'].append(seg['start_time'] + seg_duration + (0.2 if len(temp_final_segments) < len(audio_segments) - 1 else 0))
                            combined_segment['matching_labels'] += seg['matching_labels']
                            remaining_duration -= seg_duration
                            used_segments.add(seg['file_name'])
                        
                        final_segment = combined_segment
                
                print(f"\nSegment {len(final_segments) + 1}:")
                if isinstance(final_segment['file_name'], list):
                    # Handle multiple segments case
                    for i in range(len(final_segment['file_name'])):
                        print(f"Video {i+1}: {final_segment['file_name'][i]} "
                            f"({final_segment['start_time'][i]:.2f}s - {final_segment['end_time'][i]:.2f}s)")
                else:
                    # Handle single segment case
                    print(f"Video: {final_segment['file_name']} "
                        f"({final_segment['start_time']:.2f}s - {final_segment['end_time']:.2f}s)")
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

            
    except Exception as e:
        print(f"Error in create_edit_sequence: {e}")
        import traceback
        traceback.print_exc()
        return [] 