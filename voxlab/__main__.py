"""Offline Selma VOX command-line entrypoint."""
import argparse
import json
from .pipeline import analyze_file
from .corrections import record_correction, export_corrections


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m voxlab", description="Evidence-preserving audio review")
    subs = parser.add_subparsers(dest="command", required=True)
    review = subs.add_parser("analyze", help="analyze local media and preserve original")
    review.add_argument("input")
    review.add_argument("--out", default="vox-output")
    review.add_argument("--sensitivity", type=float, default=.90)
    review.add_argument("--asr-model", help="local Faster-Whisper model directory (optional)")
    review.add_argument("--language", help="e.g. en; default auto")
    review.add_argument("--no-enhance", action="store_true")
    correct = subs.add_parser("correct", help="record a human interpretation without auto-training")
    correct.add_argument("--db", required=True)
    correct.add_argument("--sha", required=True)
    correct.add_argument("--start", type=float, required=True)
    correct.add_argument("--end", type=float, required=True)
    correct.add_argument("--text", required=True)
    correct.add_argument("--status", choices=["hypothesis", "listener_reported", "rejected"], required=True)
    correct.add_argument("--reviewer", default="human")
    export = subs.add_parser("export-corrections")
    export.add_argument("--db", required=True)
    export.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    if args.command == "analyze":
        result = analyze_file(args.input, args.out, args.sensitivity,
                              args.asr_model, args.language, not args.no_enhance)
        print(json.dumps({"report_path": result["report_path"],
                          "source_sha256": result["original"]["sha256"],
                          "event_count": len(result["analysis"]["events"]),
                          "asr_status": result["asr"]["status"]}, indent=2))
    elif args.command == "correct":
        print(json.dumps({"correction_id": record_correction(args.db, args.sha, args.start, args.end,
                                                                args.text, args.status, args.reviewer)}))
    else:
        print(json.dumps({"exported_review_only": export_corrections(args.db, args.out)}))


if __name__ == "__main__":
    main()