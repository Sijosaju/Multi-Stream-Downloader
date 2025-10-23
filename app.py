# app.py - Flask application with File Manager
from flask import Flask, render_template, request, jsonify, send_file
import os
import threading
import time
import json
import mimetypes
import glob
from datetime import datetime
from downloader import MultiStreamDownloader
from simple_downloader import SimpleDownloader
from config import DOWNLOAD_FOLDER, FLASK_HOST, FLASK_PORT, FLASK_DEBUG

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

class DownloadManager:
    def __init__(self):
        self.active_downloads = {}
    
    def start_download(self, url, mode, num_streams):
        download_id = str(int(time.time() * 1000))
        
        try:
            # Create appropriate downloader
            if mode == "single":
                downloader = SimpleDownloader(url, progress_callback=None)
            else:
                downloader = MultiStreamDownloader(url, num_streams=num_streams, progress_callback=None)
            
            self.active_downloads[download_id] = {
                'downloader': downloader,
                'url': url,
                'mode': mode,
                'status': 'downloading',
                'progress': 0,
                'speed': 0,
                'start_time': time.time(),
                'thread': None,
                'filename': None,
                'error': None,
                'total_size': 0,  # Track total file size
                'downloaded_size': 0  # Track downloaded bytes
            }
            
            # Start download in thread
            thread = threading.Thread(target=self._download_thread, args=(download_id,))
            thread.daemon = True
            thread.start()
            self.active_downloads[download_id]['thread'] = thread
            
            return download_id
        except Exception as e:
            print(f"Error starting download: {str(e)}")
            raise e
    
    def _download_thread(self, download_id):
        download_info = self.active_downloads.get(download_id)
        if not download_info:
            return
            
        downloader = download_info['downloader']
        
        try:
            # Get file info before starting download
            if hasattr(downloader, 'get_file_info'):
                file_size, filename = downloader.get_file_info()
                download_info['total_size'] = file_size
                download_info['filename'] = filename
            elif hasattr(downloader, 'check_download_support'):
                supports_ranges, file_size, filename = downloader.check_download_support()
                download_info['total_size'] = file_size
                download_info['filename'] = filename
            
            result = downloader.download()
            if result:
                download_info['status'] = 'completed'
                download_info['result_path'] = result
                download_info['filename'] = os.path.basename(result)
                # Set downloaded size to total size when completed
                download_info['downloaded_size'] = download_info['total_size']
                # Safely get metrics
                try:
                    download_info['metrics'] = downloader.get_detailed_metrics()
                except Exception as e:
                    print(f"Error getting metrics: {str(e)}")
                    download_info['metrics'] = None
            else:
                download_info['status'] = 'failed'
                download_info['error'] = 'Download failed'
        except Exception as e:
            download_info['status'] = 'failed'
            download_info['error'] = str(e)
            print(f"Download error for {download_id}: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def get_download_status(self, download_id):
        try:
            if download_id not in self.active_downloads:
                return None
                
            download_info = self.active_downloads[download_id]
            
            # Safely update progress if downloader exists
            if 'downloader' in download_info and download_info['downloader']:
                downloader = download_info['downloader']
                try:
                    if hasattr(downloader, 'downloaded_bytes') and hasattr(downloader, 'file_size'):
                        if downloader.file_size > 0:
                            download_info['progress'] = (downloader.downloaded_bytes / downloader.file_size) * 100
                            download_info['downloaded_size'] = downloader.downloaded_bytes  # Track downloaded bytes
                            download_info['total_size'] = downloader.file_size  # Track total size
                        # Safely get speed
                        try:
                            download_info['speed'] = downloader.get_speed() if hasattr(downloader, 'get_speed') else 0
                        except:
                            download_info['speed'] = 0
                except Exception as e:
                    print(f"Error updating progress: {str(e)}")
                    # Don't fail the entire request if progress update fails
            
            # Create a serializable status object (without the downloader instance)
            serializable_status = {
                'url': download_info['url'],
                'mode': download_info['mode'],
                'status': download_info['status'],
                'progress': download_info['progress'],
                'speed': download_info['speed'],
                'start_time': download_info['start_time'],
                'filename': download_info.get('filename'),
                'error': download_info.get('error'),
                'metrics': download_info.get('metrics'),
                'total_size': download_info.get('total_size', 0),  # Include total size
                'downloaded_size': download_info.get('downloaded_size', 0)  # Include downloaded size
            }
            
            return serializable_status
        except Exception as e:
            print(f"Error in get_download_status: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def cancel_download(self, download_id):
        if download_id in self.active_downloads:
            download_info = self.active_downloads[download_id]
            if 'downloader' in download_info and download_info['downloader']:
                download_info['downloader'].cancel()
            download_info['status'] = 'cancelled'
            return True
        return False

# Initialize download manager
download_manager = DownloadManager()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/downloads', methods=['POST'])
def start_download():
    data = request.json
    url = data.get('url', '').strip()
    mode = data.get('mode', 'multi')
    num_streams = int(data.get('num_streams', 8))
    
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    if not url.startswith(('http://', 'https://')):
        return jsonify({'error': 'URL must start with http:// or https://'}), 400
    
    try:
        download_id = download_manager.start_download(url, mode, num_streams)
        return jsonify({
            'download_id': download_id,
            'message': 'Download started successfully'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/downloads/<download_id>')
def get_download_status(download_id):
    try:
        status = download_manager.get_download_status(download_id)
        if status:
            return jsonify(status)
        else:
            return jsonify({'error': 'Download not found'}), 404
    except Exception as e:
        print(f"Error getting download status for {download_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Internal server error: {str(e)}'}), 500

@app.route('/api/downloads/<download_id>/cancel', methods=['POST'])
def cancel_download(download_id):
    if download_manager.cancel_download(download_id):
        return jsonify({'message': 'Download cancelled successfully'})
    else:
        return jsonify({'error': 'Download not found'}), 404

@app.route('/api/downloads/<download_id>/metrics')
def get_download_metrics(download_id):
    status = download_manager.get_download_status(download_id)
    if status and 'metrics' in status:
        return jsonify(status['metrics'])
    else:
        return jsonify({'error': 'Metrics not available'}), 404

@app.route('/downloads/<filename>')
def download_file(filename):
    file_path = os.path.join(DOWNLOAD_FOLDER, filename)
    if os.path.exists(file_path):
        # Determine if we should display inline or force download
        mime_type, encoding = mimetypes.guess_type(filename)
        
        # Force download for certain file types
        force_download_types = ['.zip', '.rar', '.7z', '.exe', '.msi', '.dmg', '.pkg', '.deb', '.rpm']
        as_attachment = any(filename.lower().endswith(ext) for ext in force_download_types)
        
        # For safe file types, try to open in browser
        safe_types = ['.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.txt', '.mp4', '.mp3', '.webm', '.avi']
        can_open_in_browser = any(filename.lower().endswith(ext) for ext in safe_types)
        
        if can_open_in_browser and not as_attachment:
            # Try to open in browser
            return send_file(
                file_path,
                as_attachment=False,
                mimetype=mime_type
            )
        else:
            # Force download
            return send_file(
                file_path, 
                as_attachment=True,
                download_name=filename
            )
    else:
        return jsonify({'error': 'File not found'}), 404

@app.route('/api/downloads')
def list_downloads():
    downloads = []
    for download_id, info in download_manager.active_downloads.items():
        # Create serializable download info
        serializable_info = {
            'id': download_id,
            'url': info['url'],
            'status': info['status'],
            'progress': info.get('progress', 0),
            'mode': info['mode'],
            'filename': info.get('filename'),
            'speed': info.get('speed', 0),
            'total_size': info.get('total_size', 0),  # Include total size
            'downloaded_size': info.get('downloaded_size', 0)  # Include downloaded size
        }
        downloads.append(serializable_info)
    return jsonify(downloads)

@app.route('/api/files')
def list_files():
    """List all files in the download folder."""
    try:
        files = []
        download_folder = DOWNLOAD_FOLDER
        
        # Get all files in the download folder
        for file_path in glob.glob(os.path.join(download_folder, '*')):
            if os.path.isfile(file_path):
                filename = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                modified_time = os.path.getmtime(file_path)
                
                # Skip temporary files and system files
                if not (filename.startswith('.') or 
                       filename.startswith('download_metrics') or
                       filename.endswith('_simple_metrics.txt') or
                       filename.endswith('.part')):
                    
                    files.append({
                        'name': filename,
                        'size': file_size,
                        'modified': modified_time,
                        'path': file_path
                    })
        
        # Sort by modification time (newest first)
        files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify(files)
    except Exception as e:
        print(f"Error listing files: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Delete a file from the download folder."""
    try:
        # Security check: prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'error': 'Invalid filename'}), 400
            
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'File not found'}), 404
            
        # Additional security check
        if not os.path.realpath(file_path).startswith(os.path.realpath(DOWNLOAD_FOLDER)):
            return jsonify({'error': 'Access denied'}), 403
            
        os.remove(file_path)
        return jsonify({'message': 'File deleted successfully'})
        
    except Exception as e:
        print(f"Error deleting file {filename}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# @app.route('/downloads/')
# def list_downloads_directory():
#     """Serve a simple directory listing page."""
#     try:
#         files = []
#         download_folder = DOWNLOAD_FOLDER
        
#         for file_path in glob.glob(os.path.join(download_folder, '*')):
#             if os.path.isfile(file_path):
#                 filename = os.path.basename(file_path)
#                 file_size = os.path.getsize(file_path)
#                 modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
#                 # Skip temporary files
#                 if not (filename.startswith('.') or 
#                        filename.startswith('download_metrics') or
#                        filename.endswith('_simple_metrics.txt') or
#                        filename.endswith('.part')):
                    
#                     files.append({
#                         'name': filename,
#                         'size': file_size,
#                         'modified': modified_time.strftime('%Y-%m-%d %H:%M:%S'),
#                         'url': f'/downloads/{filename}'
#                     })
        
#         # Sort by modification time (newest first)
#         files.sort(key=lambda x: x['modified'], reverse=True)
        
#         # Simple HTML directory listing
#         html = """
#         <!DOCTYPE html>
#         <html>
#         <head>
#             <title>TurboLane - Downloaded Files</title>
#             <style>
#                 body { 
#                     font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
#                     margin: 0; 
#                     padding: 0;
#                     background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
#                     color: #f1f5f9;
#                     min-height: 100vh;
#                 }
#                 .container {
#                     max-width: 1200px;
#                     margin: 0 auto;
#                     padding: 40px;
#                 }
#                 .header {
#                     text-align: center;
#                     margin-bottom: 40px;
#                     padding-bottom: 20px;
#                     border-bottom: 1px solid #334155;
#                 }
#                 .header h1 {
#                     font-size: 32px;
#                     font-weight: 700;
#                     background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#                     -webkit-background-clip: text;
#                     -webkit-text-fill-color: transparent;
#                     margin-bottom: 8px;
#                 }
#                 .header p {
#                     color: #94a3b8;
#                     font-size: 16px;
#                 }
#                 table {
#                     width: 100%;
#                     border-collapse: collapse;
#                     background: #1e293b;
#                     border-radius: 12px;
#                     overflow: hidden;
#                     box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
#                 }
#                 th, td {
#                     padding: 16px 20px;
#                     text-align: left;
#                     border-bottom: 1px solid #334155;
#                 }
#                 th {
#                     background: linear-gradient(135deg, #1e293b 0%, #1a253c 100%);
#                     font-weight: 600;
#                     color: #f1f5f9;
#                 }
#                 tr:hover {
#                     background: rgba(255, 255, 255, 0.05);
#                 }
#                 .file-link {
#                     color: #60a5fa;
#                     text-decoration: none;
#                     font-weight: 500;
#                     transition: color 0.3s ease;
#                 }
#                 .file-link:hover {
#                     color: #3b82f6;
#                     text-decoration: underline;
#                 }
#                 .back-link {
#                     display: inline-flex;
#                     align-items: center;
#                     gap: 8px;
#                     color: #94a3b8;
#                     text-decoration: none;
#                     margin-bottom: 20px;
#                     padding: 10px 16px;
#                     border: 1px solid #334155;
#                     border-radius: 8px;
#                     transition: all 0.3s ease;
#                 }
#                 .back-link:hover {
#                     color: #f1f5f9;
#                     border-color: #475569;
#                     background: rgba(255, 255, 255, 0.05);
#                 }
#                 .file-size {
#                     color: #94a3b8;
#                     font-family: 'JetBrains Mono', monospace;
#                 }
#                 .file-date {
#                     color: #94a3b8;
#                 }
#                 .empty-state {
#                     text-align: center;
#                     padding: 60px 40px;
#                     color: #94a3b8;
#                 }
#                 .empty-state i {
#                     font-size: 64px;
#                     color: #334155;
#                     margin-bottom: 20px;
#                     opacity: 0.5;
#                 }
#             </style>
#             <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
#             <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
#         </head>
#         <body>
#             <div class="container">
#                 <div class="header">
#                     <h1><i class="fas fa-folder-open"></i> TurboLane File Manager</h1>
#                     <p>All your downloaded files in one place</p>
#                 </div>
                
#                 <a href="/" class="back-link">
#                     <i class="fas fa-arrow-left"></i>
#                     Back to Download Manager
#                 </a>
#         """
        
#         if not files:
#             html += """
#                 <div class="empty-state">
#                     <i class="fas fa-folder-open"></i>
#                     <p>No files downloaded yet</p>
#                     <small>Downloaded files will appear here</small>
#                 </div>
#             """
#         else:
#             html += """
#                 <table>
#                     <thead>
#                         <tr>
#                             <th>Filename</th>
#                             <th>Size</th>
#                             <th>Modified</th>
#                             <th>Action</th>
#                         </tr>
#                     </thead>
#                     <tbody>
#             """
            
#             for file in files:
#                 size_mb = file['size'] / (1024 * 1024)
#                 html += f"""
#                         <tr>
#                             <td>
#                                 <i class="fas fa-file" style="margin-right: 8px; color: #94a3b8;"></i>
#                                 {file['name']}
#                             </td>
#                             <td class="file-size">{size_mb:.2f} MB</td>
#                             <td class="file-date">{file['modified']}</td>
#                             <td>
#                                 <a href="{file['url']}" class="file-link" download>
#                                     <i class="fas fa-download"></i>
#                                     Download
#                                 </a>
#                             </td>
#                         </tr>
#                 """
            
#             html += """
#                     </tbody>
#                 </table>
#             """
        
#         html += """
#             </div>
#         </body>
#         </html>
#         """
        
#         return html
#     except Exception as e:
#         print(f"Error generating directory listing: {str(e)}")
#         import traceback
#         traceback.print_exc()
#         return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_stats():
    """Get download statistics."""
    try:
        total_files = 0
        total_size = 0
        download_folder = DOWNLOAD_FOLDER
        
        for file_path in glob.glob(os.path.join(download_folder, '*')):
            if os.path.isfile(file_path):
                filename = os.path.basename(file_path)
                # Skip temporary files
                if not (filename.startswith('.') or 
                       filename.startswith('download_metrics') or
                       filename.endswith('_simple_metrics.txt') or
                       filename.endswith('.part')):
                    total_files += 1
                    total_size += os.path.getsize(file_path)
        
        # Get active downloads count
        active_downloads = len([d for d in download_manager.active_downloads.values() 
                              if d.get('status') == 'downloading'])
        
        return jsonify({
            'total_files': total_files,
            'total_size': total_size,
            'total_size_mb': total_size / (1024 * 1024),
            'active_downloads': active_downloads,
            'download_folder': download_folder
        })
    except Exception as e:
        print(f"Error getting stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Ensure download folder exists
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    
    print(f"🚀 TurboLane Download Manager starting...")
    print(f"📁 Download folder: {DOWNLOAD_FOLDER}")
    print(f"🌐 Server running at: http://{FLASK_HOST}:{FLASK_PORT}")
    print(f"🔧 Debug mode: {FLASK_DEBUG}")
    
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=FLASK_PORT)