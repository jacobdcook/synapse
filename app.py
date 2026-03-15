"""
QuickPaste - A lightweight pastebin clone with syntax highlighting.
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, abort, Response
from database import (
    init_db, save_paste, get_paste, list_pastes, delete_paste, get_paste_count
)
import json

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024  # 100KB max

# Supported languages
LANGUAGES = ['python', 'javascript', 'html', 'css', 'sql', 'bash', 'json', 'plain']

# Initialize database on startup
init_db()


@app.route('/')
def index():
    """Homepage with paste creation form."""
    return render_template('index.html', languages=LANGUAGES)


@app.route('/paste', methods=['POST'])
def create_paste():
    """Create a new paste."""
    # Get form data
    title = request.form.get('title', '').strip()[:200]  # Max 200 chars
    content = request.form.get('content', '').strip()
    language = request.form.get('language', 'plain')
    
    # Validation
    if not content:
        return render_template('index.html', languages=LANGUAGES, 
                              error='Paste content cannot be empty'), 400
    
    if len(content.encode('utf-8')) > 100 * 1024:
        return render_template('index.html', languages=LANGUAGES,
                              error='Paste size exceeds 100KB limit'), 400
    
    if language not in LANGUAGES:
        language = 'plain'
    
    # Save paste
    paste_id = save_paste(title, content, language)
    
    return redirect(url_for('view_paste', paste_id=paste_id))


@app.route('/p/<paste_id>')
def view_paste(paste_id):
    """View a single paste with syntax highlighting."""
    paste = get_paste(paste_id)
    
    if paste is None:
        abort(404)
    
    return render_template('view.html', paste=paste, languages=LANGUAGES)


@app.route('/p/<paste_id>/raw')
def raw_paste(paste_id):
    """View raw paste content."""
    paste = get_paste(paste_id)
    
    if paste is None:
        abort(404)
    
    return Response(paste['content'], mimetype='text/plain')


@app.route('/p/<paste_id>/delete', methods=['POST'])
def delete_paste_route(paste_id):
    """Delete a paste."""
    if delete_paste(paste_id):
        return redirect(url_for('list_pastes_route'))
    else:
        return redirect(url_for('view_paste', paste_id=paste_id))


@app.route('/list')
def list_pastes_route():
    """List recent pastes."""
    pastes = list_pastes(limit=50)
    return render_template('list.html', pastes=pastes)


@app.route('/api/pastes')
def api_pastes():
    """API endpoint: Get list of recent 50 pastes as JSON."""
    pastes = list_pastes(limit=50)
    
    # Convert to serializable format
    paste_list = []
    for paste in pastes:
        paste_dict = {
            'id': paste['id'],
            'title': paste['title'],
            'language': paste['language'],
            'created_at': paste['created_at'].isoformat() if paste['created_at'] else None,
            'url': url_for('view_paste', paste_id=paste['id'], _external=True)
        }
        paste_list.append(paste_dict)
    
    return jsonify({
        'pastes': paste_list,
        'total': len(paste_list)
    })


@app.route('/api/paste/<paste_id>', methods=['DELETE'])
def api_delete_paste(paste_id):
    """API endpoint: Delete a paste."""
    if delete_paste(paste_id):
        return jsonify({'message': 'Paste deleted successfully', 'id': paste_id}), 200
    else:
        return jsonify({'error': 'Paste not found'}), 404


@app.route('/api/paste/<paste_id>')
def api_get_paste(paste_id):
    """API endpoint: Get a single paste as JSON."""
    paste = get_paste(paste_id)
    
    if paste is None:
        return jsonify({'error': 'Paste not found'}), 404
    
    paste_dict = {
        'id': paste['id'],
        'title': paste['title'],
        'content': paste['content'],
        'language': paste['language'],
        'created_at': paste['created_at'].isoformat() if paste['created_at'] else None,
        'url': url_for('view_paste', paste_id=paste['id'], _external=True)
    }
    
    return jsonify(paste_dict)


@app.errorhandler(404)
def not_found_error(error):
    """Custom 404 error page."""
    return render_template('404.html'), 404


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle paste size exceeding limit."""
    return render_template('index.html', languages=LANGUAGES,
                          error='Paste size exceeds 100KB limit'), 413


@app.errorhandler(500)
def internal_server_error(error):
    """Custom 500 error page."""
    return render_template('500.html'), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
