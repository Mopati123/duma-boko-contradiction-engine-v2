#!/usr/bin/env python3
"""
Simple web-based evidence review interface for manual verification.
Opens in browser for easy review of findings.
"""
import json
import csv
import webbrowser
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import socket

# Create HTML review page
def create_review_html():
    """Generate HTML review interface."""
    
    # Load evidence CSV if it exists
    evidence_file = Path("downloads/evidence_final.csv")
    findings = []
    
    if evidence_file.exists():
        with open(evidence_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            findings = list(reader)
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Evidence Review - Duma Boko Video Analysis</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .stats {{ display: flex; gap: 20px; margin-bottom: 20px; }}
        .stat-box {{ background: white; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .finding {{ background: white; padding: 15px; margin-bottom: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .finding.unreviewed {{ border-left: 4px solid #3498db; }}
        .finding.confirmed {{ border-left: 4px solid #27ae60; }}
        .finding.rejected {{ border-left: 4px solid #e74c3c; }}
        .video-id {{ font-weight: bold; color: #2c3e50; }}
        .timestamp {{ color: #7f8c8d; font-size: 0.9em; }}
        .text {{ margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 3px; }}
        .phrase {{ color: #e74c3c; font-weight: bold; }}
        .actions {{ margin-top: 10px; }}
        button {{ padding: 8px 15px; margin-right: 10px; border: none; border-radius: 3px; cursor: pointer; }}
        .btn-confirm {{ background: #27ae60; color: white; }}
        .btn-reject {{ background: #e74c3c; color: white; }}
        .btn-skip {{ background: #95a5a6; color: white; }}
        .empty {{ text-align: center; padding: 50px; color: #7f8c8d; }}
        .export-btn {{ background: #3498db; color: white; padding: 10px 20px; font-size: 1.1em; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 Evidence Review Interface</h1>
        <p>Review and verify potential contradictions found in Duma Boko's video statements</p>
    </div>
    
    <div class="stats">
        <div class="stat-box">
            <strong>Total Findings</strong><br>
            <span style="font-size: 2em; color: #3498db;">{len(findings)}</span>
        </div>
        <div class="stat-box">
            <strong>Unreviewed</strong><br>
            <span style="font-size: 2em; color: #3498db;" id="unreviewed-count">{len(findings)}</span>
        </div>
        <div class="stat-box">
            <strong>Confirmed</strong><br>
            <span style="font-size: 2em; color: #27ae60;" id="confirmed-count">0</span>
        </div>
        <div class="stat-box">
            <strong>Rejected</strong><br>
            <span style="font-size: 2em; color: #e74c3c;" id="rejected-count">0</span>
        </div>
    </div>
    
    <div style="margin-bottom: 20px;">
        <button class="export-btn" onclick="exportResults()">📥 Export Confirmed Evidence</button>
    </div>
"""
    
    if not findings:
        html += """
    <div class="empty">
        <h2>No findings to review</h2>
        <p>Run the batch processor first to generate evidence findings.</p>
        <p>Then run: <code>python compile_evidence.py</code></p>
    </div>
"""
    else:
        for i, finding in enumerate(findings, 1):
            html += f"""
    <div class="finding unreviewed" id="finding-{i}">
        <div class="video-id">🎬 Video: {finding.get('video_id', 'Unknown')}</div>
        <div class="timestamp">⏱️ Time: {finding.get('timestamp', 'N/A')}</div>
        <div class="text">
            Matched phrase: <span class="phrase">"{finding.get('matched_phrase', '')}"</span><br><br>
            Context: {finding.get('text', finding.get('full_text', 'No text available'))}
        </div>
        <div class="actions">
            <button class="btn-confirm" onclick="markConfirmed({i})">✓ Confirm</button>
            <button class="btn-reject" onclick="markRejected({i})">✗ Reject</button>
            <button class="btn-skip" onclick="markSkipped({i})">Skip</button>
        </div>
    </div>
"""
    
    html += """
    <script>
        let confirmed = 0;
        let rejected = 0;
        let skipped = 0;
        const total = """ + str(len(findings)) + """;
        
        function updateStats() {
            document.getElementById('confirmed-count').textContent = confirmed;
            document.getElementById('rejected-count').textContent = rejected;
            document.getElementById('unreviewed-count').textContent = total - confirmed - rejected - skipped;
        }
        
        function markConfirmed(id) {
            const el = document.getElementById('finding-' + id);
            el.className = 'finding confirmed';
            confirmed++;
            updateStats();
        }
        
        function markRejected(id) {
            const el = document.getElementById('finding-' + id);
            el.className = 'finding rejected';
            rejected++;
            updateStats();
        }
        
        function markSkipped(id) {
            const el = document.getElementById('finding-' + id);
            el.style.display = 'none';
            skipped++;
            updateStats();
        }
        
        function exportResults() {
            alert('Export functionality would save confirmed findings to: downloads/evidence_confirmed.csv');
        }
    </script>
</body>
</html>
"""
    
    return html

def find_free_port():
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def launch_review_interface():
    """Launch the review interface in browser."""
    
    # Create HTML file
    html_content = create_review_html()
    html_path = Path("evidence_review.html")
    html_path.write_text(html_content, encoding='utf-8')
    
    # Find free port
    port = find_free_port()
    
    # Create simple HTTP server
    class Handler(SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
            super().end_headers()
        
        def log_message(self, format, *args):
            pass  # Suppress log messages
    
    server = HTTPServer(('', port), Handler)
    
    # Start server in thread
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    
    # Open browser
    url = f"http://localhost:{port}/evidence_review.html"
    print(f"\n🌐 Opening review interface at: {url}")
    webbrowser.open(url)
    
    print("\n" + "="*70)
    print("EVIDENCE REVIEW INTERFACE LAUNCHED")
    print("="*70)
    print("\nInstructions:")
    print("1. Review each finding in your browser")
    print("2. Click '✓ Confirm' for valid contradictions")
    print("3. Click '✗ Reject' for false positives")
    print("4. Click 'Skip' to hide and move on")
    print("\nPress Ctrl+C to stop the server when done")
    print("="*70 + "\n")
    
    try:
        while True:
            input()
    except KeyboardInterrupt:
        print("\n[OK] Shutting down server...")
        server.shutdown()
        print("[OK] Server stopped")

if __name__ == "__main__":
    launch_review_interface()
