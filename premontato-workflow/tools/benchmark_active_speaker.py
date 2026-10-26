"""Measure local ASD work on one user-selected interval; never clears a user cache."""
import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'worker'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--fps', type=float, required=True)
    parser.add_argument('--duration-frames', type=int, required=True)
    parser.add_argument('--start', type=int, required=True)
    parser.add_argument('--end', type=int, required=True)
    args = parser.parse_args()
    if not args.source.is_file() or not 0 < args.fps or not 0 <= args.start < args.end <= args.duration_frames:
        parser.error('Provide an existing source and valid original frame coordinates.')
    source = {'path': str(args.source), 'fps': args.fps, 'duration_frames': args.duration_frames}
    from active_speaker import ActiveSpeaker
    previous = os.environ.get('PREMONTATO_CACHE_DIR')
    rows = []
    try:
        with tempfile.TemporaryDirectory(prefix='premontato-asd-benchmark-') as folder:
            os.environ['PREMONTATO_CACHE_DIR'] = folder
            started = time.perf_counter()
            analyzer = ActiveSpeaker()
            initialization = time.perf_counter() - started

            def measure(name, start, end):
                result = analyzer.analyze(source, start, end)
                rows.append({'scenario': name, 'start_frame': start, 'end_frame': end,
                             'status': result['status'], 'elapsed_seconds': result['elapsed_seconds'],
                             'interval_cache_hit': result['cache_hit'],
                             'sample_cache_hit': result['sample_cache_hit'],
                             'stage_seconds': result['stage_seconds'], 'work': result['work']})

            measure('cold_audio_and_speaker', args.start, args.end)
            measure('same_interval', args.start, args.end)
            if args.end-args.start > 2:
                # Same midpoint, hence the same sample; the classification slice changes.
                measure('same_sample_different_interval', args.start+1, args.end-1)
            # New ASD directory, same private PCM directory and loaded model.
            analyzer.cache = Path(folder) / 'warm-pcm-new-speaker-cache'
            measure('warm_pcm_cold_speaker', args.start, args.end)
            print(json.dumps({'provider': analyzer.session.get_providers(),
                              'inference_threads': analyzer.session.get_session_options().intra_op_num_threads,
                              'initialization_seconds': round(initialization, 6), 'runs': rows}, indent=2))
    finally:
        if previous is None:
            os.environ.pop('PREMONTATO_CACHE_DIR', None)
        else:
            os.environ['PREMONTATO_CACHE_DIR'] = previous


if __name__ == '__main__':
    main()
