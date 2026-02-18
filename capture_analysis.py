#!/usr/bin/env python3
"""Connect to SmartCV WebSocket, collect analysis for a few seconds, save to analysis_output.json"""
import asyncio
import json
import websockets

OUTPUT_FILE = "analysis_output.json"
HOST = "localhost"
PORT = 6565
COLLECT_SECONDS = 25  # Let the video be processed

async def main():
    uri = f"ws://{HOST}:{PORT}"
    payloads = []
    try:
        async with websockets.connect(uri) as ws:
            end = asyncio.get_event_loop().time() + COLLECT_SECONDS
            while asyncio.get_event_loop().time() < end:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)
                    payloads.append(data)
                except asyncio.Timeout:
                    continue
    except Exception as e:
        print(f"Connection error: {e}")
        print("Is SmartCV running? Start it first, then run this script.")
        return
    if not payloads:
        print("No data received.")
        return
    # Save last payload and a summary
    latest = payloads[-1]
    inputs_seen = [(p.get("input_p1"), p.get("input_p2")) for p in payloads if p.get("input_p1") or p.get("input_p2")]
    with open(OUTPUT_FILE, "w") as f:
        json.dump({
            "latest": latest,
            "total_samples": len(payloads),
            "states_seen": list({p.get("state") for p in payloads if p.get("state")}),
            "input_samples": inputs_seen[:10],
        }, f, indent=2)
    print(f"Saved {len(payloads)} samples to {OUTPUT_FILE}")
    print("Latest state:", latest.get("state"), "| round:", latest.get("round"))
    print("Input P1:", repr(latest.get("input_p1")))
    print("Input P2:", repr(latest.get("input_p2")))
    if inputs_seen:
        print(f"Inputs seen in {len(inputs_seen)} sample(s); first:", inputs_seen[0])
    else:
        print("No input_p1/input_p2 text captured. Check config [input_display] regions or enable debug_mode to inspect crops.")

if __name__ == "__main__":
    asyncio.run(main())
